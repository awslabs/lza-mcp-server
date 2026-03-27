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
from mcp.server.fastmcp import Context

from .get_uc_releases import tool_get_uc_releases
from .get_uc_network_models import tool_get_uc_network_models
from .start_uc_merge_session import tool_start_uc_merge_session
from .read_uc_file import read_uc_file
from .get_uc_network_customization_guide import get_uc_network_customization_guide
from .update_uc_file import update_uc_file
from .copy_uc_to_lza_config import copy_uc_to_lza_config
from .validate_lza_for_uc_merge import validate_lza_for_uc_merge
from awslabs.lza_mcp_server.utils.guidance_toggle import (
    strip_llm_guidance,
    tool_description,
)
from .descriptions import DESCRIPTIONS


logger = logging.getLogger(__name__)


def register_uc_merge_tools(mcp):
    """Register UC merge-related MCP tools.

    This function registers all tools needed for the Universal Configuration
    merge workflow, enabling AI-assisted integration of LZA Universal Configuration
    with fresh LZA installations.

    Tools registered:
    - validate_lza_for_uc_merge: Validate LZA installation is fresh and compatible
    - get_uc_releases: Discover available UC release versions
    - get_uc_network_models: Get network deployment model comparison
    - start_uc_merge_session: Initialize a UC merge session
    - read_uc_file: Read UC files from session
    - update_uc_file: Update UC files in session
    - get_uc_network_customization_guide: Get customization guidance
    - copy_uc_to_lza_config: Copy UC configuration to LZA directory

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["validateLzaForUcMerge"]),
    )
    async def validateLzaForUcMerge(ctx: Context):
        """Validate that the LZA installation is fresh and compatible with UC merge."""
        return strip_llm_guidance(await validate_lza_for_uc_merge(ctx))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["get_uc_releases"]),
    )
    async def get_uc_releases(ctx: Context):
        """Discover available UC release versions."""
        return strip_llm_guidance(await tool_get_uc_releases(ctx))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["get_uc_network_models"]),
    )
    async def get_uc_network_models(ctx: Context, uc_release: str):
        """Get available UC network deployment models with comparison information."""
        return strip_llm_guidance(await tool_get_uc_network_models(ctx, uc_release))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["start_uc_merge_session"]),
    )
    async def start_uc_merge_session(ctx: Context, uc_release: str, network_model: str):
        """Start a new UC merge session with the selected release and network model."""
        return strip_llm_guidance(
            await tool_start_uc_merge_session(ctx, uc_release, network_model)
        )

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["readUcFile"]),
    )
    async def readUcFile(ctx: Context, session_id: str, file_path: str):
        """Read a file from the UC session directory."""
        return strip_llm_guidance(await read_uc_file(ctx, session_id, file_path))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["getUcNetworkCustomizationGuide"]),
    )
    async def getUcNetworkCustomizationGuide(ctx: Context, session_id: str):
        """Get network customization guidance and file list for the session's network model."""
        return strip_llm_guidance(get_uc_network_customization_guide(session_id))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["updateUcFile"]),
    )
    async def updateUcFile(
        ctx: Context, session_id: str, file_path: str, updates: dict
    ):
        """Update a UC configuration file in the session directory with new values."""
        return strip_llm_guidance(await update_uc_file(session_id, file_path, updates))

    @mcp.tool(
        description=tool_description(**DESCRIPTIONS["copyUcToLzaConfig"]),
    )
    async def copyUcToLzaConfig(ctx: Context, session_id: str):
        """Copy UC configuration from session directory to extracted LZA configuration directory."""
        return strip_llm_guidance(await copy_uc_to_lza_config(ctx, session_id))

    logger.info("UC merge tools registered successfully")
