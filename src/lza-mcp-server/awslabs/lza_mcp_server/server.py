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

"""AWS Landing Zone Accelerator (LZA) MCP Server implementation."""

import os
import logging
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set log level from environment variable (default: INFO)
log_level = os.environ.get("FASTMCP_LOG_LEVEL", "INFO")
logging.getLogger().setLevel(log_level)

# Initialize the FastMCP server
mcp = FastMCP(
    "awslabs.lza-mcp-server",
    instructions="""# AWS Landing Zone Accelerator (LZA) MCP Server

This MCP server helps manage LZA configurations and pipeline operations for the AWS Landing Zone Accelerator solution.

## Available Tools

### Pipeline Management
- **releasePipeline**: Trigger execution of the LZA Configuration Pipeline (AWSAccelerator-Pipeline)
- **getPipelineStatus**: Monitor pipeline execution status with stage progression details
- **diagnosePipelineErrors**: Automatically retrieve CodeBuild logs for failed pipeline executions

## Pipeline Management Workflow

1. Trigger pipeline deployment with `releasePipeline`
2. Monitor progress with `getPipelineStatus`
3. If failures occur, diagnose issues with `diagnosePipelineErrors`

For detailed usage instructions, see the individual tool documentation.
""",
    dependencies=["pydantic", "PyYAML", "boto3"],
)


def register_all_components():
    """Register all MCP tools and resources."""
    from .tools.pipeline import register_pipeline_tools

    # Register pipeline tools
    register_pipeline_tools(mcp)

    logger.info("All MCP components registered successfully")


def main():
    """Run the LZA MCP server."""
    logger.info("Starting LZA MCP Server")

    # Register all components
    register_all_components()

    # Run the server
    mcp.run()


def runserver():
    """Alternative entry point for the server."""
    main()


if __name__ == "__main__":
    main()
