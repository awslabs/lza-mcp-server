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

"""
Comprehensive input validation and sanitization utilities.

This module provides centralized input validation to prevent injection attacks
and ensure data integrity across all MCP tools.

Security Mitigation: T-008 - Comprehensive input sanitization
"""

import re
from pathlib import Path
from typing import Tuple, Any, Optional, List
from urllib.parse import urlparse


def validate_string_input(
    value: Any,
    field_name: str,
    min_length: int = 1,
    max_length: int = 1000,
    allow_empty: bool = False,
    pattern: Optional[str] = None,
) -> Tuple[bool, str]:
    """Validate generic string input with length and pattern constraints.
    
    Args:
        value: Input value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed
        pattern: Optional regex pattern to match
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        if allow_empty:
            return True, ""
        return False, f"{field_name} cannot be None"
    
    if not isinstance(value, str):
        return False, f"{field_name} must be a string, got {type(value).__name__}"
    
    if len(value) == 0:
        if not allow_empty:
            return False, f"{field_name} cannot be empty"
        # If empty is allowed and string is empty, skip other validations
        return True, ""
    
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    
    if len(value) > max_length:
        return False, f"{field_name} exceeds maximum length of {max_length} characters"
    
    if pattern and not re.match(pattern, value):
        return False, f"{field_name} does not match required format"
    
    return True, ""


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input by removing potentially dangerous characters.
    
    Args:
        value: String to sanitize
        max_length: Maximum length to truncate to
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)
    
    # Remove null bytes
    sanitized = value.replace('\x00', '')
    
    # Remove control characters except newline, tab, and carriage return
    sanitized = ''.join(char for char in sanitized 
                       if char in '\n\r\t' or not (0 <= ord(char) < 32))
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_s3_bucket_name(bucket_name: str) -> Tuple[bool, str]:
    """Validate S3 bucket name according to AWS naming rules.
    
    Args:
        bucket_name: S3 bucket name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not bucket_name:
        return False, "S3 bucket name cannot be empty"
    
    if not isinstance(bucket_name, str):
        return False, "S3 bucket name must be a string"
    
    # AWS S3 bucket naming rules:
    # - 3-63 characters
    # - Lowercase letters, numbers, hyphens, and periods
    # - Must start and end with letter or number
    # - Cannot contain consecutive periods
    # - Cannot be formatted as IP address
    
    if len(bucket_name) < 3:
        return False, "S3 bucket name must be at least 3 characters"
    
    if len(bucket_name) > 63:
        return False, f"S3 bucket name exceeds maximum length of 63 characters (got {len(bucket_name)})"
    
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket_name):
        return False, "S3 bucket name must start and end with lowercase letter or number, and contain only lowercase letters, numbers, hyphens, and periods"
    
    if '..' in bucket_name:
        return False, "S3 bucket name cannot contain consecutive periods"
    
    # Check if formatted as IP address
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', bucket_name):
        return False, "S3 bucket name cannot be formatted as IP address"
    
    return True, ""


def validate_s3_key(key: str) -> Tuple[bool, str]:
    """Validate S3 object key.
    
    Args:
        key: S3 object key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "S3 object key cannot be empty"
    
    if not isinstance(key, str):
        return False, "S3 object key must be a string"
    
    # S3 key can be up to 1024 bytes
    if len(key.encode('utf-8')) > 1024:
        return False, "S3 object key exceeds maximum size of 1024 bytes"
    
    # Check for path traversal attempts
    if '..' in key:
        return False, "S3 object key cannot contain '..' (path traversal)"
    
    # Disallow absolute paths
    if key.startswith('/'):
        return False, "S3 object key cannot start with '/'"
    
    return True, ""


def validate_file_path(
    file_path: str,
    base_directory: Optional[Path] = None,
    allow_absolute: bool = False,
) -> Tuple[bool, str]:
    """Validate file path for security (prevent path traversal).
    
    Args:
        file_path: File path to validate
        base_directory: Base directory to restrict access to
        allow_absolute: Whether to allow absolute paths
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path cannot be empty"
    
    if not isinstance(file_path, str):
        return False, "File path must be a string"
    
    # Remove null bytes
    if '\x00' in file_path:
        return False, "File path contains null bytes"
    
    # Check for path traversal
    if '..' in file_path:
        return False, "File path cannot contain '..' (path traversal attempt)"
    
    # Check for absolute paths if not allowed
    if not allow_absolute and (file_path.startswith('/') or (len(file_path) > 1 and file_path[1] == ':')):
        return False, "Absolute paths are not allowed"
    
    # If base directory provided, ensure path is within it
    if base_directory:
        try:
            base_path = Path(base_directory).resolve()
            full_path = (base_path / file_path).resolve()
            
            # Check if resolved path is within base directory
            if not str(full_path).startswith(str(base_path)):
                return False, f"File path escapes base directory: {base_directory}"
        except (ValueError, OSError) as e:
            return False, f"Invalid file path: {str(e)}"
    
    return True, ""


def validate_session_id(session_id: str) -> Tuple[bool, str]:
    """Validate session ID format.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id:
        return False, "Session ID cannot be empty"
    
    if not isinstance(session_id, str):
        return False, "Session ID must be a string"
    
    # Session ID format: uc-session-YYYYMMDD-HHMMSS
    session_pattern = r'^uc-session-\d{8}-\d{6}$'
    
    if not re.match(session_pattern, session_id):
        return False, "Invalid session ID format. Expected: uc-session-YYYYMMDD-HHMMSS"
    
    return True, ""


def validate_lza_version(version: str) -> Tuple[bool, str]:
    """Validate LZA version format.
    
    Args:
        version: LZA version string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not version:
        return False, "LZA version cannot be empty"
    
    if not isinstance(version, str):
        return False, "LZA version must be a string"
    
    # LZA version format: vX.Y.Z or X.Y.Z
    version_pattern = r'^v?\d+\.\d+\.\d+$'
    
    if not re.match(version_pattern, version):
        return False, "Invalid LZA version format. Expected: vX.Y.Z or X.Y.Z (e.g., v1.9.2)"
    
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email address cannot be empty"
    
    if not isinstance(email, str):
        return False, "Email address must be a string"
    
    # Basic email validation pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email address format"
    
    if len(email) > 254:  # RFC 5321
        return False, "Email address exceeds maximum length of 254 characters"
    
    return True, ""


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> Tuple[bool, str]:
    """Validate URL format and scheme.
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https', 's3'])
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    if not isinstance(url, str):
        return False, "URL must be a string"
    
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https', 's3']
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return False, "URL must include a scheme (e.g., https://)"
        
        if parsed.scheme not in allowed_schemes:
            return False, f"URL scheme '{parsed.scheme}' not allowed. Allowed schemes: {', '.join(allowed_schemes)}"
        
        if not parsed.netloc and parsed.scheme != 's3':
            return False, "URL must include a domain/host"
        
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    return True, ""


def validate_integer_range(
    value: Any,
    field_name: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> Tuple[bool, str]:
    """Validate integer input with range constraints.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, int):
        return False, f"{field_name} must be an integer, got {type(value).__name__}"
    
    if min_value is not None and value < min_value:
        return False, f"{field_name} must be at least {min_value}, got {value}"
    
    if max_value is not None and value > max_value:
        return False, f"{field_name} must be at most {max_value}, got {value}"
    
    return True, ""


def validate_dict_input(
    value: Any,
    field_name: str,
    required_keys: Optional[List[str]] = None,
    max_depth: int = 10,
) -> Tuple[bool, str]:
    """Validate dictionary input.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        required_keys: List of required keys
        max_depth: Maximum nesting depth allowed
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, dict):
        return False, f"{field_name} must be a dictionary, got {type(value).__name__}"
    
    if required_keys:
        missing_keys = [key for key in required_keys if key not in value]
        if missing_keys:
            return False, f"{field_name} missing required keys: {', '.join(missing_keys)}"
    
    # Check nesting depth
    def check_depth(obj, current_depth=0):
        if current_depth > max_depth:
            return False
        if isinstance(obj, dict):
            return all(check_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            return all(check_depth(item, current_depth + 1) for item in obj)
        return True
    
    if not check_depth(value):
        return False, f"{field_name} exceeds maximum nesting depth of {max_depth}"
    
    return True, ""


def sanitize_command_argument(arg: str) -> str:
    """Sanitize command-line argument to prevent injection.
    
    Args:
        arg: Command argument to sanitize
        
    Returns:
        Sanitized argument
    """
    if not isinstance(arg, str):
        arg = str(arg)
    
    # Remove shell metacharacters
    dangerous_chars = ['|', '&', ';', '$', '`', '\n', '\r', '(', ')', '<', '>', '\\']
    
    for char in dangerous_chars:
        arg = arg.replace(char, '')
    
    return arg


def validate_json_schema_path(schema_path: str) -> Tuple[bool, str]:
    """Validate JSON schema path format.
    
    Args:
        schema_path: Schema path to validate (e.g., "accounts-config.json" or "accounts-config")
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not schema_path:
        return False, "Schema path cannot be empty"
    
    if not isinstance(schema_path, str):
        return False, "Schema path must be a string"
    
    # Schema paths should be alphanumeric with hyphens, optionally ending with .json
    if not re.match(r'^[a-z0-9-]+(?:\.json)?$', schema_path):
        return False, "Schema path must contain only lowercase letters, numbers, hyphens, and optionally end with .json"
    
    if len(schema_path) > 100:
        return False, "Schema path exceeds maximum length of 100 characters"
    
    return True, ""


def validate_account_id(account_id: str) -> Tuple[bool, str]:
    """Validate AWS account ID format.
    
    Args:
        account_id: AWS account ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not account_id:
        return False, "AWS account ID cannot be empty"
    
    if not isinstance(account_id, str):
        return False, "AWS account ID must be a string"
    
    # AWS account IDs are exactly 12 digits
    if not re.match(r'^\d{12}$', account_id):
        return False, "AWS account ID must be exactly 12 digits"
    
    return True, ""


def validate_pipeline_name(pipeline_name: str) -> Tuple[bool, str]:
    """Validate AWS CodePipeline name format.
    
    Args:
        pipeline_name: Pipeline name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not pipeline_name:
        return False, "Pipeline name cannot be empty"
    
    if not isinstance(pipeline_name, str):
        return False, "Pipeline name must be a string"
    
    # AWS CodePipeline naming rules:
    # - 1-100 characters
    # - Letters, numbers, periods, underscores, and hyphens
    # - Cannot contain spaces
    
    if len(pipeline_name) < 1:
        return False, "Pipeline name must be at least 1 character"
    
    if len(pipeline_name) > 100:
        return False, f"Pipeline name exceeds maximum length of 100 characters (got {len(pipeline_name)})"
    
    if not re.match(r'^[A-Za-z0-9._-]+$', pipeline_name):
        return False, "Pipeline name can only contain letters, numbers, periods, underscores, and hyphens"
    
    return True, ""


def validate_execution_id(execution_id: str) -> Tuple[bool, str]:
    """Validate AWS CodePipeline execution ID format.
    
    Args:
        execution_id: Execution ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not execution_id:
        return False, "Execution ID cannot be empty"
    
    if not isinstance(execution_id, str):
        return False, "Execution ID must be a string"
    
    # AWS execution IDs are UUIDs (36 characters with hyphens)
    # Format: 12345678-1234-1234-1234-123456789012
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    
    if not re.match(uuid_pattern, execution_id):
        return False, "Execution ID must be a valid UUID format (e.g., 12345678-1234-1234-1234-123456789012)"
    
    return True, ""


# Validation registry for easy lookup
VALIDATORS = {
    'string': validate_string_input,
    's3_bucket': validate_s3_bucket_name,
    's3_key': validate_s3_key,
    'file_path': validate_file_path,
    'session_id': validate_session_id,
    'lza_version': validate_lza_version,
    'email': validate_email,
    'url': validate_url,
    'integer_range': validate_integer_range,
    'dict': validate_dict_input,
    'schema_path': validate_json_schema_path,
    'account_id': validate_account_id,
    'pipeline_name': validate_pipeline_name,
    'execution_id': validate_execution_id,
}
