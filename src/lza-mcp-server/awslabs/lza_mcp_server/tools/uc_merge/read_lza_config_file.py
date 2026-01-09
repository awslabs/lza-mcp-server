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

"""Read LZA configuration files from extracted S3 configuration."""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from .common import (
    validate_path_security,
    create_error_response,
    create_success_response,
    categorize_uc_merge_error,
    format_file_size,
    LZA_CONFIG_BASE_PATH,
)

logger = logging.getLogger(__name__)


def get_next_steps_for_file(file_name: str) -> str:
    """Get context-aware next steps based on filename.

    Args:
        file_name: Name of the file that was read

    Returns:
        Context-aware next steps guidance
    """
    file_name_lower = file_name.lower()

    if "accounts-config" in file_name_lower:
        return (
            "Parse the YAML content and extract the mandatory account emails "
            "(Management, LogArchive, Audit) from the mandatoryAccounts section. "
            "Store these values - you will need them to update UC accounts-config.yaml. "
            "Verify workloadAccounts is empty or contains an empty array."
        )
    elif "global-config" in file_name_lower:
        return (
            "Parse the YAML content and extract the homeRegion value. "
            "Store this value - you will need it to update UC replacements-config.yaml "
            "and global-config.yaml."
        )
    elif "network-config" in file_name_lower:
        return "Verify minimal configuration (empty transitGateways, vpcs, endpointPolicies arrays)."
    elif "iam-config" in file_name_lower:
        return (
            "Verify minimal configuration (empty providers, policySets, roleSets, "
            "groupSets, userSets arrays)."
        )
    else:
        return "Review the file content and proceed with validation or customization as needed."


async def read_lza_config_file(ctx: Context, file_path: str) -> Dict[str, Any]:
    """Read a configuration file from the extracted LZA configuration.

    This tool reads files from the LZA configuration directory that was
    extracted via getConfigurationFromS3(). It validates paths for security
    and provides context-aware guidance based on the file being read.

    Common files to review:
    - accounts-config.yaml: Account structure and emails
    - global-config.yaml: Global settings including homeRegion
    - network-config.yaml: Network configuration
    - iam-config.yaml: IAM configuration

    Args:
        ctx: MCP context for logging
        file_path: Relative path to file (e.g., "accounts-config.yaml")

    Returns:
        Dictionary with file content and metadata:
        {
            "success": bool,
            "file_path": str,
            "content": str,
            "size_bytes": int,
            "size_formatted": str,
            "next_steps": str
        }
    """
    try:
        await ctx.info(f"Reading LZA config file: {file_path}")

        # Use the standard extracted config path
        # This matches what getConfigurationFromS3 uses
        base_directory = LZA_CONFIG_BASE_PATH / "retrieved-config"

        # Check if the base directory exists
        if not base_directory.exists():
            return create_error_response(
                error_message=(
                    "LZA configuration directory not found. "
                    "Call getConfigurationFromS3() first to retrieve the configuration."
                ),
                error_code="CONFIG_NOT_RETRIEVED",
                category=ErrorCategory.CONFIGURATION,
                troubleshooting=[
                    "Call getConfigurationFromS3() to retrieve the LZA configuration",
                    "Verify the configuration was extracted successfully",
                    "Check that the configuration directory exists at /app/lza-config/retrieved-config",
                    "Ensure getConfigurationFromS3() completed without errors",
                ],
                context={
                    "expected_directory": str(base_directory),
                    "file_path": file_path,
                },
                next_steps="Call getConfigurationFromS3() to retrieve the LZA configuration before reading files.",
            )

        # Validate path security
        is_valid, error_message, resolved_path = validate_path_security(
            file_path, base_directory, operation="read"
        )

        if not is_valid:
            error_info = categorize_uc_merge_error(Exception(error_message))
            return create_error_response(
                error_message=error_message,
                error_code=error_info["error_code"],
                category=error_info["category"],
                troubleshooting=error_info["troubleshooting"],
                context={"file_path": file_path, "base_directory": str(base_directory)},
                next_steps="Provide a valid relative path within the configuration directory.",
            )

        # Check if file exists
        if not resolved_path.exists():
            return create_error_response(
                error_message=f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    f"Verify the file path is correct: {file_path}",
                    "Check that the file exists in the extracted configuration",
                    "List available files in the configuration directory",
                    "Ensure getConfigurationFromS3() extracted all files successfully",
                ],
                context={
                    "file_path": file_path,
                    "resolved_path": str(resolved_path),
                    "base_directory": str(base_directory),
                },
                next_steps="Verify the file path and retry the operation.",
            )

        # Check if it's a file (not a directory)
        if not resolved_path.is_file():
            return create_error_response(
                error_message=f"Path is not a file: {file_path}",
                error_code="NOT_A_FILE",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    f"The path points to a directory, not a file: {file_path}",
                    "Provide a path to a specific file",
                    "Use a file path like 'accounts-config.yaml' instead of a directory",
                ],
                context={"file_path": file_path, "resolved_path": str(resolved_path)},
                next_steps="Provide a path to a file, not a directory.",
            )

        # Read file content
        try:
            content = resolved_path.read_text(encoding="utf-8")
            size_bytes = resolved_path.stat().st_size

            await ctx.info(
                f"Successfully read {file_path} ({format_file_size(size_bytes)})"
            )

            # Get context-aware next steps
            next_steps = get_next_steps_for_file(resolved_path.name)

            return create_success_response(
                data={
                    "file_path": file_path,
                    "content": content,
                    "size_bytes": size_bytes,
                    "size_formatted": format_file_size(size_bytes),
                },
                next_steps=next_steps,
            )

        except UnicodeDecodeError as e:
            return create_error_response(
                error_message=f"Failed to decode file as UTF-8: {str(e)}",
                error_code="ENCODING_ERROR",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "File may not be a text file or uses a different encoding",
                    "Verify the file is a valid YAML or text configuration file",
                    "Check if the file is corrupted",
                    "Ensure the file was extracted correctly from S3",
                ],
                context={"file_path": file_path, "error": str(e)},
                next_steps="Verify the file is a valid text file and retry.",
            )
        except PermissionError as e:
            return create_error_response(
                error_message=f"Permission denied reading file: {str(e)}",
                error_code="ACCESS_DENIED",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "Check file system permissions",
                    "Ensure the user has read access to the file",
                    "Verify the file is not locked by another process",
                    "Check container permissions and volume mounts",
                ],
                context={"file_path": file_path, "resolved_path": str(resolved_path)},
                next_steps="Check file permissions and retry.",
            )
        except Exception as e:
            error_info = categorize_uc_merge_error(e)
            return create_error_response(
                error_message=f"Failed to read file: {str(e)}",
                error_code=error_info["error_code"],
                category=error_info["category"],
                troubleshooting=error_info["troubleshooting"],
                context={
                    "file_path": file_path,
                    "resolved_path": str(resolved_path),
                    "error_type": type(e).__name__,
                },
                next_steps="Check the error details and retry the operation.",
            )

    except Exception as e:
        logger.error(f"Unexpected error reading LZA config file: {str(e)}")
        return create_error_response(
            error_message=f"Unexpected error reading file: {str(e)}",
            error_code="UNEXPECTED_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check system logs for more details",
                "Verify the configuration directory is accessible",
                "Ensure sufficient system resources",
                "Try calling getConfigurationFromS3() again",
            ],
            context={"file_path": file_path, "error_type": type(e).__name__},
            next_steps="Review the error and retry the operation.",
        )
