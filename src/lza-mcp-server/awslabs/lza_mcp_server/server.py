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
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set log level from environment variable (default: INFO)
log_level = os.environ.get("FASTMCP_LOG_LEVEL", "INFO")
logging.getLogger().setLevel(log_level)

# Check if UC Merge tools should be enabled
_enable_uc_merge = os.environ.get("ENABLE_UC_MERGE", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Build instructions based on enabled features
_base_instructions = """# AWS Landing Zone Accelerator (LZA) MCP Server

This MCP server helps manage LZA configurations and pipeline operations for the AWS Landing Zone Accelerator solution.

## Available Tools

### AWS Services
- **checkAwsConnectivity**: Verify AWS credentials and connectivity
- **getDeployedLzaVersion**: Get the currently deployed LZA version from SSM Parameter Store

### Configuration Management
- **getMinimumConfiguration**: Generate minimal LZA configuration templates
- **uploadConfigurationToS3**: Upload configuration files to S3 bucket
- **getConfigurationFromS3**: Retrieve and extract current LZA configuration from S3

### Pipeline Management
- **releasePipeline**: Trigger execution of the LZA Configuration Pipeline
- **getPipelineStatus**: Monitor pipeline execution status with stage progression
- **diagnosePipelineErrors**: Retrieve CodeBuild logs for failed executions

### Schema Management
- **listLzaSupportedVersions**: List all supported LZA versions with schema information
- **searchJsonSchema**: Search through LZA JSON schemas (requires lza_version parameter)
- **getFullSchema**: Retrieve complete LZA configuration JSON schemas (requires lza_version parameter)"""

_uc_merge_instructions = """

### UC Merge Tools (Universal Configuration)
- **validateLzaForUcMerge**: Validate LZA installation compatibility with UC merge
- **get_uc_releases**: Discover available UC release versions
- **get_uc_network_models**: Get network deployment model comparison
- **start_uc_merge_session**: Initialize a UC merge session
- **readLzaConfigFile**: Read LZA configuration files
- **readUcFile**: Read UC files from session
- **updateUcFile**: Update UC files in session
- **getUcNetworkCustomizationGuide**: Get customization guidance
- **copyUcToLzaConfig**: Copy UC configuration to LZA directory"""

_workflow_instructions = """

## Typical Workflows

### Deployment Workflow
1. Check AWS connectivity with `checkAwsConnectivity`
2. Generate configuration with `getMinimumConfiguration`
3. Upload to S3 with `uploadConfigurationToS3`
4. Deploy with `releasePipeline`
5. Monitor with `getPipelineStatus`

### Schema Query Workflow
When working with LZA schemas, use this recommended workflow:
1. Call `getDeployedLzaVersion` to get the currently deployed LZA version
2. Use the returned version as the `lza_version` parameter in `searchJsonSchema` or `getFullSchema`
3. This ensures schema queries match your deployed environment

Alternatively, use `listLzaSupportedVersions` to see all available schema versions.

For detailed usage instructions, see the individual tool documentation.
"""

_instructions = _base_instructions
if _enable_uc_merge:
    _instructions += _uc_merge_instructions
_instructions += _workflow_instructions

# Initialize the FastMCP server
mcp = FastMCP(
    "awslabs.lza-mcp-server",
    instructions=_instructions,
    dependencies=["pydantic", "PyYAML", "boto3"],
)


def register_all_components():
    """Register all MCP tools and resources."""
    from .tools.aws_services import register_aws_tools
    from .tools.config import register_config_tools
    from .tools.pipeline import register_pipeline_tools
    from .tools.schema import register_schema_tools

    # Register core tool categories
    register_aws_tools(mcp)
    register_config_tools(mcp)
    register_pipeline_tools(mcp)
    register_schema_tools(mcp)

    # Conditionally register UC Merge tools based on environment variable
    enable_uc_merge = os.environ.get("ENABLE_UC_MERGE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    if enable_uc_merge:
        from .tools.uc_merge import register_uc_merge_tools

        register_uc_merge_tools(mcp)
        logger.info("UC Merge tools enabled and registered")
    else:
        logger.info("UC Merge tools disabled (set ENABLE_UC_MERGE=true to enable)")

    logger.info("All MCP components registered successfully")


def main():
    """Run the LZA MCP server."""
    logger.info("Starting LZA MCP Server")

    # Validate schema integrity on startup (T-015)
    schema_dir = Path(os.environ.get("LZA_SCHEMA_DIR", "/app/json-schemas"))

    try:
        from .utils.integrity import validate_schemas_on_startup

        # Validate schemas - fail fast if tampering detected
        validate_schemas_on_startup(schema_dir=schema_dir, fail_on_error=True)
    except ImportError:
        logger.warning("Schema integrity validation module not available")
    except Exception as e:
        logger.error(f"Schema integrity validation failed: {e}")
        raise

    # Register all components
    register_all_components()

    # Run the server
    mcp.run()


def runserver():
    """Alternative entry point for the server."""
    main()


if __name__ == "__main__":
    main()
