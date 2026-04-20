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

"""Component registration for MCP server."""

import logging
import os
from typing import Any, Union

from .utils.local_adapter import LocalAdapter
from .utils.s3_adapter import S3Adapter
from .utils.workspace_manager import WorkspaceManager
from .utils.zip_utility import ZipUtility

logger = logging.getLogger(__name__)


def create_storage_adapter() -> Union[LocalAdapter, S3Adapter]:
    """Create the appropriate storage adapter based on environment config.

    Reads ``WORKSPACE_STORAGE`` env var. Returns ``LocalAdapter`` for
    ``local`` (or unset), ``S3Adapter`` for ``s3``. Logs an error and
    falls back to local for unrecognised values.
    """
    storage_type = os.environ.get("WORKSPACE_STORAGE", "local").lower()

    if storage_type == "s3":
        s3_adapter = S3Adapter()
        logger.info("Using S3 storage adapter")
        return s3_adapter

    if storage_type not in ("local", ""):
        logger.error(
            "Unrecognized WORKSPACE_STORAGE='%s', defaulting to local",
            storage_type,
        )

    local_adapter = LocalAdapter()
    logger.info("Using local storage adapter")
    return local_adapter


def register_core_tools(mcp: Any, workspace_manager: WorkspaceManager) -> None:
    """Register core MCP tools.

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
    """
    from .tools.aws_services import register_aws_tools
    from .tools.config import register_config_tools
    from .tools.pipeline import register_pipeline_tools
    from .tools.schema import register_schema_tools

    register_aws_tools(mcp)
    register_config_tools(mcp, workspace_manager)
    register_pipeline_tools(mcp)
    register_schema_tools(mcp)


def register_uc_merge_tools_if_enabled(
    mcp: Any, enabled: bool, workspace_manager: WorkspaceManager
) -> None:
    """Conditionally register UC Merge tools.

    Args:
        mcp: FastMCP server instance
        enabled: Whether UC Merge tools should be enabled
        workspace_manager: Shared WorkspaceManager instance
    """
    if enabled:
        from .tools.uc_merge import register_uc_merge_tools

        register_uc_merge_tools(mcp, workspace_manager)
        logger.info("UC Merge tools enabled and registered")
    else:
        logger.info("UC Merge tools disabled (set ENABLE_UC_MERGE=true to enable)")


def register_workspace_components(
    mcp: Any,
    workspace_manager: WorkspaceManager,
    zip_utility: ZipUtility,
) -> None:
    """Register workspace tools and resources.

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
        zip_utility: Shared ZipUtility instance
    """
    from .resources.workspace import register_workspace_resources
    from .tools.workspace import register_workspace_tools

    register_workspace_tools(mcp, workspace_manager, zip_utility)
    register_workspace_resources(mcp, workspace_manager)


def register_all_components(
    mcp: Any,
    enable_uc_merge: bool,
    disable_resource_tools: bool = False,
) -> None:
    """Register all MCP tools and resources.

    Args:
        mcp: FastMCP server instance
        enable_uc_merge: Whether to enable UC Merge tools
        disable_resource_tools: Whether to disable resource workaround tools
    """
    # Create shared workspace infrastructure first — used by both core and workspace tools
    adapter = create_storage_adapter()
    workspace_manager = WorkspaceManager(adapter)

    register_core_tools(mcp, workspace_manager)
    register_uc_merge_tools_if_enabled(mcp, enable_uc_merge, workspace_manager)

    # Workspace components (always active)
    zip_utility = ZipUtility(workspace_manager)
    register_workspace_components(mcp, workspace_manager, zip_utility)

    # Resource workaround tools (on by default; set DISABLE_RESOURCE_TOOLS=true to suppress)
    if not disable_resource_tools:
        from .tools.resource_tools import register_resource_tools

        register_resource_tools(mcp, workspace_manager)
    else:
        logger.info(
            "Resource workaround tools disabled (DISABLE_RESOURCE_TOOLS is set)"
        )

    logger.info("All MCP components registered successfully")
