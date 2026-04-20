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

"""Workspace-related MCP tools for the LZA MCP Server."""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.utils.error_handling import (
    create_structured_error_response,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)
from awslabs.lza_mcp_server.utils.zip_utility import ZipUtility

logger = logging.getLogger(__name__)

# Module-level singletons set during registration
_workspace_manager: Optional[WorkspaceManager] = None
_zip_utility: Optional[ZipUtility] = None


def _error_response(
    exc: Exception, operation: str, **extra_context: Any
) -> Dict[str, Any]:
    """Build a structured error response from a workspace exception."""
    if isinstance(exc, WorkspaceValidationError):
        category = ErrorCategory.VALIDATION
        code = "WORKSPACE_VALIDATION_ERROR"
        tips = ["Check that the path is relative and does not contain '..'"]
    elif isinstance(exc, WorkspaceNotFoundError):
        category = ErrorCategory.FILE_NOT_FOUND
        code = "WORKSPACE_NOT_FOUND"
        tips = [
            "Verify the workspace ID is correct",
            "Use createWorkspace to create a new workspace",
        ]
    elif isinstance(exc, WorkspaceStorageError):
        category = ErrorCategory.FILE_OPERATION
        code = "WORKSPACE_STORAGE_ERROR"
        tips = ["Check storage adapter configuration and permissions"]
    else:
        category = ErrorCategory.SYSTEM
        code = "WORKSPACE_UNEXPECTED_ERROR"
        tips = ["An unexpected error occurred — check server logs"]

    return create_structured_error_response(
        error=str(exc),
        category=category,
        error_code=code,
        troubleshooting=tips,
        context=extra_context,
        operation=operation,
    )


def register_workspace_tools(
    mcp: Any,
    workspace_manager: WorkspaceManager,
    zip_utility: ZipUtility,
) -> None:
    """Register workspace MCP tools.

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
        zip_utility: Shared ZipUtility instance
    """
    global _workspace_manager, _zip_utility  # noqa: PLW0603
    _workspace_manager = workspace_manager
    _zip_utility = zip_utility

    @mcp.tool(
        name="createWorkspace",
        description="Create a new workspace and return its unique ID.",
    )  # nosemgrep: useless-inner-function
    async def create_workspace(ctx: Context) -> Dict[str, Any]:
        try:
            workspace_id = _workspace_manager.create_workspace()
            return {"success": True, "workspace_id": workspace_id}
        except Exception as exc:
            return _error_response(exc, "createWorkspace")

    @mcp.tool(
        name="deleteWorkspace",
        description="Delete a workspace and all its contents.",
    )  # nosemgrep: useless-inner-function
    async def delete_workspace(ctx: Context, workspace_id: str) -> Dict[str, Any]:
        try:
            _workspace_manager.delete_workspace(workspace_id)
            return {"success": True}
        except Exception as exc:
            return _error_response(exc, "deleteWorkspace", workspace_id=workspace_id)

    @mcp.tool(
        name="writeWorkspaceFile",
        description=(
            "Create or overwrite a file in a workspace. "
            "Intermediate directories are created automatically."
        ),
    )  # nosemgrep: useless-inner-function
    async def write_workspace_file(
        ctx: Context, workspace_id: str, path: str, content: str
    ) -> Dict[str, Any]:
        try:
            _workspace_manager.write_file(workspace_id, path, content.encode("utf-8"))
            return {"success": True}
        except Exception as exc:
            return _error_response(
                exc, "writeWorkspaceFile", workspace_id=workspace_id, path=path
            )

    @mcp.tool(
        name="deleteWorkspaceFile",
        description="Delete a file from a workspace.",
    )  # nosemgrep: useless-inner-function
    async def delete_workspace_file(
        ctx: Context, workspace_id: str, path: str
    ) -> Dict[str, Any]:
        try:
            _workspace_manager.delete_file(workspace_id, path)
            return {"success": True}
        except Exception as exc:
            return _error_response(
                exc, "deleteWorkspaceFile", workspace_id=workspace_id, path=path
            )

    @mcp.tool(
        name="createWorkspaceFolder",
        description=(
            "Create a folder (and any intermediate directories) in a workspace."
        ),
    )  # nosemgrep: useless-inner-function
    async def create_workspace_folder(
        ctx: Context, workspace_id: str, path: str
    ) -> Dict[str, Any]:
        try:
            _workspace_manager.create_folder(workspace_id, path)
            return {"success": True}
        except Exception as exc:
            return _error_response(
                exc, "createWorkspaceFolder", workspace_id=workspace_id, path=path
            )

    @mcp.tool(
        name="deleteWorkspaceFolder",
        description="Delete a folder and all its contents from a workspace.",
    )  # nosemgrep: useless-inner-function
    async def delete_workspace_folder(
        ctx: Context, workspace_id: str, path: str
    ) -> Dict[str, Any]:
        try:
            _workspace_manager.delete_folder(workspace_id, path)
            return {"success": True}
        except Exception as exc:
            return _error_response(
                exc, "deleteWorkspaceFolder", workspace_id=workspace_id, path=path
            )

    @mcp.tool(
        name="zipWorkspaceFiles",
        description=(
            "Create a zip archive from specified files and folders in a workspace."
        ),
    )  # nosemgrep: useless-inner-function
    async def zip_workspace_files(
        ctx: Context,
        workspace_id: str,
        source_paths: List[str],
        destination_path: str,
    ) -> Dict[str, Any]:
        try:
            _zip_utility.create_zip(workspace_id, source_paths, destination_path)
            return {"success": True, "zip_path": destination_path}
        except Exception as exc:
            return _error_response(
                exc,
                "zipWorkspaceFiles",
                workspace_id=workspace_id,
                destination_path=destination_path,
            )

    logger.info("Workspace tools registered successfully")
