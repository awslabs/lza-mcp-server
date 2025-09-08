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

"""Validation-related MCP tools for the LZA MCP Server."""

import logging
from typing import Dict, Any
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.tools.validation.cleanup_validation_zip import (
    tool_cleanup_validation_zip,
)
from awslabs.lza_mcp_server.tools.validation.validate_configuration_share import (
    tool_validate_configuration_from_share,
)
from awslabs.lza_mcp_server.tools.validation.validation_configuration_s3 import (
    tool_validate_configuration_from_s3,
)

logger = logging.getLogger(__name__)


def register_validation_tools(mcp):
    """Register validation-related MCP tools."""

    @mcp.tool(
        name="validateConfigurationFromS3",
        description="Validate LZA configurations stored in S3 bucket for syntax and compliance",
    )  # nosemgrep: useless-inner-function
    async def validate_configuration_from_s3(
        ctx: Context,
        s3_path: str,
    ) -> Dict[str, Any]:
        return await tool_validate_configuration_from_s3(ctx, s3_path)

    @mcp.tool(
        name="validateConfigurationFromShare",
        description="Validate LZA configurations from local file shares or directories",
    )  # nosemgrep: useless-inner-function
    async def validate_configuration_from_share(
        ctx: Context, local_share_path: str = "~/Documents/lza-config"
    ) -> Dict[str, Any]:
        return await tool_validate_configuration_from_share(ctx, local_share_path)

    @mcp.tool(
        name="cleanupValidationZip",
        description="Clean up temporary validation files and zip archives after validation",
    )  # nosemgrep: useless-inner-function
    async def cleanup_validation_zip(
        ctx: Context, share_path: str = "~/Documents/lza-config"
    ) -> Dict[str, Any]:
        return await tool_cleanup_validation_zip(ctx, share_path)

    logger.info("Validation tools registered successfully")
