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

"""Shared utilities for UC merge tools."""

import os
from pathlib import Path
from typing import Dict, Any, Tuple

from awslabs.lza_mcp_server.error_categories import ErrorCategory


# Default paths
_DEFAULT_UC_BASE_PATH = "/app/lza-uc"
_DEFAULT_LZA_CONFIG_BASE_PATH = "/app/lza-config"
DEFAULT_UC_RELEASE = "v1.0.0"


def get_uc_base_path() -> Path:
    """Get UC base path from environment or use default.

    Returns:
        Path to UC repository base directory
    """
    return Path(os.environ.get("LZA_UC_BASE_PATH", _DEFAULT_UC_BASE_PATH))


def get_lza_config_base_path() -> Path:
    """Get LZA config base path from environment or use default.

    Returns:
        Path to LZA configuration base directory
    """
    return Path(os.environ.get("LZA_CONFIG_BASE_PATH", _DEFAULT_LZA_CONFIG_BASE_PATH))


# For backward compatibility, keep these as module-level variables
# but they will be stale if environment changes after import
UC_BASE_PATH = get_uc_base_path()
LZA_CONFIG_BASE_PATH = get_lza_config_base_path()

# Module-level variable to store extracted LZA config path
_extracted_lza_config_path: Path | None = None


def set_extracted_lza_config_path(path: Path) -> None:
    """Set the extracted LZA configuration path.

    This should be called after getConfigurationFromS3 completes.

    Args:
        path: Path to extracted LZA configuration directory
    """
    global _extracted_lza_config_path
    _extracted_lza_config_path = path


def get_extracted_lza_config_path() -> Path | None:
    """Get the extracted LZA configuration path.

    Returns:
        Path to extracted LZA configuration, or None if not set
    """
    return _extracted_lza_config_path


def validate_path_security(
    file_path: str, base_directory: Path, operation: str = "access"
) -> Tuple[bool, str, Path | None]:
    """Validate file path for security concerns.

    Checks for:
    - Path traversal attempts (..)
    - Absolute paths
    - Paths outside base directory boundary

    Args:
        file_path: File path to validate
        base_directory: Base directory that path must be within
        operation: Operation being performed (for error messages)

    Returns:
        Tuple of (is_valid, error_message, resolved_path)
    """
    if not file_path:
        return False, "File path cannot be empty", None

    if not isinstance(file_path, str):
        return False, "File path must be a string", None

    # Check for path traversal sequences
    if ".." in file_path:
        return (False, f"Path traversal detected in file path: {file_path}", None)

    # Check for absolute paths
    path_obj = Path(file_path)
    if path_obj.is_absolute():
        return (False, f"Absolute paths are not allowed: {file_path}", None)

    # Resolve the full path
    try:
        resolved_path = (base_directory / file_path).resolve()
    except (OSError, ValueError) as e:
        return (False, f"Invalid file path: {str(e)}", None)

    # Verify the resolved path is within the base directory
    try:
        resolved_path.relative_to(base_directory.resolve())
    except ValueError:
        return (False, f"Path is outside allowed directory boundary: {file_path}", None)

    return True, "", resolved_path


def create_error_response(
    error_message: str,
    error_code: str,
    category: str,
    troubleshooting: list[str],
    context: Dict[str, Any] | None = None,
    next_steps: str = "",
) -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_message: Human-readable error message
        error_code: Machine-readable error code
        category: Error category (string value from ErrorCategory)
        troubleshooting: List of troubleshooting steps
        context: Optional context information
        next_steps: Optional next steps guidance

    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": error_message,
        "error_code": error_code,
        "category": category,
        "troubleshooting": troubleshooting,
    }

    if context:
        response["context"] = context

    if next_steps:
        response["next_steps"] = next_steps

    return response


def create_success_response(
    data: Dict[str, Any], next_steps: str = ""
) -> Dict[str, Any]:
    """Create a standardized success response.

    Args:
        data: Response data
        next_steps: Next steps guidance

    Returns:
        Standardized success response dictionary
    """
    response = {"success": True, **data}

    if next_steps:
        response["next_steps"] = next_steps

    return response


def categorize_uc_merge_error(error: Exception) -> Dict[str, Any]:
    """Categorize UC merge-related errors and provide specific guidance.

    Args:
        error: Exception to categorize

    Returns:
        Dictionary with error category and troubleshooting steps
    """
    error_str = str(error).lower()

    if "path traversal" in error_str or ".." in error_str:
        return {
            "category": ErrorCategory.SECURITY,
            "error_code": "PATH_TRAVERSAL",
            "troubleshooting": [
                "Path traversal attempt detected",
                "Use relative paths without '..' sequences",
                "Ensure path is within the designated directory",
                "Verify the file path does not attempt to access parent directories",
            ],
        }

    elif "absolute" in error_str and "not allowed" in error_str:
        return {
            "category": ErrorCategory.SECURITY,
            "error_code": "BOUNDARY_VIOLATION",
            "troubleshooting": [
                "Absolute paths are not allowed",
                "Use relative paths within the session or configuration directory",
                "Remove leading '/' from the file path",
                "Ensure the file path is relative to the base directory",
            ],
        }

    elif "outside" in error_str and "boundary" in error_str:
        return {
            "category": ErrorCategory.SECURITY,
            "error_code": "BOUNDARY_VIOLATION",
            "troubleshooting": [
                "Path is outside allowed directory boundary",
                "Ensure the file path is within the session or configuration directory",
                "Use relative paths that stay within the allowed directory",
                "Verify the resolved path does not escape the base directory",
            ],
        }

    elif "not found" in error_str or "does not exist" in error_str:
        return {
            "category": ErrorCategory.FILE_NOT_FOUND,
            "error_code": "FILE_NOT_FOUND",
            "troubleshooting": [
                "File or directory not found",
                "Verify the file path is correct",
                "Check that the file exists in the expected location",
                "Ensure the session was created successfully",
                "For LZA files, ensure getConfigurationFromS3() was called first",
            ],
        }

    elif "session" in error_str:
        return {
            "category": ErrorCategory.VALIDATION,
            "error_code": "INVALID_SESSION",
            "troubleshooting": [
                "Invalid or missing session",
                "Start a new session with start_uc_merge_session()",
                "Verify the session_id is correct",
                "Check that the session has not been cleaned up",
            ],
        }

    elif "yaml" in error_str or "parse" in error_str:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "YAML_PARSE_ERROR",
            "troubleshooting": [
                "YAML parsing error",
                "Check YAML syntax in the file",
                "Ensure proper indentation and formatting",
                "Verify there are no syntax errors in the YAML content",
                "Use a YAML validator to check file syntax",
            ],
        }

    elif "permission" in error_str or "access" in error_str:
        return {
            "category": ErrorCategory.FILE_OPERATION,
            "error_code": "ACCESS_DENIED",
            "troubleshooting": [
                "Permission denied accessing file or directory",
                "Check file system permissions",
                "Ensure the user has appropriate access rights",
                "Verify the file is not locked by another process",
            ],
        }

    else:
        return {
            "category": ErrorCategory.FILE_OPERATION,
            "error_code": "FILE_OPERATION_ERROR",
            "troubleshooting": [
                "File operation failed",
                "Check file system permissions and disk space",
                "Verify the file path is valid",
                "Ensure the operation is supported for this file type",
                "Check system logs for more details",
            ],
        }


def get_uc_release_path(uc_release: str = DEFAULT_UC_RELEASE) -> Path:
    """Get the path to a UC release directory.

    Args:
        uc_release: UC release version (default: v1.0.0)

    Returns:
        Path to UC release directory
    """
    return get_uc_base_path() / uc_release


def get_uc_network_model_path(uc_release: str, network_model: str) -> Path:
    """Get the path to a UC network model directory.

    Args:
        uc_release: UC release version
        network_model: Network model name

    Returns:
        Path to UC network model directory
    """
    return get_uc_release_path(uc_release) / network_model


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    size_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} TB"
