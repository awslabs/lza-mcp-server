# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Update UC configuration files in session directory."""

from pathlib import Path
from typing import Dict, Any, Optional
import re
import yaml

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    validate_path_security,
    create_error_response,
    create_success_response,
    categorize_uc_merge_error,
)
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager
from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_cidr_format,
    validate_asn_range,
    validate_vpc_mask_length,
    validate_yaml_syntax,
)


def _parse_key_path(key: str) -> list:
    """Parse a key path into components.
    
    Examples:
        "HomeRegion" -> ["HomeRegion"]
        "mandatoryAccounts[0].email" -> ["mandatoryAccounts", 0, "email"]
        "workloadAccounts[2].name" -> ["workloadAccounts", 2, "name"]
    """
    parts = []
    # Split by dots, but handle array indices
    segments = key.split('.')
    
    for segment in segments:
        # Check if segment contains array index
        match = re.match(r'^([^\[]+)\[(\d+)\]$', segment)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(segment)
    
    return parts


def _get_nested_value(data: Dict[str, Any], key: str) -> Optional[Any]:
    """Get a value from nested dictionary/list structure using a key path."""
    parts = _parse_key_path(key)
    current = data
    
    try:
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                current = current[part]
            else:
                return None
            
            if current is None:
                return None
        
        return current
    except (KeyError, IndexError, TypeError):
        return None


def _set_nested_value(data: Dict[str, Any], key: str, value: Any) -> None:
    """Set a value in nested dictionary/list structure using a key path."""
    parts = _parse_key_path(key)
    
    if not parts:
        return
    
    # Navigate to the parent of the target
    current = data
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                # Create intermediate structure if needed
                next_part = parts[parts.index(part) + 1]
                if isinstance(next_part, int):
                    current[part] = []
                else:
                    current[part] = {}
            current = current[part]
        elif isinstance(current, list):
            current = current[part]
    
    # Set the final value
    final_key = parts[-1]
    if isinstance(current, dict):
        current[final_key] = value
    elif isinstance(current, list):
        current[final_key] = value


async def update_uc_file(
    session_id: str,
    file_path: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update a UC configuration file in the session directory with new values.
    
    This tool allows updating UC configuration files with user customizations.
    It validates the session, file existence, and applies security checks before
    updating. After updates, it validates YAML syntax and performs basic value
    validation for CIDR ranges and numeric values.
    
    Args:
        session_id: Session identifier from start_uc_merge_session()
        file_path: Relative path to file within session (e.g., "replacements-config.yaml")
        updates: Dictionary of key-value pairs to update in the YAML file
        
    Returns:
        {
            "success": bool,
            "session_id": str,
            "file_path": str,
            "updates_applied": Dict[str, Any],
            "validation_errors": List[str],
            "next_steps": str
        }
        
    Example:
        result = await update_uc_file(
            session_id="uc-session-20250127-143022",
            file_path="replacements-config.yaml",
            updates={
                "HomeRegionIngressCidr": "10.0.0.0/16",
                "DevVpcMaskLength": 24
            }
        )
    """
    session_manager = SessionManager()
    validation_errors = []
    
    # Validate session_id
    if not session_id:
        return create_error_response(
            error_message="Session ID is required",
            error_code="MISSING_SESSION_ID",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Session ID parameter is required",
                "Start a new session with start_uc_merge_session()",
                "Pass the session_id returned from start_uc_merge_session()"
            ],
            next_steps="Call start_uc_merge_session() to create a new session"
        )
    
    # Validate session exists
    is_valid, error_msg = session_manager.validate_session(session_id)
    if not is_valid:
        return create_error_response(
            error_message=error_msg,
            error_code="INVALID_SESSION",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Session does not exist or is invalid",
                "Start a new session with start_uc_merge_session()",
                "Verify the session_id is correct"
            ],
            context={"session_id": session_id},
            next_steps="Call start_uc_merge_session() to create a new session"
        )
    
    # Validate file_path
    if not file_path:
        return create_error_response(
            error_message="File path is required",
            error_code="MISSING_FILE_PATH",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "File path parameter is required",
                "Provide a relative path to the file within the session directory",
                "Example: 'replacements-config.yaml' or 'accounts-config.yaml'"
            ],
            next_steps="Provide a valid file path and retry update_uc_file()"
        )
    
    # Validate updates parameter
    if not updates or not isinstance(updates, dict):
        return create_error_response(
            error_message="Updates must be a non-empty dictionary",
            error_code="INVALID_UPDATES",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Updates parameter must be a dictionary of key-value pairs",
                "Provide at least one update to apply",
                "Example: {'HomeRegionIngressCidr': '10.0.0.0/16'}"
            ],
            next_steps="Provide a valid updates dictionary and retry update_uc_file()"
        )
    
    # Get session path
    session_path = session_manager.get_session_path(session_id)
    
    # Validate path security
    is_valid, error_msg, resolved_path = validate_path_security(
        file_path,
        session_path,
        "update"
    )
    
    if not is_valid:
        error_info = categorize_uc_merge_error(Exception(error_msg))
        return create_error_response(
            error_message=error_msg,
            error_code=error_info["error_code"],
            category=error_info["category"],
            troubleshooting=error_info["troubleshooting"],
            context={"file_path": file_path, "session_id": session_id},
            next_steps="Provide a valid relative path within the session directory"
        )
    
    # Check if file exists
    if not resolved_path.exists():
        return create_error_response(
            error_message=f"File not found: {file_path}",
            error_code="FILE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                "File does not exist in the session directory",
                "Verify the file path is correct",
                "Call get_uc_network_customization_guide() to see available files",
                "Use read_uc_file() to verify file existence before updating"
            ],
            context={"file_path": file_path, "session_id": session_id},
            next_steps="Verify the file path and retry update_uc_file()"
        )
    
    # Read and parse the YAML file
    try:
        with open(resolved_path, "r") as f:
            file_content = f.read()
        
        yaml_data = yaml.safe_load(file_content)
        
        if yaml_data is None:
            yaml_data = {}
        
    except yaml.YAMLError as e:
        return create_error_response(
            error_message=f"Failed to parse YAML file: {str(e)}",
            error_code="YAML_PARSE_ERROR",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                "File contains invalid YAML syntax",
                "Check the file for syntax errors",
                "Ensure proper indentation and formatting",
                "Use a YAML validator to check the file"
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Fix YAML syntax errors in the file and retry"
        )
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to read file: {str(e)}",
            error_code="FILE_READ_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "File could not be read",
                "Check file permissions",
                "Ensure the file is not locked by another process"
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check file permissions and retry update_uc_file()"
        )
    
    # Apply updates and validate
    updates_applied = {}
    
    # Check if this is replacements-config.yaml which has special structure
    is_replacements_config = file_path.endswith("replacements-config.yaml")
    
    for key, value in updates.items():
        # Parse the key path (e.g., "mandatoryAccounts[0].email" or "HomeRegion")
        old_value = _get_nested_value(yaml_data, key)
        
        # Special handling for replacements-config.yaml
        if is_replacements_config and "globalReplacements" in yaml_data:
            # Find the key in globalReplacements array and update its value
            found = False
            for item in yaml_data.get("globalReplacements", []):
                if isinstance(item, dict) and item.get("key") == key:
                    old_value = item.get("value")
                    item["value"] = value
                    found = True
                    break
            
            # If not found in globalReplacements, fall back to top-level update
            if not found:
                _set_nested_value(yaml_data, key, value)
        else:
            # Apply the update normally
            _set_nested_value(yaml_data, key, value)
        
        updates_applied[key] = {"old": old_value, "new": value}
        
        # Validate based on value type and key name
        if isinstance(value, str):
            # Check if it looks like a CIDR
            if "cidr" in key.lower() or "/" in value:
                is_valid_cidr, cidr_error = validate_cidr_format(value)
                if not is_valid_cidr:
                    validation_errors.append(
                        f"{key}: {cidr_error}"
                    )
        
        elif isinstance(value, int):
            # Check if it's an ASN
            if "asn" in key.lower():
                is_valid_asn, asn_error = validate_asn_range(value)
                if not is_valid_asn:
                    validation_errors.append(
                        f"{key}: {asn_error}"
                    )
            
            # Check if it's a VPC mask length
            elif "vpc" in key.lower() and "mask" in key.lower():
                is_valid_mask, mask_error = validate_vpc_mask_length(value)
                if not is_valid_mask:
                    validation_errors.append(
                        f"{key}: {mask_error}"
                    )
            
            # Check if it's a subnet mask length
            elif "subnet" in key.lower() and "mask" in key.lower():
                # For subnet masks, we need the VPC mask to validate
                # For now, just check it's in reasonable range (16-28)
                if value < 16 or value > 28:
                    validation_errors.append(
                        f"{key}: Subnet mask length {value} out of reasonable range (16-28)"
                    )
    
    # If there are validation errors, return them without writing the file
    if validation_errors:
        return create_error_response(
            error_message=f"Validation failed for {len(validation_errors)} field(s)",
            error_code="VALIDATION_FAILED",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "One or more values failed validation",
                "Review the validation_errors list for details",
                "Correct the invalid values and retry update_uc_file()"
            ],
            context={
                "file_path": file_path,
                "session_id": session_id,
                "validation_errors": validation_errors,
                "failed_updates": updates_applied
            },
            next_steps="Review validation errors, correct the values, and retry update_uc_file()"
        )
    
    # Convert back to YAML and validate syntax
    try:
        updated_yaml = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
        
        # Validate the generated YAML
        is_valid_yaml, yaml_error = validate_yaml_syntax(updated_yaml)
        if not is_valid_yaml:
            return create_error_response(
                error_message=f"Generated YAML is invalid: {yaml_error}",
                error_code="YAML_GENERATION_ERROR",
                category=ErrorCategory.CONFIGURATION,
                troubleshooting=[
                    "Updates resulted in invalid YAML",
                    "This is likely a bug in the update logic",
                    "Try updating fewer fields at once",
                    "Contact support if the issue persists"
                ],
                context={"file_path": file_path, "error": yaml_error},
                next_steps="Try updating fewer fields or contact support"
            )
        
    except yaml.YAMLError as e:
        return create_error_response(
            error_message=f"Failed to generate YAML: {str(e)}",
            error_code="YAML_GENERATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                "Could not convert updates to YAML format",
                "Check that all values are YAML-compatible types",
                "Ensure no circular references in the data"
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Review the updates and retry with valid YAML-compatible values"
        )
    
    # Write the updated YAML back to the file
    try:
        with open(resolved_path, "w") as f:
            f.write(updated_yaml)
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to write file: {str(e)}",
            error_code="FILE_WRITE_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Could not write updated content to file",
                "Check file permissions",
                "Ensure sufficient disk space",
                "Verify the file is not locked by another process"
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check file permissions and disk space, then retry"
        )
    
    # Success response
    next_steps = (
        f"Updates applied successfully to {file_path}. "
        "Ask the user if they want to make additional changes to this or other files, "
        "or proceed with copy_uc_to_lza_config() to merge the UC configuration."
    )
    
    return create_success_response(
        data={
            "session_id": session_id,
            "file_path": file_path,
            "updates_applied": updates_applied,
            "validation_errors": []
        },
        next_steps=next_steps
    )
