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

"""MCP resource workaround tools.

Provides ``listResources`` and ``readResource`` tool wrappers so that
MCP agents without native resource support can access the same data
through the tool interface.

``listResources`` takes no parameters and returns a route map of all
supported resource URI patterns with descriptions.  ``readResource``
accepts a single URI and returns the corresponding data.
"""

import json
import logging
import re
from typing import Any

from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceValidationError,
)

logger = logging.getLogger(__name__)

_SUPPORTED_URIS = [
    "workspace://list",
    "workspace://{id}/files",
    "workspace://{id}/file/{path}",
]


def _error_unsupported(uri: str) -> str:
    """Return a JSON error for an unsupported URI pattern."""
    return json.dumps(
        {
            "error": f"Unsupported URI pattern: '{uri}'",
            "supported_patterns": _SUPPORTED_URIS,
        }
    )


# -- URI pattern regexes --
_RE_WORKSPACE_LIST = re.compile(r"^workspace://list$")
_RE_WORKSPACE_FILES = re.compile(r"^workspace://([^/]+)/files$")
_RE_WORKSPACE_FILE = re.compile(r"^workspace://([^/]+)/file/(.+)$")


def register_resource_tools(
    mcp: Any,
    workspace_manager: WorkspaceManager,
) -> None:
    """Register listResources and readResource tools.

    These are workaround tools for MCP agents that don't support
    native MCP resources.  They delegate to the same underlying
    ``WorkspaceManager`` instance used by the real MCP resources.

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
    """

    @mcp.tool()
    async def listResources() -> str:
        """List all available resource URIs.

        Returns a JSON object mapping resource URI patterns to their
        descriptions.  This is a discovery endpoint — call it first to
        see what is available, then use ``readResource`` with a specific
        URI.

        Workspace URIs are dynamic (based on existing workspaces and
        their files).  Template URIs are included only when template
        features are enabled.
        """
        routes: dict[str, str] = {
            "workspace://list": "List all workspace IDs",
            "workspace://{workspace_id}/files": (
                "List files in a workspace (replace {workspace_id} with workspace ID)"
            ),
            "workspace://{workspace_id}/file/{path}": (
                "Read a file from a workspace (replace {workspace_id} and {path})"
            ),
        }

        return json.dumps(routes)

    @mcp.tool()
    async def readResource(uri: str) -> str:
        """Read a resource by URI.

        Supported URI patterns:
        - workspace://list — list all workspace IDs
        - workspace://{id}/files — list files in a workspace
        - workspace://{id}/file/{path} — read a file from a workspace
        """
        # workspace://list
        if _RE_WORKSPACE_LIST.match(uri):
            try:
                ids = workspace_manager.list_workspaces()
                return json.dumps(ids)
            except Exception as exc:
                logger.error("readResource workspace://list failed: %s", exc)
                return json.dumps({"error": str(exc)})

        # workspace://{id}/files
        m = _RE_WORKSPACE_FILES.match(uri)
        if m:
            workspace_id = m.group(1)
            try:
                files = workspace_manager.list_files(workspace_id)
                return json.dumps(files)
            except WorkspaceNotFoundError as exc:
                return json.dumps({"error": str(exc)})
            except Exception as exc:
                logger.error("readResource %s failed: %s", uri, exc)
                return json.dumps({"error": str(exc)})

        # workspace://{id}/file/{path}
        m = _RE_WORKSPACE_FILE.match(uri)
        if m:
            workspace_id = m.group(1)
            path = m.group(2)
            try:
                content = workspace_manager.read_file(workspace_id, path)
                return content.decode("utf-8")
            except (WorkspaceNotFoundError, WorkspaceValidationError) as exc:
                return json.dumps({"error": str(exc)})
            except UnicodeDecodeError:
                return json.dumps({"error": f"File '{path}' contains binary content"})
            except Exception as exc:
                logger.error("readResource %s failed: %s", uri, exc)
                return json.dumps({"error": str(exc)})

        return _error_unsupported(uri)

    logger.info("Resource workaround tools (listResources, readResource) registered")
