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

"""Create LZA configuration files in the extracted configuration directory."""

import json
import logging
from typing import Any, Dict, Optional, Union

import yaml
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    LZA_CONFIG_BASE_PATH,
    categorize_uc_merge_error,
    create_error_response,
    create_success_response,
    format_file_size,
    validate_path_security,
)

logger = logging.getLogger(__name__)

# Supported file extensions and their serializers
SUPPORTED_EXTENSIONS = {
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


# Valid json_indent values: 2 spaces, 4 spaces, or tab character
VALID_JSON_INDENTS: Dict[Union[int, str], Union[int, str]] = {
    2: 2,
    4: 4,
    "tab": "\t",
}


def _get_file_format(file_path: str) -> Optional[str]:
    """Determine the file format from the file extension.

    Args:
        file_path: File path to check.

    Returns:
        Format string ("yaml" or "json"), or None if unsupported.
    """
    lower = file_path.lower()
    for ext, fmt in SUPPORTED_EXTENSIONS.items():
        if lower.endswith(ext):
            return fmt
    return None


def _serialize_content(
    content: Dict[str, Any], fmt: str, json_indent: Union[int, str] = 2
) -> str:
    """Serialize a dictionary to YAML or JSON string.

    Args:
        content: Dictionary to serialize.
        fmt: Format string ("yaml" or "json").
        json_indent: Indentation for JSON files. Accepts 2, 4, or "tab".
            Ignored for YAML files. Defaults to 2.

    Returns:
        Serialized string.

    Raises:
        yaml.YAMLError: If YAML serialization fails.
        TypeError: If JSON serialization fails.
    """
    if fmt == "json":
        indent = VALID_JSON_INDENTS.get(json_indent, 2)
        return json.dumps(content, indent=indent, sort_keys=False) + "\n"
    return yaml.dump(content, default_flow_style=False, sort_keys=False)


async def create_lza_config_file(
    ctx: Context,
    file_path: str,
    content: Dict[str, Any],
    overwrite: bool = False,
    json_indent: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """Create a new configuration file in the extracted LZA configuration directory.

    Creates YAML (.yaml, .yml) or JSON (.json) files based on the file extension.
    This is useful for adding new policy files, custom configuration files, or
    any additional files needed by the LZA configuration.

    Args:
        ctx: MCP context for logging.
        file_path: Relative path for the new file (e.g., "iam-policies/boundary-policy.json"
            or "custom-config.yaml"). The file extension determines the format.
        content: Dictionary representing the file content to write.
        overwrite: If True, overwrite an existing file. Defaults to False.
        json_indent: Indentation for JSON files. Accepts 2, 4, or "tab".
            Ignored for YAML files. Defaults to 2 if not specified.

    Returns:
        Dictionary with operation results:
        - success: bool
        - file_path: str
        - format: str ("yaml" or "json")
        - size_bytes: int
        - size_formatted: str
        - overwritten: bool

    Examples:
        # Create a JSON policy file
        await create_lza_config_file(
            ctx,
            file_path="iam-policies/boundary-policy.json",
            content={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": "*"
                    }
                ]
            }
        )

        # Create a YAML configuration file
        await create_lza_config_file(
            ctx,
            file_path="custom-rules/tagging-policy.yaml",
            content={
                "rules": [
                    {"name": "require-environment-tag", "enabled": True}
                ]
            }
        )

        # Create a JSON file with tab indentation
        await create_lza_config_file(
            ctx,
            file_path="policy.json",
            content={"Version": "2012-10-17"},
            json_indent="tab"
        )
    """
    logger.info(f"Creating LZA config file: {file_path}")

    # --- Parameter validation ---------------------------------------------------

    if not file_path:
        return create_error_response(
            error_message="File path is required",
            error_code="MISSING_FILE_PATH",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Provide a relative path for the new configuration file",
                "Example: 'iam-policies/boundary-policy.json' or 'custom-config.yaml'",
            ],
            next_steps="Provide a valid file_path and retry.",
        )

    if content is None:
        return create_error_response(
            error_message="Content is required",
            error_code="MISSING_CONTENT",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Provide a dictionary representing the file content",
                "Example: {'Version': '2012-10-17', 'Statement': [...]}",
            ],
            next_steps="Provide content and retry.",
        )

    if not isinstance(content, dict):
        return create_error_response(
            error_message="Content must be a dictionary",
            error_code="INVALID_CONTENT",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Content must be a dictionary (object), not a string or list",
                "Wrap list content in a dictionary key if needed",
            ],
            next_steps="Provide a valid dictionary for content.",
        )

    # --- Validate file format ---------------------------------------------------

    fmt = _get_file_format(file_path)
    if fmt is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
        return create_error_response(
            error_message=f"Unsupported file extension. Supported: {supported}",
            error_code="UNSUPPORTED_FORMAT",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                f"Use one of the supported extensions: {supported}",
                "YAML files: .yaml, .yml",
                "JSON files: .json",
            ],
            context={"file_path": file_path},
            next_steps=f"Rename the file to use a supported extension ({supported}).",
        )

    # --- Validate json_indent ---------------------------------------------------

    # Default to 2 if not specified
    if json_indent is None:
        json_indent = 2

    if fmt == "json" and json_indent not in VALID_JSON_INDENTS:
        valid_options = ", ".join(str(k) for k in VALID_JSON_INDENTS)
        return create_error_response(
            error_message=f"Invalid json_indent value: {json_indent!r}. Valid options: {valid_options}",
            error_code="INVALID_JSON_INDENT",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                f"json_indent must be one of: {valid_options}",
                "Use 2 or 4 for space indentation, or 'tab' for tab indentation",
            ],
            context={"json_indent": str(json_indent)},
            next_steps=f"Set json_indent to one of: {valid_options}.",
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
            next_steps="Call getLzaConfiguration() before creating files.",
        )

    is_valid, error_msg, resolved_path = validate_path_security(
        file_path, base_directory, "create"
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

    # --- Check for existing file ------------------------------------------------

    overwritten = False
    if resolved_path.exists():
        if resolved_path.is_dir():
            return create_error_response(
                error_message=f"Path is a directory, not a file: {file_path}",
                error_code="PATH_IS_DIRECTORY",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "The specified path already exists as a directory",
                    "Choose a different file path",
                ],
                context={"file_path": file_path},
                next_steps="Provide a file path that does not conflict with an existing directory.",
            )
        if not overwrite:
            return create_error_response(
                error_message=f"File already exists: {file_path}",
                error_code="FILE_EXISTS",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    f"The file '{file_path}' already exists",
                    "Set overwrite=True to replace the existing file",
                    "Or use updateLzaConfigFile() to modify the existing file",
                ],
                context={"file_path": file_path},
                next_steps="Set overwrite=True or use updateLzaConfigFile() instead.",
            )
        overwritten = True

    # --- Serialize content ------------------------------------------------------

    try:
        serialized = _serialize_content(content, fmt, json_indent)
    except (yaml.YAMLError, TypeError, ValueError) as e:
        return create_error_response(
            error_message=f"Failed to serialize content as {fmt.upper()}: {str(e)}",
            error_code="SERIALIZATION_ERROR",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                f"Content could not be serialized to {fmt.upper()}",
                "Ensure all values are serializable (no custom objects)",
                "Check for circular references in the content",
            ],
            context={"file_path": file_path, "format": fmt, "error": str(e)},
            next_steps="Fix the content and retry.",
        )

    # --- Create parent directories and write file --------------------------------

    try:
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to create parent directories: {str(e)}",
            error_code="DIRECTORY_CREATE_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check file system permissions",
                "Ensure sufficient disk space",
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check permissions and disk space, then retry.",
        )

    try:
        resolved_path.write_text(serialized, encoding="utf-8")
        size_bytes = resolved_path.stat().st_size
    except OSError as e:
        return create_error_response(
            error_message=f"Failed to write file: {str(e)}",
            error_code="FILE_WRITE_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check file system permissions",
                "Ensure sufficient disk space",
            ],
            context={"file_path": file_path, "error": str(e)},
            next_steps="Check permissions and disk space, then retry.",
        )

    action = "Overwrote" if overwritten else "Created"
    await ctx.info(
        f"{action} {file_path} ({format_file_size(size_bytes)}, {fmt.upper()})"
    )

    next_steps = (
        f"File '{file_path}' has been {'overwritten' if overwritten else 'created'}. "
        "Use readLzaConfigFile() to verify the content, "
        "or call putLzaConfiguration() to upload and startDeployment() to deploy."
    )

    return create_success_response(
        data={
            "file_path": file_path,
            "format": fmt,
            "size_bytes": size_bytes,
            "size_formatted": format_file_size(size_bytes),
            "overwritten": overwritten,
        },
        next_steps=next_steps,
    )
