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

    lza_config_retrieval = LzaConfigRetrieval()

    @mcp.tool(
        name="getLzaConfiguration",
        description="""Retrieve LZA configuration from S3 for both standard and external pipeline deployments.

        Supports standard deployments (management account) and external pipeline deployments
        (CodePipeline or ECS container) identified by an Accelerator Qualifier.

        PARAMETERS:
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, downloads from
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
        - bucket_name (Optional[str]): Explicit bucket name override. Takes precedence over
          auto-detection.

        RECOMMENDED WORKFLOW:
        1. Run checkAwsConnectivity() to verify credentials and discover qualifiers
        2. Call getLzaConfiguration(qualifier=...) to download and extract configuration
        3. Use 'host_path' from the response to inspect/edit files
        4. Call putLzaConfiguration(qualifier=...) to upload changes (no path needed)
        5. Call startDeployment(qualifier=...) to deploy

        IMPORTANT: Use 'host_path' from the response to access files for inspection.
        The 'container_path' is internal Docker path only.

        NOTE: Automatic cleanup occurs on next retrieval to keep the file system clean.

        RETURNS: Dictionary with success, container_path, host_path, file/directory counts,
        structure, bucket_name, object_key, qualifier, and llm_instructions.""",
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
        return await lza_config_retrieval.get_configuration(ctx, qualifier, bucket_name)

    @mcp.tool(
        name="putLzaConfiguration",
        description="""Upload LZA configuration to S3 for both standard and external pipeline deployments.

        Supports standard deployments (management account) and external pipeline deployments
        (CodePipeline or ECS container) identified by an Accelerator Qualifier.

        PARAMETERS:
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, uploads to
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
        - config_path (Optional[str]): Path to config folder WITHIN the container.
          Leave empty to auto-detect from getLzaConfiguration().
        - bucket_name (Optional[str]): Explicit bucket name override.
        - offer_pipeline_release (bool): Whether to suggest startDeployment() after upload.

        IMPORTANT: This server runs in Docker. If you used getLzaConfiguration(), leave
        config_path empty — the tool auto-detects the retrieved configuration.

        RECOMMENDED WORKFLOW:
        1. getLzaConfiguration(qualifier=...) — download config
        2. Edit files via host_path
        3. putLzaConfiguration(qualifier=...) — upload (no path needed)
        4. startDeployment(qualifier=...) — deploy""",
    )  # nosemgrep: useless-inner-function
    async def put_lza_configuration(
        ctx: Context,
        qualifier: Optional[str] = None,
        config_path: Optional[str] = None,
        bucket_name: Optional[str] = None,
        offer_pipeline_release: bool = True,
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
            offer_pipeline_release: Whether to suggest startDeployment() after upload.
        """
        return await tool_put_lza_configuration(
            ctx, qualifier, config_path, bucket_name, offer_pipeline_release
        )

    @mcp.tool(
        name="readLzaConfigFile",
        description="Read a configuration file from the extracted LZA configuration directory",
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
        return await read_lza_config_file(ctx, file_path)

    @mcp.tool(
        name="updateLzaConfigFile",
        description="""Update an LZA configuration file in the extracted configuration directory.

        Supports three mutually exclusive modes:

        MODE 1 — Update existing values (use 'updates'):
            Modify existing key-value pairs using dot-notation paths with optional
            array index syntax. Also adds new keys if they don't exist yet.

        MODE 2 — Insert a new item into a list (use 'insert_path' + 'insert_value'):
            Append a new object to an existing YAML list, such as adding a new VPC
            to the 'vpcs' array or a new workload account.

        MODE 3 — Delete a key or list item (use 'delete_path'):
            Remove a key from a dict or an item from a list using dot-notation path.

        PARAMETERS:
        - file_path (str): Relative path to config file (e.g., "network-config.yaml"). Required.
        - updates (dict, optional): Key-value pairs to set. Keys use dot/index notation.
        - insert_path (str, optional): Dot-notation path to a list to append to.
        - insert_value (dict, optional): Object to append at insert_path.
        - delete_path (str, optional): Dot-notation path to the key or list item to remove.

        IMPORTANT: 'updates', 'insert_path'/'insert_value', and 'delete_path' are mutually exclusive.

        EXAMPLES:
            # Update existing values
            updateLzaConfigFile(file_path="network-config.yaml", updates={"vpcs[0].vpcName": "prod-vpc"})

            # Insert a new VPC
            updateLzaConfigFile(
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value={"vpcName": "dev-vpc", "account": "Development", "cidrs": [{"value": "10.3.0.0/16"}]}
            )

            # Add a new workload account
            updateLzaConfigFile(
                file_path="accounts-config.yaml",
                insert_path="workloadAccounts",
                insert_value={"name": "SharedServices", "email": "shared@example.com", "organizationalUnit": "Infrastructure"}
            )

            # Remove the third VPC
            updateLzaConfigFile(file_path="network-config.yaml", delete_path="vpcs[2]")

            # Remove an entire top-level key
            updateLzaConfigFile(file_path="network-config.yaml", delete_path="endpointPolicies")

        WORKFLOW: getLzaConfiguration() → readLzaConfigFile() → updateLzaConfigFile() → putLzaConfiguration() → startDeployment()""",
    )  # nosemgrep: useless-inner-function
    async def update_lza_config_file_tool(
        ctx: Context,
        file_path: str,
        updates: Optional[Dict[str, Any]] = None,
        insert_path: Optional[str] = None,
        insert_value: Optional[Dict[str, Any]] = None,
        delete_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await update_lza_config_file(
            ctx, file_path, updates, insert_path, insert_value, delete_path
        )

    @mcp.tool(
        name="createLzaConfigFile",
        description="""Create a new configuration file in the extracted LZA configuration directory.

        Creates YAML (.yaml, .yml) or JSON (.json) files based on the file extension.
        Useful for adding new policy files (JSON), custom configuration files, or
        any additional files needed by the LZA configuration.

        PARAMETERS:
        - file_path (str): Relative path for the new file. The extension determines
          the format (.yaml/.yml for YAML, .json for JSON). Required.
        - content (dict): Dictionary representing the file content to write. Required.
        - overwrite (bool): If True, overwrite an existing file. Defaults to False.
        - json_indent (int or str, optional): Indentation for JSON files. Accepts 2, 4,
          or "tab". Ignored for YAML files. Defaults to 2.

        EXAMPLES:
            # Create a JSON IAM policy file
            createLzaConfigFile(
                file_path="iam-policies/boundary-policy.json",
                content={
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
                }
            )

            # Create a YAML configuration file
            createLzaConfigFile(
                file_path="custom-config.yaml",
                content={"rules": [{"name": "require-tag", "enabled": True}]}
            )

            # Create a JSON file with tab indentation
            createLzaConfigFile(
                file_path="policy.json",
                content={"Version": "2012-10-17", "Statement": []},
                json_indent="tab"
            )

            # Create a JSON file with 4-space indentation
            createLzaConfigFile(
                file_path="policy.json",
                content={"Version": "2012-10-17", "Statement": []},
                json_indent=4
            )

        WORKFLOW: getLzaConfiguration() → createLzaConfigFile() → putLzaConfiguration() → startDeployment()""",
    )  # nosemgrep: useless-inner-function
    async def create_lza_config_file_tool(
        ctx: Context,
        file_path: str,
        content: Dict[str, Any],
        overwrite: bool = False,
        json_indent: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return await create_lza_config_file(
            ctx, file_path, content, overwrite, json_indent
        )

    logger.info("Configuration tools registered successfully")
