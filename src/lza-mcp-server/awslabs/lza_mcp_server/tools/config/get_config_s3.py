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

"""S3 Configuration Retrieval tools for the LZA MCP Server."""

import logging
import os
import re
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.common import categorize_aws_error
from awslabs.lza_mcp_server.constants import S3_OBJECT_KEY
from awslabs.lza_mcp_server.tools.uc_merge.common import set_extracted_lza_config_path

logger = logging.getLogger(__name__)


class S3ConfigRetrieval:
    """Handles retrieval and extraction of LZA configurations from S3."""

    def __init__(self):
        """Initialize with S3Manager and logging."""
        self.logger = logger
        self.s3_manager = S3Manager()
        self._temp_directories = {}  # Track temp dirs for cleanup
        self._last_temp_directory = None  # Track last created temp directory

    async def _cleanup_previous_temp_directory(self, ctx: Context) -> None:
        """
        Clean up previous temporary directory if it exists and wasn't manually cleaned.

        This ensures the temporary file system stays clean by automatically removing
        the previous temp directory before creating a new one.

        Args:
            ctx: MCP context for logging
        """
        if self._last_temp_directory and os.path.exists(self._last_temp_directory):
            try:
                await ctx.info(
                    f"Cleaning up previous temp directory: {self._last_temp_directory}"
                )
                shutil.rmtree(self._last_temp_directory)
                self.logger.info(
                    f"Automatically cleaned up previous temp directory: {self._last_temp_directory}"
                )

                # Remove from tracking
                if self._last_temp_directory in self._temp_directories:
                    del self._temp_directories[self._last_temp_directory]

            except Exception as e:
                self.logger.warning(
                    f"Failed to clean up previous temp directory: {str(e)}"
                )
                await ctx.warning(
                    f"Could not clean up previous temp directory: {str(e)}"
                )

    async def ensure_aws_connectivity(self, ctx: Context) -> Dict[str, Any]:
        """
        Ensure AWS connectivity has been verified.

        Args:
            ctx: MCP context for logging

        Returns:
            AWS connectivity status

        Raises:
            Exception if AWS connectivity not verified
        """
        try:
            session = get_aws_session()
            sts = session.client("sts")
            identity = sts.get_caller_identity()

            return {
                "success": True,
                "account_id": identity["Account"],
                "user_arn": identity["Arn"],
                "region": session.region_name,
            }
        except Exception as e:
            error_message = f"AWS connectivity check failed: {str(e)}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def _validate_bucket_name(self, bucket_name: str) -> Dict[str, Any]:
        """
        Validate bucket name format.

        Args:
            bucket_name: Bucket name to validate

        Returns:
            Dictionary with validation result and LLM-friendly error message if invalid
        """
        if not bucket_name:
            return {
                "valid": False,
                "error": "Bucket name cannot be empty.",
            }

        if len(bucket_name) < 3 or len(bucket_name) > 63:
            return {
                "valid": False,
                "error": f"The bucket name '{bucket_name}' is invalid. Bucket names must be 3-63 characters, lowercase, and follow AWS S3 naming rules.",
            }

        if not bucket_name.islower():
            return {
                "valid": False,
                "error": f"The bucket name '{bucket_name}' is invalid. Bucket names must be 3-63 characters, lowercase, and follow AWS S3 naming rules.",
            }

        # Check for invalid characters (basic check)
        if not re.match(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", bucket_name):
            return {
                "valid": False,
                "error": f"The bucket name '{bucket_name}' is invalid. Bucket names must be 3-63 characters, lowercase, and follow AWS S3 naming rules.",
            }

        return {"valid": True}

    async def get_configuration(
        self, ctx: Context, bucket_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get and extract LZA configuration from S3.

        Automatically cleans up previous temp directory before creating new one.
        Extracts configuration to Docker mounted volume location for LLM interaction.

        Args:
            ctx: MCP context for logging
            bucket_name: Optional custom bucket name (will be validated)

        Returns:
            Dictionary with extraction results and metadata
        """
        temp_zip_path = None
        temp_extract_path = None

        try:
            # Clean up previous temp directory automatically
            await self._cleanup_previous_temp_directory(ctx)

            # Validate custom bucket name if provided
            if bucket_name:
                validation_result = self._validate_bucket_name(bucket_name)
                if not validation_result["valid"]:
                    return create_structured_error_response(
                        error=validation_result["error"],
                        category=ErrorCategory.CONFIGURATION,
                        error_code="INVALID_BUCKET_NAME",
                        troubleshooting=[
                            "Ensure bucket name is 3-63 characters long",
                            "Use only lowercase letters, numbers, hyphens, and dots",
                            "Bucket name must start and end with a letter or number",
                            "Follow AWS S3 bucket naming rules",
                        ],
                        context={"bucket_name": bucket_name},
                    )

                # Verify custom bucket exists
                bucket_exists = await self.s3_manager.verify_bucket_exists(bucket_name)
                if not bucket_exists:
                    return create_structured_error_response(
                        error=f"Bucket '{bucket_name}' does not exist or is not accessible",
                        category=ErrorCategory.S3,
                        error_code="BUCKET_NOT_FOUND",
                        troubleshooting=[
                            f"Verify the bucket '{bucket_name}' exists in your AWS account",
                            "Check that you have access permissions to the bucket",
                            "Ensure the bucket is in the same region as your AWS session",
                            "Use checkAwsConnectivity() to verify your AWS credentials",
                        ],
                        context={"bucket_name": bucket_name},
                    )
            else:
                # Use default bucket name
                bucket_name = await self.s3_manager.determine_bucket_name()
                await ctx.info(f"Using default bucket: {bucket_name}")

                # Verify default bucket exists
                bucket_exists = await self.s3_manager.verify_bucket_exists(bucket_name)
                if not bucket_exists:
                    return create_structured_error_response(
                        error=f"Default bucket '{bucket_name}' does not exist",
                        category=ErrorCategory.S3,
                        error_code="DEFAULT_BUCKET_NOT_FOUND",
                        troubleshooting=[
                            f"Create the default bucket: aws s3 mb s3://{bucket_name}",
                            "Or provide a custom bucket name using the bucket_name parameter",
                            "Verify your AWS account ID and region are correct",
                            "Check that LZA has been deployed in this account/region",
                        ],
                        context={"bucket_name": bucket_name},
                    )

            await ctx.info(
                f"Downloading configuration from s3://{bucket_name}/{S3_OBJECT_KEY}"
            )

            # Create temporary file for ZIP download
            temp_zip_fd, temp_zip_path = tempfile.mkstemp(
                suffix=".zip", prefix="lza-config-download-"
            )
            os.close(temp_zip_fd)

            # Download ZIP file from S3
            try:
                s3_client = self.s3_manager._get_s3_client()
                s3_client.download_file(bucket_name, S3_OBJECT_KEY, temp_zip_path)
                self.logger.info(
                    f"Downloaded configuration from s3://{bucket_name}/{S3_OBJECT_KEY}"
                )
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "NoSuchKey":
                    return create_structured_error_response(
                        error=f"Configuration file not found at s3://{bucket_name}/{S3_OBJECT_KEY}",
                        category=ErrorCategory.S3,
                        error_code="OBJECT_NOT_FOUND",
                        troubleshooting=[
                            "Verify that LZA configuration has been deployed to this bucket",
                            f"Check that the file exists at {S3_OBJECT_KEY}",
                            "Ensure you have s3:GetObject permission for this bucket",
                            "Use the AWS Console or CLI to verify the object exists",
                        ],
                        context={
                            "bucket_name": bucket_name,
                            "object_key": S3_OBJECT_KEY,
                        },
                    )
                else:
                    error_info = categorize_aws_error(e)
                    return create_structured_error_response(
                        error=f"Failed to download configuration from S3: {str(e)}",
                        category=error_info["category"],
                        error_code=error_info["error_code"],
                        troubleshooting=error_info["troubleshooting"],
                        context={
                            "bucket_name": bucket_name,
                            "object_key": S3_OBJECT_KEY,
                            "operation": "s3_download",
                        },
                    )

            # Validate ZIP file
            if not zipfile.is_zipfile(temp_zip_path):
                return create_structured_error_response(
                    error="Downloaded file is not a valid ZIP archive",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_ZIP_FILE",
                    troubleshooting=[
                        "Verify the file at S3 is a valid ZIP archive",
                        "Check if the file was corrupted during upload",
                        "Try re-uploading the configuration to S3",
                        "Verify the file size matches expectations",
                    ],
                    context={
                        "bucket_name": bucket_name,
                        "object_key": S3_OBJECT_KEY,
                        "file_path": temp_zip_path,
                    },
                )

            # Create extraction directory in Docker mounted volume location
            # This allows the LLM to interact with the configuration files
            # The user maps their local directory to /app/lza-config in the container
            docker_share_path = "/app/lza-config"
            os.makedirs(docker_share_path, exist_ok=True)
            
            # Get the host path from environment variable (configured in MCP server settings)
            # This tells the LLM where to access files on the host system
            host_share_path = os.environ.get("LZA_CONFIG_HOST_PATH", "~/Documents/lza-config")
            
            # Create a subdirectory for this retrieval
            # IMPORTANT: Remove existing directory completely to avoid stale files from previous configs
            temp_extract_path = os.path.join(docker_share_path, "retrieved-config")
            if os.path.exists(temp_extract_path):
                self.logger.info(f"Removing existing configuration directory: {temp_extract_path}")
                shutil.rmtree(temp_extract_path)
            os.makedirs(temp_extract_path, exist_ok=True)
            
            # Calculate the host path where LLM can access the files
            host_extract_path = os.path.join(host_share_path, "retrieved-config")
            
            self.logger.info(f"Extracting configuration to {temp_extract_path}")
            await ctx.info(f"Extracting configuration to {temp_extract_path}")
            await ctx.info(f"LLM can access files at: {host_extract_path}")

            # Extract ZIP file
            try:
                with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                self.logger.info("Configuration extracted successfully")
            except Exception as e:
                return create_structured_error_response(
                    error=f"Failed to extract ZIP file: {str(e)}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="EXTRACTION_FAILED",
                    troubleshooting=[
                        "Verify the ZIP file is not corrupted",
                        "Check available disk space",
                        "Ensure file system permissions allow extraction",
                        "Try downloading the configuration again",
                    ],
                    context={
                        "bucket_name": bucket_name,
                        "object_key": S3_OBJECT_KEY,
                        "temp_directory": temp_extract_path,
                    },
                )

            # Track temp directory
            self._temp_directories[temp_extract_path] = {
                "bucket_name": bucket_name,
                "object_key": S3_OBJECT_KEY,
            }
            self._last_temp_directory = temp_extract_path
            
            # Set the extracted path for UC merge tools to use
            set_extracted_lza_config_path(Path(temp_extract_path))

            # Extract metadata
            metadata = self._extract_zip_metadata(temp_zip_path, temp_extract_path)

            # Build success response
            response = {
                "success": True,
                "container_path": temp_extract_path,
                "host_path": host_extract_path,
                "file_count": metadata["file_count"],
                "directory_count": metadata["directory_count"],
                "root_files": metadata["root_files"],
                "root_folders": metadata["root_folders"],
                "structure": metadata["structure"],
                "zip_size": metadata["zip_size"],
                "bucket_name": bucket_name,
                "object_key": S3_OBJECT_KEY,
                "message": "Configuration retrieved and extracted successfully",
                "llm_instructions": (
                    f"IMPORTANT - Configuration Workflow:\n"
                    f"1. Configuration has been extracted to the container workspace\n"
                    f"2. To inspect/edit files, use host_path with bash commands or file tools: {host_extract_path}\n"
                    f"3. After making changes, call uploadConfigurationToS3() WITHOUT any path parameter\n"
                    f"4. The upload tool will automatically detect and use this retrieved configuration\n"
                    f"5. DO NOT pass host_path or container_path to uploadConfigurationToS3()\n"
                    f"\n"
                    f"TYPICAL WORKFLOW:\n"
                    f"  - getConfigurationFromS3() ← You are here\n"
                    f"  - Edit files using bash/file tools at: {host_extract_path}\n"
                    f"  - uploadConfigurationToS3() ← NO PATH NEEDED\n"
                    f"  - releasePipeline() ← Deploy changes"
                ),
            }

            await ctx.info("✅ Configuration retrieved successfully")
            await ctx.info(f"Extracted {metadata['file_count']} files to {temp_extract_path}")
            await ctx.info(f"📁 Access files on host system at: {host_extract_path}")

            return response

        except Exception as e:
            self.logger.error(f"Unexpected error during configuration retrieval: {str(e)}")
            return create_structured_error_response(
                error=f"Unexpected error during configuration retrieval: {str(e)}",
                category=ErrorCategory.S3,
                error_code="UNEXPECTED_RETRIEVAL_ERROR",
                troubleshooting=[
                    "Check AWS credentials and permissions",
                    "Verify network connectivity to AWS S3",
                    "Ensure sufficient disk space for extraction",
                    "Check system resources and try again",
                ],
                context={
                    "bucket_name": bucket_name,
                    "object_key": S3_OBJECT_KEY,
                    "error_type": type(e).__name__,
                },
            )
        finally:
            # Clean up temporary ZIP file
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                    self.logger.info(f"Cleaned up temporary ZIP file: {temp_zip_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temporary ZIP file: {str(e)}")

    def _extract_zip_metadata(self, zip_path: str, extract_path: str) -> Dict[str, Any]:
        """
        Extract metadata about ZIP contents and extracted files.

        Args:
            zip_path: Path to ZIP file
            extract_path: Path where files were extracted

        Returns:
            Dictionary with file counts, directory structure, etc.
        """
        metadata = {
            "file_count": 0,
            "directory_count": 0,
            "root_files": [],
            "root_folders": [],
            "structure": {"root": {"files": [], "directories": {}}},
            "zip_size": 0,
        }

        try:
            # Get ZIP file size
            metadata["zip_size"] = os.path.getsize(zip_path)

            # Count files and directories
            for root, dirs, files in os.walk(extract_path):
                metadata["directory_count"] += len(dirs)
                metadata["file_count"] += len(files)

                # Get root-level items
                if root == extract_path:
                    metadata["root_files"] = sorted(files)
                    metadata["root_folders"] = sorted(dirs)

            # Build hierarchical structure (max depth: 2 levels for performance)
            root_structure = metadata["structure"]["root"]

            # Add root files
            root_structure["files"] = metadata["root_files"]

            # Add first level directories and their contents
            for folder in metadata["root_folders"]:
                folder_path = os.path.join(extract_path, folder)
                folder_structure = {"files": [], "directories": {}}

                if os.path.isdir(folder_path):
                    try:
                        items = os.listdir(folder_path)
                        for item in items:
                            item_path = os.path.join(folder_path, item)
                            if os.path.isfile(item_path):
                                folder_structure["files"].append(item)
                            elif os.path.isdir(item_path):
                                # Just list subdirectories, don't recurse further
                                folder_structure["directories"][item] = {
                                    "files": [],
                                    "directories": {},
                                }
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to read directory {folder_path}: {str(e)}"
                        )

                root_structure["directories"][folder] = folder_structure

        except Exception as e:
            self.logger.warning(f"Failed to extract complete metadata: {str(e)}")

        return metadata
