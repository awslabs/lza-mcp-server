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

"""Server configuration and instructions builder."""

import os


def is_uc_merge_enabled() -> bool:
    """Check if UC Merge tools should be enabled.

    Returns:
        bool: True if UC Merge is enabled, False otherwise
    """
    return os.environ.get("ENABLE_UC_MERGE", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def get_base_instructions() -> str:
    """Get base server instructions.

    Returns:
        str: Base instructions text
    """
    return """# AWS Landing Zone Accelerator (LZA) MCP Server

This MCP server helps manage LZA configurations and pipeline operations for the AWS Landing Zone Accelerator solution.

## Configuration

The server can be configured via environment variables in your MCP client configuration:

- **LZA_PREFIX**: The prefix used by your LZA deployment for resource naming (default: "AWSAccelerator")
  - This prefix is used for pipeline names, SSM parameters, and CloudFormation stacks
  - Set this if you customized the prefix during LZA installation
  - Example: If your pipeline is named "MyOrg-Pipeline", set LZA_PREFIX="MyOrg"

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


def get_uc_merge_instructions() -> str:
    """Get UC Merge tools instructions.

    Returns:
        str: UC Merge instructions text
    """
    return """

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


def get_workflow_instructions() -> str:
    """Get workflow instructions.

    Returns:
        str: Workflow instructions text
    """
    return """

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


def build_instructions(include_uc_merge: bool = None) -> str:
    """Build complete server instructions.

    Args:
        include_uc_merge: Whether to include UC Merge instructions.
                         If None, checks environment variable.

    Returns:
        str: Complete instructions text
    """
    if include_uc_merge is None:
        include_uc_merge = is_uc_merge_enabled()

    instructions = get_base_instructions()

    if include_uc_merge:
        instructions += get_uc_merge_instructions()

    instructions += get_workflow_instructions()

    return instructions
