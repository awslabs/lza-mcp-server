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

"""Copy UC configuration from UC workspace to LZA workspace."""

import logging
import posixpath
from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)
from .common import (
    create_error_response,
    create_success_response,
    categorize_uc_merge_error,
)

logger = logging.getLogger(__name__)


async def copy_uc_to_lza_config(
    ctx: Context,
    uc_workspace_id: str,
    lza_workspace_id: str,
    workspace_manager: WorkspaceManager,
    path: str = "",
) -> Dict[str, Any]:
    """Copy UC configuration from UC workspace to LZA workspace.

    Reads all files from the UC workspace and writes them to the LZA workspace,
    preserving directory structure. Skips .session_metadata.json. Supports an
    optional path prefix for the LZA workspace destination.

    Args:
        ctx: MCP context for logging
        uc_workspace_id: Workspace ID containing UC configuration
        lza_workspace_id: Workspace ID containing LZA configuration
        workspace_manager: WorkspaceManager instance for file operations
        path: Optional path prefix for LZA workspace destination

    Returns:
        Dictionary with copy operation results
    """
    try:
        await ctx.info(
            f"Copying UC configuration from workspace {uc_workspace_id} "
            f"to LZA workspace {lza_workspace_id}"
        )

        # Validate uc_workspace_id is provided
        if not uc_workspace_id:
            return create_error_response(
                error_message="UC workspace ID is required",
                error_code="MISSING_WORKSPACE_ID",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Provide a uc_workspace_id parameter",
                    "Start a new session with start_uc_merge_session()",
                    "Ensure you have the workspace_id from the session creation response",
                ],
                next_steps="Call start_uc_merge_session() to create a UC workspace first.",
            )

        # Validate lza_workspace_id is provided
        if not lza_workspace_id:
            return create_error_response(
                error_message="LZA workspace ID is required",
                error_code="MISSING_WORKSPACE_ID",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Provide a lza_workspace_id parameter",
                    "Call getLzaConfiguration() to create an LZA workspace",
                    "Ensure you have the workspace_id from getLzaConfiguration response",
                ],
                next_steps="Call getLzaConfiguration() to retrieve the LZA configuration first.",
            )

        # List files in UC workspace
        try:
            uc_files = workspace_manager.list_files(uc_workspace_id)
        except WorkspaceNotFoundError:
            return create_error_response(
                error_message="UC workspace not found",
                error_code="WORKSPACE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify the uc_workspace_id is correct",
                    "Start a new session with start_uc_merge_session()",
                    "Ensure the workspace has not been deleted",
                ],
                next_steps="Call start_uc_merge_session() to create a new UC workspace.",
            )

        # Verify LZA workspace exists by listing files (will raise if not found)
        try:
            workspace_manager.list_files(lza_workspace_id)
        except WorkspaceNotFoundError:
            return create_error_response(
                error_message="LZA workspace not found",
                error_code="WORKSPACE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify the lza_workspace_id is correct",
                    "Call getLzaConfiguration() to create an LZA workspace",
                    "Ensure the workspace has not been deleted",
                ],
                context={"lza_workspace_id": lza_workspace_id},
                next_steps="Call getLzaConfiguration() to retrieve the LZA configuration.",
            )

        # Copy files from UC workspace to LZA workspace
        files_copied = 0
        directories_created: set[str] = set()

        for file_path in uc_files:
            # Skip metadata files
            if file_path == ".session_metadata.json":
                continue

            # Read file from UC workspace
            try:
                content = workspace_manager.read_file(uc_workspace_id, file_path)
            except (WorkspaceNotFoundError, WorkspaceStorageError) as e:
                logger.warning(
                    f"Failed to read file '{file_path}' from UC workspace: {e}"
                )
                continue

            # Determine destination path with optional prefix
            if path:
                dest_path = posixpath.join(path, file_path)
            else:
                dest_path = file_path

            # Track directories created
            parent_dir = posixpath.dirname(dest_path)
            if parent_dir:
                directories_created.add(parent_dir)

            # Write file to LZA workspace
            try:
                workspace_manager.write_file(lza_workspace_id, dest_path, content)
                files_copied += 1

                if files_copied % 10 == 0:
                    await ctx.info(f"Copied {files_copied} files...")
            except (WorkspaceValidationError, WorkspaceStorageError) as e:
                logger.warning(
                    f"Failed to write file '{dest_path}' to LZA workspace: {e}"
                )
                continue

        await ctx.info(
            f"Successfully copied {files_copied} files from UC workspace "
            f"{uc_workspace_id} to LZA workspace {lza_workspace_id}"
        )

        return create_success_response(
            data={
                "uc_workspace_id": uc_workspace_id,
                "lza_workspace_id": lza_workspace_id,
                "files_copied": files_copied,
                "directories_created": len(directories_created),
            },
            next_steps=(
                "UC configuration merged successfully. "
                f"Call putLzaConfiguration(workspace_id='{lza_workspace_id}') "
                "to upload the merged configuration."
            ),
        )

    except Exception as e:
        logger.error(f"Unexpected error copying UC to LZA config: {str(e)}")
        error_info = categorize_uc_merge_error(e)
        return create_error_response(
            error_message=f"Unexpected error during copy operation: {str(e)}",
            error_code=error_info["error_code"],
            category=error_info["category"],
            troubleshooting=error_info["troubleshooting"],
            context={
                "uc_workspace_id": uc_workspace_id,
                "lza_workspace_id": lza_workspace_id,
                "error_type": type(e).__name__,
            },
            next_steps="Review the error and retry the operation.",
        )
