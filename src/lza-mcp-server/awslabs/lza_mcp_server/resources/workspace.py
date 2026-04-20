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

"""Workspace MCP resources (read-only operations)."""

import json
import logging
from typing import Any, Optional

from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceValidationError,
)

logger = logging.getLogger(__name__)

_workspace_manager: Optional[WorkspaceManager] = None


def register_workspace_resources(
    mcp: Any,
    workspace_manager: WorkspaceManager,
) -> None:
    """Register workspace MCP resources.

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
    """
    global _workspace_manager  # noqa: PLW0603
    _workspace_manager = workspace_manager

    @mcp.resource("workspace://list")
    async def list_workspaces() -> str:
        """Return a JSON array of all workspace IDs."""
        try:
            ids = _workspace_manager.list_workspaces()
            return json.dumps(ids)
        except Exception as exc:
            logger.error("Failed to list workspaces: %s", exc)
            return json.dumps({"error": str(exc)})

    @mcp.resource("workspace://{workspace_id}/files")
    async def list_workspace_files(workspace_id: str) -> str:
        """Return a JSON array of all file paths in a workspace."""
        try:
            files = _workspace_manager.list_files(workspace_id)
            return json.dumps(files)
        except WorkspaceNotFoundError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("Failed to list files in workspace %s: %s", workspace_id, exc)
            return json.dumps({"error": str(exc)})

    @mcp.resource("workspace://{workspace_id}/file/{path}")
    async def read_workspace_file(workspace_id: str, path: str) -> str:
        """Return the contents of a file in a workspace."""
        try:
            content = _workspace_manager.read_file(workspace_id, path)
            return content.decode("utf-8")
        except (WorkspaceNotFoundError, WorkspaceValidationError) as exc:
            return json.dumps({"error": str(exc)})
        except UnicodeDecodeError:
            # Binary file — return as-is (base64 could be added later)
            return json.dumps({"error": f"File '{path}' contains binary content"})
        except Exception as exc:
            logger.error(
                "Failed to read file '%s' in workspace %s: %s",
                path,
                workspace_id,
                exc,
            )
            return json.dumps({"error": str(exc)})

    logger.info("Workspace resources registered successfully")
