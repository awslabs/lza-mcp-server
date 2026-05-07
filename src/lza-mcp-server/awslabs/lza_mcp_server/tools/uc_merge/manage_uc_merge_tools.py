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

"""UC Merge-related MCP tools for the LZA MCP Server."""

import logging
from typing import Optional

from mcp.server.fastmcp import Context

from .get_uc_releases import tool_get_uc_releases
from .get_uc_network_models import tool_get_uc_network_models
from .start_uc_merge_session import tool_start_uc_merge_session
from .get_uc_network_customization_guide import get_uc_network_customization_guide
from .copy_uc_to_lza_config import copy_uc_to_lza_config
from .validate_lza_for_uc_merge import validate_lza_for_uc_merge
from awslabs.lza_mcp_server.aws_access import current_tool
from awslabs.lza_mcp_server.utils.guidance_toggle import (
    strip_llm_guidance,
    tool_description,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from .descriptions import DESCRIPTIONS


logger = logging.getLogger(__name__)

# Module-level singleton set during registration
_workspace_manager: Optional[WorkspaceManager] = None


def register_uc_merge_tools(mcp, workspace_manager: WorkspaceManager):
    """Register UC merge-related MCP tools.

    This function registers all tools needed for the Universal Configuration
    merge workflow, enabling AI-assisted integration of LZA Universal Configuration
    with fresh LZA installations.

    Tools registered:
    - validate_lza_for_uc_merge: Validate LZA installation is fresh and compatible
    - get_uc_releases: Discover available UC release versions
    - get_uc_network_models: Get network deployment model comparison
    - start_uc_merge_session: Initialize a UC merge session
    - get_uc_network_customization_guide: Get customization guidance
    - copy_uc_to_lza_config: Copy UC configuration to LZA directory

    Args:
        mcp: FastMCP server instance
        workspace_manager: Shared WorkspaceManager instance
    """
    global _workspace_manager  # noqa: PLW0603
    _workspace_manager = workspace_manager

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["validateLzaForUcMerge"]),
    )
    async def validateLzaForUcMerge(ctx: Context, workspace_id: str, path: str = ""):
        """Validate that the LZA installation is fresh and compatible with UC merge."""
        current_tool.set("validateLzaForUcMerge")
        return strip_llm_guidance(
            await validate_lza_for_uc_merge(ctx, workspace_id, path, _workspace_manager)
        )

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["get_uc_releases"]),
    )
    async def get_uc_releases(ctx: Context):
        """Discover available UC release versions."""
        current_tool.set("get_uc_releases")
        return strip_llm_guidance(await tool_get_uc_releases(ctx))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["get_uc_network_models"]),
    )
    async def get_uc_network_models(ctx: Context, uc_release: str):
        """Get available UC network deployment models with comparison information."""
        current_tool.set("get_uc_network_models")
        return strip_llm_guidance(await tool_get_uc_network_models(ctx, uc_release))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["start_uc_merge_session"]),
    )
    async def start_uc_merge_session(ctx: Context, uc_release: str, network_model: str):
        """Start a new UC merge session with the selected release and network model."""
        current_tool.set("start_uc_merge_session")
        return strip_llm_guidance(
            await tool_start_uc_merge_session(
                ctx, uc_release, network_model, _workspace_manager
            )
        )

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["getUcNetworkCustomizationGuide"]),
    )
    async def getUcNetworkCustomizationGuide(ctx: Context, workspace_id: str):
        """Get network customization guidance and file list for the session's network model."""
        current_tool.set("getUcNetworkCustomizationGuide")
        return strip_llm_guidance(
            get_uc_network_customization_guide(workspace_id, _workspace_manager)
        )

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["copyUcToLzaConfig"]),
    )
    async def copyUcToLzaConfig(
        ctx: Context, uc_workspace_id: str, lza_workspace_id: str, path: str = ""
    ):
        """Copy UC configuration from UC workspace to LZA workspace."""
        current_tool.set("copyUcToLzaConfig")
        return strip_llm_guidance(
            await copy_uc_to_lza_config(
                ctx, uc_workspace_id, lza_workspace_id, _workspace_manager, path
            )
        )

    logger.info("UC merge tools registered successfully")
