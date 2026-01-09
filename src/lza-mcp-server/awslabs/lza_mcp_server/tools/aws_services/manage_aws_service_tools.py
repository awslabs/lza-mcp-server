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

"""AWS-related MCP tools for the LZA MCP Server."""

import logging
from typing import Dict, Any
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity import (
    tool_check_aws_connectivity,
)
from awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version import (
    tool_get_deployed_lza_version,
)

logger = logging.getLogger(__name__)


def register_aws_tools(mcp):
    """Register AWS-related MCP tools."""

    @mcp.tool(
        name="checkAwsConnectivity",
        description="Verify AWS credentials and connectivity to ensure proper access to AWS services",
    )
    async def check_aws_connectivity(ctx: Context) -> Dict[str, Any]:
        return await tool_check_aws_connectivity(ctx)

    @mcp.tool(
        name="getDeployedLzaVersion",
        description="Get the currently deployed LZA version from the environment by reading the SSM parameter",
    )
    async def get_deployed_lza_version(ctx: Context) -> Dict[str, Any]:
        return await tool_get_deployed_lza_version(ctx)

    logger.info("AWS tools registered successfully")
