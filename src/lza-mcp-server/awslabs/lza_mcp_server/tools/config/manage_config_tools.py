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
from awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file import (
    read_lza_config_file,
)
from awslabs.lza_mcp_server.tools.config.update_lza_config_file import (
    update_lza_config_file,
)
from awslabs.lza_mcp_server.tools.config.create_lza_config_file import (
    create_lza_config_file,
)
from awslabs.lza_mcp_server.utils.guidance_toggle import (
    strip_llm_guidance,
    tool_description,
)
from .descriptions import DESCRIPTIONS

logger = logging.getLogger(__name__)


def register_config_tools(mcp):
    """Register configuration-related MCP tools."""

    @mcp.tool(
        name="getMinimumConfiguration",
        description=tool_description(**DESCRIPTIONS["getMinimumConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def get_minimum_configuration(
        ctx: Context,
        config_type: Optional[str] = None,
        save_to_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        return strip_llm_guidance(
            await tool_get_minimum_configuration(ctx, config_type, save_to_directory)
        )

    lza_config_retrieval = LzaConfigRetrieval()

    @mcp.tool(
        name="getLzaConfiguration",
        description=tool_description(**DESCRIPTIONS["getLzaConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def get_lza_configuration(
        ctx: Context,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve LZA configuration from S3.

        For standard deployments (no qualifier):
          - Bucket: aws-accelerator-config-{account_id}-{region}
          - Key: zipped/aws-accelerator-config.zip

        For external pipeline deployments (with qualifier):
          - Bucket: {qualifier}-config-{account_id}-{region}
          - Key: lza/aws-accelerator-config.zip

        Args:
            qualifier: Accelerator Qualifier for external pipeline deployments.
            bucket_name: Explicit bucket name override.
        """
        return strip_llm_guidance(
            await lza_config_retrieval.get_configuration(ctx, qualifier, bucket_name)
        )

    @mcp.tool(
        name="putLzaConfiguration",
        description=tool_description(**DESCRIPTIONS["putLzaConfiguration"]),
    )  # nosemgrep: useless-inner-function
    async def put_lza_configuration(
        ctx: Context,
        qualifier: Optional[str] = None,
        config_path: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload LZA configuration to S3.

        For standard deployments (no qualifier):
          - Bucket: aws-accelerator-config-{account_id}-{region}
          - Key: zipped/aws-accelerator-config.zip

        For external pipeline deployments (with qualifier):
          - Bucket: {qualifier}-config-{account_id}-{region}
          - Key: lza/aws-accelerator-config.zip

        Args:
            qualifier: Accelerator Qualifier for external pipeline deployments.
            config_path: Optional container-relative path. Leave empty to auto-detect.
            bucket_name: Explicit bucket name override.
        """
        return strip_llm_guidance(
            await tool_put_lza_configuration(ctx, qualifier, config_path, bucket_name)
        )

    @mcp.tool(
        name="readLzaConfigFile",
        description=tool_description(**DESCRIPTIONS["readLzaConfigFile"]),
    )  # nosemgrep: useless-inner-function
    async def readLzaConfigFile(ctx: Context, file_path: str):
        """Read a configuration file from the extracted LZA configuration.

        This tool reads files from the LZA configuration directory that was
        extracted via getLzaConfiguration(). It validates paths for security
        and provides context-aware guidance based on the file being read.

        Common files to review:
        - accounts-config.yaml: Account structure and emails
        - global-config.yaml: Global settings including homeRegion
        - network-config.yaml: Network configuration
        - iam-config.yaml: IAM configuration

        Args:
            file_path: Relative path to file (e.g., "accounts-config.yaml"). Required parameter.

        Returns:
            Dictionary with file content, metadata, and next steps guidance
        """
        return strip_llm_guidance(await read_lza_config_file(ctx, file_path))

    @mcp.tool(
        name="updateLzaConfigFile",
        description=tool_description(**DESCRIPTIONS["updateLzaConfigFile"]),
    )  # nosemgrep: useless-inner-function
    async def update_lza_config_file_tool(
        ctx: Context,
        file_path: str,
        updates: Optional[Dict[str, Any]] = None,
        insert_path: Optional[str] = None,
        insert_value: Optional[Dict[str, Any]] = None,
        delete_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return strip_llm_guidance(
            await update_lza_config_file(
                ctx, file_path, updates, insert_path, insert_value, delete_path
            )
        )

    @mcp.tool(
        name="createLzaConfigFile",
        description=tool_description(**DESCRIPTIONS["createLzaConfigFile"]),
    )  # nosemgrep: useless-inner-function
    async def create_lza_config_file_tool(
        ctx: Context,
        file_path: str,
        content: Dict[str, Any],
        overwrite: bool = False,
        json_indent: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return strip_llm_guidance(
            await create_lza_config_file(
                ctx, file_path, content, overwrite, json_indent
            )
        )

    logger.info("Configuration tools registered successfully")
