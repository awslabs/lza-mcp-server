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

### AWS Services
- **checkAwsConnectivity**: Verify AWS credentials and connectivity
- **setupS3Bucket**: Create and configure S3 buckets for LZA

### Configuration Management
- **getMinimumConfiguration**: Generate minimal LZA configuration templates
- **uploadConfigurationToS3**: Upload configuration files to S3 bucket

### Validation
- **validateConfigurationFromS3**: Validate LZA configurations stored in S3
- **validateConfigurationFromShare**: Validate configurations from file shares
- **cleanupValidationZip**: Clean up temporary validation files

### Pipeline Management
- **releasePipeline**: Trigger execution of the LZA Configuration Pipeline
- **getPipelineStatus**: Monitor pipeline execution status with stage progression
- **diagnosePipelineErrors**: Retrieve CodeBuild logs for failed executions

### Schema Management
- **getConfigurationSchema**: Retrieve LZA configuration JSON schemas

## Typical Workflow

1. Check AWS connectivity with `checkAwsConnectivity`
2. Generate configuration with `getMinimumConfiguration`
3. Validate configuration with `validateConfigurationFromS3`
4. Upload to S3 with `uploadConfigurationToS3`
5. Deploy with `releasePipeline`
6. Monitor with `getPipelineStatus`

For detailed usage instructions, see the individual tool documentation.
""",
    dependencies=["pydantic", "PyYAML", "boto3"],
)


def register_all_components():
    """Register all MCP tools and resources."""
    from .tools.aws_services import register_aws_tools
    from .tools.config import register_config_tools
    from .tools import register_validation_tools
    from .tools.pipeline import register_pipeline_tools
    from .tools.schema import register_schema_tools

    # Register all tool categories
    register_aws_tools(mcp)
    register_config_tools(mcp)
    register_validation_tools(mcp)
    register_pipeline_tools(mcp)
    register_schema_tools(mcp)

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
