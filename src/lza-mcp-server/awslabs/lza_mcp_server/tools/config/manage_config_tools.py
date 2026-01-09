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
from awslabs.lza_mcp_server.tools.config.get_config_s3 import (
    S3ConfigRetrieval,
)

logger = logging.getLogger(__name__)


def register_config_tools(mcp):
    """Register configuration-related MCP tools."""

    # Initialize S3ConfigRetrieval instance for the retrieve tool
    s3_config_retrieval = S3ConfigRetrieval()

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

    @mcp.tool(
        name="getConfigurationFromS3",
        description="""Retrieve current LZA configuration ZIP from S3 and extract to Docker mounted volume. 
        
        PARAMETERS:
        - bucket_name (Optional[str]): Custom S3 bucket name. If not provided, uses default: aws-accelerator-config-{account_id}-{region}
        
        RECOMMENDED WORKFLOW:
        1. Run checkAwsConnectivity() first to verify AWS credentials
        2. Call getConfigurationFromS3(bucket_name=None) to download and extract configuration
        3. Use the 'host_path' from the response to inspect configuration files with readFile or other tools
        
        IMPORTANT: Use 'host_path' from the response to access files for inspection. The 'container_path' is internal Docker path only.
        
        NOTE: Automatic cleanup occurs on next retrieval to keep the file system clean.
        
        RETURNS: Dictionary with success status, container_path, host_path (use this!), file_count, directory_count, root_files, root_folders, structure, zip_size, bucket_name, object_key, and llm_instructions.""",
    )  # nosemgrep: useless-inner-function
    async def get_configuration_from_s3(
        ctx: Context,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve current LZA configuration ZIP from S3 and extract to Docker mounted volume.

        This tool downloads the configuration from the standard LZA S3 location
        (zipped/aws-accelerator-config.zip) and extracts it to the Docker mounted volume.

        IMPORTANT FOR LLM: Use the 'host_path' from the response to access and inspect files.
        The 'container_path' is the internal Docker path, while 'host_path' is where you can
        actually read the files on the local system.

        The tool automatically cleans up the previous retrieved configuration before creating
        a new one to keep the file system clean.

        RECOMMENDED WORKFLOW:
        1. Run checkAwsConnectivity() first to verify AWS credentials (recommended)
        2. Call getConfigurationFromS3() to download and extract configuration
        3. Use the 'host_path' from the response to inspect configuration files

        NOTE: Automatic cleanup will occur on next retrieval to keep the file system clean

        Args:
            bucket_name: Optional custom bucket name. If not provided, uses
                        aws-accelerator-config-{account_id}-{region}

        Returns:
            Dictionary containing:
            - success: Boolean indicating operation success
            - container_path: Path inside Docker container (/app/lza-config/retrieved-config)
            - host_path: Path on host system where LLM can access files (use this for inspection!)
            - file_count: Total number of files extracted
            - directory_count: Total number of directories
            - root_files: List of files in root directory
            - root_folders: List of folders in root directory
            - structure: Hierarchical view of configuration
            - zip_size: Size of downloaded ZIP in bytes
            - bucket_name: Bucket used for retrieval
            - object_key: S3 object key used
            - llm_instructions: Specific instructions for LLM on how to access files
        """
        return await s3_config_retrieval.get_configuration(ctx, bucket_name)

    logger.info("Configuration tools registered successfully")
