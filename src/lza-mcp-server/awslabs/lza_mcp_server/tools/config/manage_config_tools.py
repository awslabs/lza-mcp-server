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

"""Configuration-related MCP tools for the LZA MCP Server."""

import logging
from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
)
from awslabs.lza_mcp_server.tools.config.get_lza_configuration import (
    LzaConfigRetrieval,
)
from awslabs.lza_mcp_server.tools.config.put_lza_configuration import (
    tool_put_lza_configuration,
)
from awslabs.lza_mcp_server.utils.guidance_toggle import (
    strip_llm_guidance,
    tool_description,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from .descriptions import DESCRIPTIONS

logger = logging.getLogger(__name__)


def register_config_tools(mcp, workspace_manager: WorkspaceManager):
    """Register configuration-related MCP tools."""

    @mcp.tool(
        name="getMinimumConfiguration",
        description=tool_description(**DESCRIPTIONS["getMinimumConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def get_minimum_configuration(
        ctx: Context,
        config_type: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return strip_llm_guidance(
            await tool_get_minimum_configuration(
                ctx, workspace_manager, config_type, workspace_id
            )
        )

    lza_config_retrieval = LzaConfigRetrieval(workspace_manager)

    @mcp.tool(
        name="getLzaConfiguration",
        description=tool_description(**DESCRIPTIONS["getLzaConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def get_lza_configuration(
        ctx: Context,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve LZA configuration from S3 into a workspace.

        For standard deployments (no qualifier):
          - Bucket: aws-accelerator-config-{account_id}-{region}
          - Key: zipped/aws-accelerator-config.zip

        For external pipeline deployments (with qualifier):
          - Bucket: {qualifier}-config-{account_id}-{region}
          - Key: lza/aws-accelerator-config.zip

        Args:
            qualifier: Accelerator Qualifier for external pipeline deployments.
            bucket_name: Explicit bucket name override.
            workspace_id: Optional workspace ID. A new workspace is created if omitted.
            path: Optional relative path within the workspace to extract into.
        """
        return strip_llm_guidance(
            await lza_config_retrieval.get_configuration(
                ctx, qualifier, bucket_name, workspace_id, path
            )
        )

    @mcp.tool(
        name="putLzaConfiguration",
        description=tool_description(**DESCRIPTIONS["putLzaConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def put_lza_configuration(
        ctx: Context,
        workspace_id: str,
        path: str,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload LZA configuration from a workspace to S3.

        For standard deployments (no qualifier):
          - Bucket: aws-accelerator-config-{account_id}-{region}
          - Key: zipped/aws-accelerator-config.zip

        For external pipeline deployments (with qualifier):
          - Bucket: {qualifier}-config-{account_id}-{region}
          - Key: lza/aws-accelerator-config.zip

        Args:
            workspace_id: Workspace containing the configuration files.
            path: Relative path within the workspace where config files reside.
            qualifier: Accelerator Qualifier for external pipeline deployments.
            bucket_name: Explicit bucket name override.
        """
        return strip_llm_guidance(
            await tool_put_lza_configuration(
                ctx, workspace_manager, workspace_id, path, qualifier, bucket_name
            )
        )

    logger.info("Configuration tools registered successfully")
