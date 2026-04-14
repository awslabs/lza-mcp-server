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

"""Read UC configuration files from session directory."""

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
)
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


def get_next_steps_for_uc_file(file_name: str) -> str:
    """Get context-aware next steps based on UC filename.

    Args:
        file_name: Name of the file that was read

    Returns:
        Context-aware next steps guidance
    """
    file_name_lower = file_name.lower()

    if "accounts-config" in file_name_lower:
        return (
            "Parse the YAML and identify which account emails need updating. "
            "Use the mandatory account emails you extracted from LZA accounts-config.yaml "
            "(Management, LogArchive, Audit) and keep them unchanged. "
            "For workload accounts, ask the user to provide email addresses."
        )
    elif "replacements-config" in file_name_lower:
        return (
            "Parse the YAML and identify settings that need customization. "
            "Use the homeRegion you extracted from LZA global-config.yaml to update HomeRegion. "
            "For network settings, present the current values to the user and ask if they want to customize them: "
            "  - CIDR ranges"
            "  - VPC mask lengths"
            "  - Transit Gateway ASN"
            "For email addresses, ask the user to provide values."
        )
    elif "global-config" in file_name_lower:
        return "Review global settings and update as needed for your organization."
    elif "network-config" in file_name_lower:
        return "Review network configuration and customize CIDR ranges if needed."
    elif "iam-config" in file_name_lower:
        return "Review IAM configuration and customize roles/policies as needed."
    elif "security-config" in file_name_lower:
        return "Review security configuration and adjust security controls as needed."
    elif "organization-config" in file_name_lower:
        return "Review organization structure and adjust OUs as needed."
    else:
        return (
            "Review the file content. Use update_uc_file() to make changes, "
            "or read additional files to continue customization."
        )


async def read_uc_file(ctx: Context, session_id: str, file_path: str) -> Dict[str, Any]:
    """Read a file from the UC session directory.

    This tool reads files from the UC session directory created by
    start_uc_merge_session(). It validates paths for security and provides
    context-aware guidance based on the file being read.

    For UC merge workflow, review at minimum:
    - accounts-config.yaml: Account structure and emails
    - replacements-config.yaml: Network settings and global replacements

    Args:
        ctx: MCP context for logging
        session_id: Session identifier from start_uc_merge_session()
        file_path: Relative path within UC session (e.g., "accounts-config.yaml")

    Returns:
        Dictionary with file content and metadata:
        {
            "success": bool,
            "session_id": str,
            "file_path": str,
            "content": str,
            "size_bytes": int,
            "size_formatted": str,
            "next_steps": str
        }
    """
    try:
        await ctx.info(f"Reading UC file from session {session_id}: {file_path}")

        # Validate session_id is provided
        if not session_id:
            return create_error_response(
                error_message="Session ID is required",
                error_code="MISSING_SESSION_ID",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Provide a session_id parameter",
                    "Start a new session with start_uc_merge_session()",
                    "Ensure you have the session_id from the session creation response",
                ],
                next_steps="Call start_uc_merge_session() to create a session first.",
            )

        # Validate session exists
        session_manager = SessionManager()
        is_valid, error_message = session_manager.validate_session(session_id)

        if not is_valid:
            return create_error_response(
                error_message=error_message,
                error_code="INVALID_SESSION",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Verify the session_id is correct",
                    "Start a new session with start_uc_merge_session()",
                    "Check that the session has not been cleaned up",
                    "Ensure the session was created successfully",
                ],
                next_steps="Start a new session with start_uc_merge_session() and use the returned session_id.",
            )

        # Get session directory
        session_path = session_manager.get_session_path(session_id)

        # Validate path security
        is_valid, error_message, resolved_path = validate_path_security(
            file_path, session_path, operation="read"
        )

        if not is_valid:
            error_info = categorize_uc_merge_error(Exception(error_message))
            return create_error_response(
                error_message=error_message,
                error_code=error_info["error_code"],
                category=error_info["category"],
                troubleshooting=error_info["troubleshooting"],
                next_steps="Provide a valid relative path within the session directory.",
            )

        # Check if file exists
        if not resolved_path.exists():
            return create_error_response(
                error_message="File not found in session directory",
                error_code="FILE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify the file path is correct",
                    "Check that the file exists in the UC session directory",
                    "Use get_uc_network_customization_guide() to see available files",
                    "Ensure the session was created successfully with all files copied",
                ],
                next_steps="Verify the file path and retry the operation.",
            )

        # Check if it's a file (not a directory)
        if not resolved_path.is_file():
            return create_error_response(
                error_message="Path is not a file",
                error_code="NOT_A_FILE",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "The path points to a directory, not a file",
                    "Provide a path to a specific file",
                    "Use a file path like 'accounts-config.yaml' instead of a directory",
                ],
                next_steps="Provide a path to a file, not a directory.",
            )

        # Read file content
        try:
            content = resolved_path.read_text(encoding="utf-8")
            size_bytes = resolved_path.stat().st_size

            await ctx.info(
                f"Successfully read {file_path} from session {session_id} "
                f"({format_file_size(size_bytes)})"
            )

            # Get context-aware next steps
            next_steps = get_next_steps_for_uc_file(resolved_path.name)

            return create_success_response(
                data={
                    "session_id": session_id,
                    "file_path": file_path,
                    "content": content,
                    "size_bytes": size_bytes,
                    "size_formatted": format_file_size(size_bytes),
                },
                next_steps=next_steps,
            )

        except UnicodeDecodeError:
            return create_error_response(
                error_message="Failed to decode file as UTF-8",
                error_code="ENCODING_ERROR",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "File may not be a text file or uses a different encoding",
                    "Verify the file is a valid YAML or text configuration file",
                    "Check if the file is corrupted",
                    "Ensure the file was copied correctly to the session",
                ],
                next_steps="Verify the file is a valid text file and retry.",
            )
        except PermissionError:
            return create_error_response(
                error_message="Permission denied reading file",
                error_code="ACCESS_DENIED",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "Check file system permissions",
                    "Ensure the user has read access to the file",
                    "Verify the file is not locked by another process",
                    "Check container permissions and volume mounts",
                ],
                next_steps="Check file permissions and retry.",
            )
        except Exception as e:
            error_info = categorize_uc_merge_error(e)
            return create_error_response(
                error_message=f"Failed to read file: {type(e).__name__}",
                error_code=error_info["error_code"],
                category=error_info["category"],
                troubleshooting=error_info["troubleshooting"],
                next_steps="Check the error details and retry the operation.",
            )

    except Exception as e:
        logger.error(f"Unexpected error reading UC file: {str(e)}")
        return create_error_response(
            error_message="Unexpected error reading file",
            error_code="UNEXPECTED_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check system logs for more details",
                "Verify the session directory is accessible",
                "Ensure sufficient system resources",
                "Try creating a new session",
            ],
            next_steps="Review the error and retry the operation.",
        )
