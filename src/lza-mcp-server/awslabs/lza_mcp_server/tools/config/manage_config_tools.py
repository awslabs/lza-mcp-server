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
from awslabs.lza_mcp_server.tools.config.upload_config_s3 import (
    tool_upload_configuration_to_s3,
)

logger = logging.getLogger(__name__)


def register_config_tools(mcp):
    """Register configuration-related MCP tools."""

    @mcp.tool(
        name="getMinimumConfiguration",
        description="Generate minimal LZA configuration templates for quick setup",
    )  # nosemgrep: useless-inner-function
    async def get_minimum_configuration(
        ctx: Context,
        config_type: Optional[str] = None,
        save_to_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await tool_get_minimum_configuration(ctx, config_type, save_to_directory)

    @mcp.tool(
        name="uploadConfigurationToS3",
        description="Upload LZA configuration files to the default S3 bucket",
    )  # nosemgrep: useless-inner-function
    async def upload_configuration_to_s3(
        ctx: Context,
        config_path: Optional[str] = None,
        bucket_name: Optional[str] = None,
        offer_pipeline_release: bool = True,
    ) -> Dict[str, Any]:
        return await tool_upload_configuration_to_s3(
            ctx, config_path, bucket_name, offer_pipeline_release
        )

    logger.info("Configuration tools registered successfully")
