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

import os
import logging
from typing import Dict, Any
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.tools.validation.validate_configuration_share import (
    tool_validate_configuration_from_share,
)
from awslabs.lza_mcp_server.tools.validation.validation_configuration_s3 import (
    tool_validate_configuration_from_s3,
)

logger = logging.getLogger(__name__)


def register_validation_tools(mcp):
    """Register validation-related MCP tools."""

    @mcp.tool(name="validateConfigurationFromS3")  # nosemgrep: useless-inner-function
    async def validate_configuration_from_s3(
        ctx: Context,
        s3_path: str,
    ) -> Dict[str, Any]:
        return await tool_validate_configuration_from_s3(ctx, s3_path)

    @mcp.tool(
        name="validateConfigurationFromShare"
    )  # nosemgrep: useless-inner-function
    async def validate_configuration_from_share(
        ctx: Context, local_share_path: str = "~/Documents/lza-config"
    ) -> Dict[str, Any]:
        return await tool_validate_configuration_from_share(ctx, local_share_path)

    @mcp.tool(name="cleanupValidationZip")  # nosemgrep: useless-inner-function
    async def cleanup_validation_zip(
        ctx: Context, share_path: str = "~/Documents/lza-config"
    ) -> Dict[str, Any]:
        """
        Clean up the validation ZIP file from the share location.

        This tool allows manual cleanup of the config.zip file after successful
        upload to S3. Use this only after you've uploaded the configuration.

        Args:
            share_path (str, optional): Path to the share location (default: ~/Documents/lza-config)

        Returns:
            Dictionary containing cleanup result

        Example:
            ```python
            # Clean up after successful upload
            result = await cleanup_validation_zip(ctx)

            # Clean up from custom share location
            result = await cleanup_validation_zip(ctx, share_path="~/my-lza-config")
            ```
        """
        try:
            await ctx.info("🧹 Cleaning up validation ZIP file...")

            # Expand the share path
            expanded_path = os.path.expanduser(share_path)
            zip_file_path = os.path.join(expanded_path, "config.zip")

            if not os.path.exists(zip_file_path):
                await ctx.info(f"✅ ZIP file already cleaned up: {zip_file_path}")
                return {
                    "success": True,
                    "message": "ZIP file already cleaned up",
                    "zip_path": zip_file_path,
                    "existed": False,
                }

            # Remove the ZIP file
            os.remove(zip_file_path)
            await ctx.info(f"✅ Successfully cleaned up ZIP file: {zip_file_path}")

            return {
                "success": True,
                "message": "ZIP file cleaned up successfully",
                "zip_path": zip_file_path,
                "existed": True,
            }

        except Exception as e:
            error_message = f"Failed to clean up ZIP file: {str(e)}"
            await ctx.error(error_message)

            return {
                "success": False,
                "error": error_message,
                "zip_path": zip_file_path if "zip_file_path" in locals() else None,
                "troubleshooting": [
                    "Check that the share path is correct",
                    "Verify file system permissions",
                    "Ensure the ZIP file is not locked by another process",
                ],
            }

    logger.info("Validation tools registered successfully")
