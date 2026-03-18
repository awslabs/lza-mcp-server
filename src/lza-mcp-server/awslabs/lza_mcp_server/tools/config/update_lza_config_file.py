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

"""Update LZA configuration files in the extracted configuration directory."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import yaml
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    LZA_CONFIG_BASE_PATH,
    categorize_uc_merge_error,
    create_error_response,
    create_success_response,
    validate_path_security,
)
from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_asn_range,
    validate_cidr_format,
    validate_vpc_mask_length,
    validate_yaml_syntax,
)

logger = logging.getLogger(__name__)


def _parse_key_path(key: str) -> list:
    """Parse a dot-notation key path into components.

    Supports simple keys, nested dot paths, and array index notation.

    Examples:
        "homeRegion" -> ["homeRegion"]
        "vpcs[0].vpcName" -> ["vpcs", 0, "vpcName"]
        "workloadAccounts[2].name" -> ["workloadAccounts", 2, "name"]

    Args:
        key: Dot-notation key path string.

    Returns:
        List of path components (strings for dict keys, ints for list indices).
    """
    parts: list = []
    segments = key.split(".")

    for segment in segments:
        match = re.match(r"^([^\[]+)\[(\d+)\]$", segment)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(segment)

    return parts


def _get_nested_value(data: Dict[str, Any], key: str) -> Optional[Any]:
    """Get a value from a nested dict/list structure using a dot-notation key path."""
    parts = _parse_key_path(key)
    current: Any = data

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
    """Set a value in a nested dict/list structure using a dot-notation key path."""
    parts = _parse_key_path(key)

    if not parts:
        return

    current: Any = data
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, dict):
            if part not in current:
                next_part = parts[i + 1]
                if isinstance(next_part, int):
                    current[part] = []
                else:
                    current[part] = {}
            current = current[part]
        elif isinstance(current, list):
            current = current[part]

    final_key = parts[-1]
    if isinstance(current, dict):
        current[final_key] = value
    elif isinstance(current, list):
        current[final_key] = value


def _validate_update_values(
    updates: Dict[str, Any],
) -> List[str]:
    """Validate update values for known LZA patterns (CIDR, ASN, masks).

    Args:
        updates: Dictionary of key-value pairs to validate.

    Returns:
        List of validation error strings (empty if all values are valid).
    """
    validation_errors: List[str] = []

    for key, value in updates.items():
        if isinstance(value, str):
            if "cidr" in key.lower() or "/" in value:
                is_valid, error = validate_cidr_format(value)
                if not is_valid:
                    validation_errors.append(f"{key}: {error}")

        elif isinstance(value, int):
            if "asn" in key.lower():
                is_valid, error = validate_asn_range(value)
                if not is_valid:
                    validation_errors.append(f"{key}: {error}")
            elif "vpc" in key.lower() and "mask" in key.lower():
                is_valid, error = validate_vpc_mask_length(value)
                if not is_valid:
                    validation_errors.append(f"{key}: {error}")
            elif "subnet" in key.lower() and "mask" in key.lower():
                if value < 16 or value > 28:
                    validation_errors.append(
                        f"{key}: Subnet mask length {value} out of reasonable range (16-28)"
                    )

    return validation_errors


async def update_lza_config_file(
    ctx: Context,
    file_path: str,
    updates: Optional[Dict[str, Any]] = None,
    insert_path: Optional[str] = None,
    insert_value: Optional[Dict[str, Any]] = None,
    delete_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an LZA configuration file in the extracted configuration directory.

    Supports three mutually exclusive modes:

    MODE 1 — Update existing values (use ``updates``):
        Modify existing key-value pairs using dot-notation paths with optional
        array index syntax. Also adds new keys if they don't exist yet.

    MODE 2 — Insert a new item into a list (use ``insert_path`` + ``insert_value``):
        Append a new object to an existing YAML list, such as adding a new VPC
        to the ``vpcs`` array or a new workload account.

    MODE 3 — Delete a key or list item (use ``delete_path``):
        Remove a key from a dict or an item from a list using dot-notation path.

    Args:
        ctx: MCP context for logging.
        file_path: Relative path to the config file (e.g., "network-config.yaml").
        updates: Dict of key-value pairs to set. Keys use dot/index notation
            (e.g., ``"vpcs[0].vpcName"``). Mutually exclusive with other modes.
        insert_path: Dot-notation path to a list where ``insert_value`` will be
            appended (e.g., ``"vpcs"``, ``"workloadAccounts"``).
            Required together with ``insert_value``.
        insert_value: Dictionary object to append at ``insert_path``.
            Required together with ``insert_path``.
        delete_path: Dot-notation path to the key or list item to remove
            (e.g., ``"vpcs[2]"``, ``"workloadAccounts"``).
            Mutually exclusive with other modes.

    Returns:
        Dictionary with operation results:
        - success: bool
        - file_path: str
        - updates_applied / inserted / deleted: change details
        - validation_errors: list (empty on success)

    Examples:
        # Update existing values
        await update_lza_config_file(
            ctx,
            file_path="network-config.yaml",
            updates={"vpcs[0].vpcName": "prod-vpc"}
        )

        # Insert a new VPC into the vpcs list
        await update_lza_config_file(
            ctx,
            file_path="network-config.yaml",
            insert_path="vpcs",
            insert_value={
                "vpcName": "dev-vpc",
                "account": "Development",
                "region": "us-east-1",
                "cidrs": [{"value": "10.3.0.0/16"}]
            }
        )

        # Add a new workload account
        await update_lza_config_file(
            ctx,
            file_path="accounts-config.yaml",
            insert_path="workloadAccounts",
            insert_value={
                "name": "SharedServices",
                "email": "shared@example.com",
                "organizationalUnit": "Infrastructure"
            }
        )

        # Remove the third VPC
        await update_lza_config_file(
            ctx,
            file_path="network-config.yaml",
            delete_path="vpcs[2]"
        )

        # Remove an entire top-level key
        await update_lza_config_file(
            ctx,
            file_path="network-config.yaml",
            delete_path="endpointPolicies"
        )
    """
    logger.info(f"Updating LZA config file: {file_path}")

    # --- Parameter validation ---------------------------------------------------

    if not file_path:
        return create_error_response(
            error_message="File path is required",
            error_code="MISSING_FILE_PATH",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Provide a relative path to the configuration file",
                "Example: 'network-config.yaml' or 'accounts-config.yaml'",
            ],
            next_steps="Provide a valid file_path and retry.",
        )

    has_updates = updates is not None and len(updates) > 0
    has_insert = insert_path is not None or insert_value is not None
    has_delete = delete_path is not None

    mode_count = sum([has_updates, has_insert, has_delete])

    if mode_count > 1:
        return create_error_response(
            error_message="Only one mode allowed per call: 'updates', 'insert_path'/'insert_value', or 'delete_path'",
            error_code="MUTUALLY_EXCLUSIVE_PARAMS",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Use 'updates' to modify values, 'insert_path'+'insert_value' to add a list item, or 'delete_path' to remove",
                "Do not combine modes in a single call",
            ],
            next_steps="Choose one mode and retry.",
        )

    if mode_count == 0:
        return create_error_response(
            error_message="One of 'updates', 'insert_path'+'insert_value', or 'delete_path' is required",
            error_code="MISSING_PARAMS",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Provide 'updates' dict to modify values, 'insert_path'+'insert_value' to append, or 'delete_path' to remove",
            ],
            next_steps="Provide the required parameters and retry.",
        )

    if has_insert:
        if insert_path is None or insert_value is None:
            return create_error_response(
                error_message="Both 'insert_path' and 'insert_value' are required for insert mode",
                error_code="INCOMPLETE_INSERT_PARAMS",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "'insert_path' specifies the target list (e.g., 'vpcs')",
                    "'insert_value' is the dict to append",
                ],
                next_steps="Provide both insert_path and insert_value.",
            )
        if not isinstance(insert_value, dict):
            return create_error_response(
                error_message="'insert_value' must be a dictionary",
                error_code="INVALID_INSERT_VALUE",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "insert_value should be a dict representing the YAML object to append",
                ],
                next_steps="Provide a valid dict for insert_value.",
            )

    if has_updates and not isinstance(updates, dict):
        return create_error_response(
            error_message="'updates' must be a non-empty dictionary",
            error_code="INVALID_UPDATES",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Provide a dictionary of key-value pairs",
                "Example: {'vpcs[0].vpcName': 'prod-vpc'}",
            ],
            next_steps="Provide a valid updates dictionary.",
        )

    # --- Resolve and validate file path -----------------------------------------

    base_directory = LZA_CONFIG_BASE_PATH / "retrieved-config"

    if not base_directory.exists():
        return create_error_response(
            error_message=(
                "LZA configuration directory not found. "
                "Call getLzaConfiguration() first to retrieve the configuration."
            ),
            error_code="CONFIG_NOT_RETRIEVED",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                "Call getLzaConfiguration() to download the LZA configuration from S3",
                "Verify the configuration was extracted successfully",
            ],
            next_steps="Call getLzaConfiguration() before updating files.",
        )

    is_valid, error_msg, resolved_path = validate_path_security(
        file_path, base_directory, "update"
    )
    if not is_valid:
        error_info = categorize_uc_merge_error(Exception(error_msg))
        return create_error_response(
            error_message=error_msg,
            error_code=error_info["error_code"],
            category=error_info["category"],
            troubleshooting=error_info["troubleshooting"],
            context={"file_path": file_path},
            next_steps="Provide a valid relative path within the configuration directory.",
        )

    if not resolved_path.exists():
        return create_error_response(
            error_message=f"File not found: {file_path}",
            error_code="FILE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                f"Verify the file path is correct: {file_path}",
                "Use readLzaConfigFile() to check available files",
                "Ensure getLzaConfiguration() extracted all files",
            ],
            context={"file_path": file_path},
            next_steps="Verify the file path and retry.",
        )

    if not resolved_path.is_file():
        return create_error_response(
            error_message=f"Path is a directory, not a file: {file_path}",
            error_code="NOT_A_FILE",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Provide a path to a specific file, not a directory",
            ],
            context={"file_path": file_path},
            next_steps="Provide a file path like 'network-config.yaml'.",
        )

    # --- Read and parse YAML ----------------------------------------------------

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
                "Check indentation and formatting",
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Fix YAML syntax errors and retry.",
        )
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to read file: {str(e)}",
            error_code="FILE_READ_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=["Check file permissions"],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check file permissions and retry.",
        )

    await ctx.info(f"Loaded {file_path} for update")

    # --- Apply changes ----------------------------------------------------------

    if has_updates:
        result = await _apply_updates(ctx, file_path, yaml_data, updates, resolved_path)
    elif has_insert:
        result = await _apply_insert(
            ctx, file_path, yaml_data, insert_path, insert_value, resolved_path
        )
    else:
        result = await _apply_delete(
            ctx, file_path, yaml_data, delete_path, resolved_path
        )

    return result


async def _apply_updates(
    ctx: Context,
    file_path: str,
    yaml_data: Dict[str, Any],
    updates: Dict[str, Any],
    resolved_path,
) -> Dict[str, Any]:
    """Apply key-value updates to the YAML data and write back to file."""
    # Validate values before applying
    validation_errors = _validate_update_values(updates)
    if validation_errors:
        return create_error_response(
            error_message=f"Validation failed for {len(validation_errors)} field(s)",
            error_code="VALIDATION_FAILED",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Review the validation_errors for details",
                "Correct invalid values and retry",
            ],
            context={
                "file_path": file_path,
                "validation_errors": validation_errors,
            },
            next_steps="Fix validation errors and retry.",
        )

    updates_applied: Dict[str, Any] = {}
    is_replacements_config = file_path.endswith("replacements-config.yaml")

    for key, value in updates.items():
        old_value = _get_nested_value(yaml_data, key)

        # Handle replacements-config.yaml globalReplacements array
        if is_replacements_config and "globalReplacements" in yaml_data:
            found = False
            for item in yaml_data.get("globalReplacements", []):
                if isinstance(item, dict) and item.get("key") == key:
                    old_value = item.get("value")
                    item["value"] = value
                    found = True
                    break
            if not found:
                _set_nested_value(yaml_data, key, value)
        else:
            _set_nested_value(yaml_data, key, value)

        updates_applied[key] = {"old": old_value, "new": value}

    return await _write_yaml(
        ctx, file_path, yaml_data, resolved_path, updates_applied=updates_applied
    )


async def _apply_insert(
    ctx: Context,
    file_path: str,
    yaml_data: Dict[str, Any],
    insert_path: str,
    insert_value: Dict[str, Any],
    resolved_path,
) -> Dict[str, Any]:
    """Append insert_value to the list at insert_path and write back to file."""
    # Navigate to the target list
    target = _get_nested_value(yaml_data, insert_path)

    if target is None:
        # Target path doesn't exist — create it as an empty list
        _set_nested_value(yaml_data, insert_path, [])
        target = _get_nested_value(yaml_data, insert_path)

    if not isinstance(target, list):
        return create_error_response(
            error_message=f"insert_path '{insert_path}' does not point to a list",
            error_code="INSERT_TARGET_NOT_LIST",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                f"The value at '{insert_path}' is not a list (found {type(target).__name__})",
                "Verify the insert_path points to an array in the YAML file",
                "Use readLzaConfigFile() to inspect the file structure",
            ],
            context={"file_path": file_path, "insert_path": insert_path},
            next_steps="Verify insert_path points to a YAML list and retry.",
        )

    target.append(insert_value)

    return await _write_yaml(
        ctx,
        file_path,
        yaml_data,
        resolved_path,
        inserted={
            "path": insert_path,
            "value": insert_value,
            "new_index": len(target) - 1,
        },
    )


async def _apply_delete(
    ctx: Context,
    file_path: str,
    yaml_data: Dict[str, Any],
    delete_path: str,
    resolved_path,
) -> Dict[str, Any]:
    """Remove the key or list item at delete_path and write back to file."""
    parts = _parse_key_path(delete_path)

    if not parts:
        return create_error_response(
            error_message="delete_path cannot be empty",
            error_code="INVALID_DELETE_PATH",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Provide a valid dot-notation path to delete"],
            next_steps="Provide a valid delete_path and retry.",
        )

    # Navigate to the parent of the target
    parent: Any = yaml_data
    for part in parts[:-1]:
        if isinstance(parent, dict):
            parent = parent.get(part)
        elif isinstance(parent, list):
            try:
                parent = parent[part]
            except (IndexError, TypeError):
                parent = None
        else:
            parent = None

        if parent is None:
            return create_error_response(
                error_message=f"Path not found: '{delete_path}' (parent does not exist)",
                error_code="DELETE_PATH_NOT_FOUND",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    f"The path '{delete_path}' does not exist in the file",
                    "Use readLzaConfigFile() to inspect the file structure",
                ],
                context={"file_path": file_path, "delete_path": delete_path},
                next_steps="Verify the path exists and retry.",
            )

    target_key = parts[-1]
    old_value: Any = None

    if isinstance(parent, dict):
        if target_key not in parent:
            return create_error_response(
                error_message=f"Key not found: '{delete_path}'",
                error_code="DELETE_PATH_NOT_FOUND",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    f"The key '{target_key}' does not exist at the specified path",
                    "Use readLzaConfigFile() to inspect the file structure",
                ],
                context={"file_path": file_path, "delete_path": delete_path},
                next_steps="Verify the path exists and retry.",
            )
        old_value = parent[target_key]
        del parent[target_key]

    elif isinstance(parent, list):
        if not isinstance(target_key, int):
            return create_error_response(
                error_message=f"Cannot delete non-index key '{target_key}' from a list",
                error_code="INVALID_DELETE_PATH",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Use array index notation to delete list items (e.g., 'vpcs[2]')",
                ],
                context={"file_path": file_path, "delete_path": delete_path},
                next_steps="Use index notation for list items.",
            )
        if target_key < 0 or target_key >= len(parent):
            return create_error_response(
                error_message=f"Index {target_key} out of range (list has {len(parent)} items)",
                error_code="DELETE_INDEX_OUT_OF_RANGE",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    f"Valid indices are 0 to {len(parent) - 1}",
                    "Use readLzaConfigFile() to inspect the list contents",
                ],
                context={"file_path": file_path, "delete_path": delete_path},
                next_steps="Use a valid index and retry.",
            )
        old_value = parent.pop(target_key)

    else:
        return create_error_response(
            error_message=f"Cannot delete from path '{delete_path}' (parent is not a dict or list)",  # nosec B608 - error message, not SQL
            error_code="INVALID_DELETE_PATH",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "The parent of the target is not a dict or list",
                "Use readLzaConfigFile() to inspect the file structure",
            ],
            context={"file_path": file_path, "delete_path": delete_path},
            next_steps="Verify the path and retry.",
        )

    return await _write_yaml(
        ctx,
        file_path,
        yaml_data,
        resolved_path,
        deleted={"path": delete_path, "old_value": old_value},
    )


async def _write_yaml(
    ctx: Context,
    file_path: str,
    yaml_data: Dict[str, Any],
    resolved_path,
    updates_applied: Optional[Dict[str, Any]] = None,
    inserted: Optional[Dict[str, Any]] = None,
    deleted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Serialize data back to the original file format (YAML or JSON) and write to file."""
    try:
        # Preserve the original file format based on extension
        is_json = file_path.lower().endswith(".json")
        if is_json:
            updated_content = json.dumps(yaml_data, indent=4, sort_keys=False) + "\n"
        else:
            updated_content = yaml.dump(
                yaml_data, default_flow_style=False, sort_keys=False
            )
            is_valid, yaml_error = validate_yaml_syntax(updated_content)
            if not is_valid:
                return create_error_response(
                    error_message=f"Generated YAML is invalid: {yaml_error}",
                    error_code="YAML_GENERATION_ERROR",
                    category=ErrorCategory.CONFIGURATION,
                    troubleshooting=[
                        "The update produced invalid YAML",
                        "Try updating fewer fields at once",
                    ],
                    context={"file_path": file_path, "error": yaml_error},
                    next_steps="Try simpler updates or contact support.",
                )
    except (yaml.YAMLError, TypeError, ValueError) as e:
        return create_error_response(
            error_message=f"Failed to serialize file: {str(e)}",
            error_code="SERIALIZATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                "Check that all values are compatible types",
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Review values and retry.",
        )

    try:
        with open(resolved_path, "w") as f:
            f.write(updated_content)
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to write file: {str(e)}",
            error_code="FILE_WRITE_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check file permissions",
                "Ensure sufficient disk space",
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check permissions and disk space, then retry.",
        )

    await ctx.info(f"Successfully updated {file_path}")

    data: Dict[str, Any] = {
        "file_path": file_path,
        "validation_errors": [],
    }
    if updates_applied is not None:
        data["updates_applied"] = updates_applied
    if inserted is not None:
        data["inserted"] = inserted
    if deleted is not None:
        data["deleted"] = deleted

    next_steps = (
        f"Changes applied to {file_path}. "
        "Use readLzaConfigFile() to verify, make more changes, "
        "or call putLzaConfiguration() to upload and startDeployment() to deploy."
    )

    return create_success_response(data=data, next_steps=next_steps)
