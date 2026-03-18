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

"""Retrieve LZA configuration from S3 for both standard and external pipeline deployments.

Supports:
  - Standard deployments (management account, no qualifier)
  - External pipeline deployments with qualifier (CodePipeline or ECS)

Bucket / key resolution is delegated to config_s3_resolver so the naming
rules live in one place.
"""

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.aws_services.common import categorize_aws_error
from awslabs.lza_mcp_server.tools.config.config_s3_resolver import (
    ConfigS3Location,
    get_caller_identity,
    resolve_config_location,
)
from awslabs.lza_mcp_server.tools.pipeline.common import validate_qualifier
from awslabs.lza_mcp_server.tools.uc_merge.common import set_extracted_lza_config_path
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import validate_s3_bucket_name

logger = logging.getLogger(__name__)


class LzaConfigRetrieval:
    """Retrieve and extract LZA configuration from S3.

    Handles both standard and external pipeline (qualifier-based) deployments.
    Manages temp directory lifecycle so each retrieval starts clean.
    """

    def __init__(self) -> None:
        self.logger = logger
        self.s3_manager = S3Manager()
        self._last_temp_directory: Optional[str] = None

    # ------------------------------------------------------------------
    # Temp directory management
    # ------------------------------------------------------------------

    async def _cleanup_previous(self, ctx: Context) -> None:
        """Remove the temp directory from the previous retrieval, if any."""
        if self._last_temp_directory and os.path.exists(self._last_temp_directory):
            try:
                await ctx.info(
                    f"Cleaning up previous config directory: {self._last_temp_directory}"
                )
                shutil.rmtree(self._last_temp_directory)
                self.logger.info(
                    "Cleaned up previous temp directory: %s", self._last_temp_directory
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to clean up previous temp directory: %s", str(e)
                )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def get_configuration(
        self,
        ctx: Context,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Download and extract LZA configuration from S3.

        Args:
            ctx: MCP context for progress reporting.
            qualifier: Accelerator Qualifier for external pipeline deployments.
                       Omit for standard (management account) deployments.
            bucket_name: Explicit bucket name override. When omitted the bucket
                         is derived from the deployment type and qualifier.

        Returns:
            Dictionary with extraction results, paths, and metadata.
        """
        temp_zip_path: Optional[str] = None

        try:
            await self._cleanup_previous(ctx)

            # --- input validation ---
            if qualifier:
                is_valid, err = validate_qualifier(qualifier)
                if not is_valid:
                    return create_structured_error_response(
                        error=f"Invalid qualifier: {err}",
                        category=ErrorCategory.CONFIGURATION,
                        error_code="INVALID_QUALIFIER",
                        troubleshooting=[
                            "Qualifier must contain only lowercase letters, numbers, and hyphens",
                            "Run checkAwsConnectivity() to see available qualifiers",
                        ],
                        context={"qualifier": qualifier},
                    )

            if bucket_name:
                is_valid, err = validate_s3_bucket_name(bucket_name)
                if not is_valid:
                    return create_structured_error_response(
                        error=f"Invalid bucket name: {err}",
                        category=ErrorCategory.CONFIGURATION,
                        error_code="INVALID_BUCKET_NAME",
                        troubleshooting=[
                            "Bucket names must be 3-63 characters, lowercase, no spaces",
                            "Must start and end with a letter or number",
                        ],
                        context={"bucket_name": bucket_name},
                    )

            # --- resolve S3 location ---
            await ctx.info("Resolving S3 configuration location...")
            identity = get_caller_identity()
            location: ConfigS3Location = resolve_config_location(
                account_id=identity["account_id"],
                region=identity["region"],
                qualifier=qualifier,
                bucket_name_override=bucket_name,
            )

            await ctx.info(f"Target: s3://{location.bucket_name}/{location.object_key}")
            if qualifier:
                await ctx.info(f"Qualifier: {qualifier}")

            # --- verify bucket ---
            bucket_exists = await self.s3_manager.verify_bucket_exists(
                location.bucket_name
            )
            if not bucket_exists:
                return create_structured_error_response(
                    error=f"Bucket '{location.bucket_name}' does not exist or is not accessible",
                    category=ErrorCategory.S3,
                    error_code="BUCKET_NOT_FOUND",
                    troubleshooting=[
                        f"Verify the bucket '{location.bucket_name}' exists in your AWS account",
                        "Check IAM permissions (s3:ListBucket, s3:GetObject)",
                        "Ensure the bucket is in the correct region",
                        "Run checkAwsConnectivity() to verify credentials and deployment type",
                    ],
                    context={
                        "bucket_name": location.bucket_name,
                        "qualifier": qualifier,
                    },
                )

            # --- download ZIP ---
            await ctx.info(
                f"Downloading s3://{location.bucket_name}/{location.object_key} ..."
            )
            temp_zip_fd, temp_zip_path = tempfile.mkstemp(
                suffix=".zip", prefix="lza-config-download-"
            )
            os.close(temp_zip_fd)

            try:
                s3_client = self.s3_manager._get_s3_client()
                s3_client.download_file(
                    location.bucket_name, location.object_key, temp_zip_path
                )
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "NoSuchKey":
                    return create_structured_error_response(
                        error=f"Configuration not found at s3://{location.bucket_name}/{location.object_key}",
                        category=ErrorCategory.S3,
                        error_code="OBJECT_NOT_FOUND",
                        troubleshooting=[
                            "Verify LZA has been deployed and configuration uploaded",
                            f"Check that the object exists at key '{location.object_key}'",
                            "Ensure s3:GetObject permission is granted",
                        ],
                        context={
                            "bucket_name": location.bucket_name,
                            "object_key": location.object_key,
                            "qualifier": qualifier,
                        },
                    )
                error_info = categorize_aws_error(e)
                return create_structured_error_response(
                    error=f"S3 download failed: {str(e)}",
                    category=error_info["category"],
                    error_code=error_info["error_code"],
                    troubleshooting=error_info["troubleshooting"],
                    context={
                        "bucket_name": location.bucket_name,
                        "object_key": location.object_key,
                    },
                )

            # --- validate ZIP ---
            if not zipfile.is_zipfile(temp_zip_path):
                return create_structured_error_response(
                    error="Downloaded file is not a valid ZIP archive",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_ZIP_FILE",
                    troubleshooting=[
                        "Verify the S3 object is a valid ZIP archive",
                        "The file may have been corrupted during upload",
                    ],
                    context={
                        "bucket_name": location.bucket_name,
                        "object_key": location.object_key,
                    },
                )

            # --- extract ---
            docker_share_path = os.environ.get(
                "LZA_CONFIG_BASE_PATH", "/app/lza-config"
            )
            os.makedirs(docker_share_path, exist_ok=True)
            host_share_path = os.environ.get(
                "LZA_CONFIG_HOST_PATH", "~/Documents/lza-config"
            )

            extract_path = os.path.join(docker_share_path, "retrieved-config")
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
            os.makedirs(extract_path, exist_ok=True)

            host_extract_path = os.path.join(host_share_path, "retrieved-config")

            await ctx.info(f"Extracting to {extract_path}")
            with zipfile.ZipFile(temp_zip_path, "r") as zf:
                zf.extractall(extract_path)

            self._last_temp_directory = extract_path
            set_extracted_lza_config_path(Path(extract_path))

            metadata = self._extract_metadata(temp_zip_path, extract_path)

            await ctx.info(f"Extracted {metadata['file_count']} files")
            await ctx.info(f"Access files at: {host_extract_path}")

            return {
                "success": True,
                "container_path": extract_path,
                "host_path": host_extract_path,
                "file_count": metadata["file_count"],
                "directory_count": metadata["directory_count"],
                "root_files": metadata["root_files"],
                "root_folders": metadata["root_folders"],
                "structure": metadata["structure"],
                "zip_size": metadata["zip_size"],
                "bucket_name": location.bucket_name,
                "object_key": location.object_key,
                "qualifier": qualifier,
                "message": "Configuration retrieved and extracted successfully",
                "llm_instructions": (
                    f"IMPORTANT - Configuration Workflow:\n"
                    f"1. Configuration has been extracted to the container workspace\n"
                    f"2. To inspect/edit files, use host_path: {host_extract_path}\n"
                    f"3. After making changes, call putLzaConfiguration()"
                    f"{' with qualifier=' + repr(qualifier) if qualifier else ''}"
                    f" — NO path parameter needed\n"
                    f"4. The upload tool will automatically detect the retrieved configuration\n"
                    f"\n"
                    f"TYPICAL WORKFLOW:\n"
                    f"  - getLzaConfiguration() ← You are here\n"
                    f"  - Edit files at: {host_extract_path}\n"
                    f"  - putLzaConfiguration()"
                    f"{' qualifier=' + repr(qualifier) if qualifier else ''}\n"
                    f"  - startDeployment()"
                    f"{' qualifier=' + repr(qualifier) if qualifier else ''}"
                ),
            }

        except Exception as e:
            self.logger.error("Configuration retrieval failed: %s", str(e))
            return create_structured_error_response(
                error=f"Configuration retrieval failed: {str(e)}",
                category=ErrorCategory.S3,
                error_code="RETRIEVAL_ERROR",
                troubleshooting=[
                    "Check AWS credentials and permissions",
                    "Verify network connectivity to S3",
                    "Ensure sufficient disk space",
                ],
                context={
                    "qualifier": qualifier,
                    "bucket_name": bucket_name,
                    "error_type": type(e).__name__,
                },
            )
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except Exception:  # nosec B110 - temp file cleanup is best-effort
                    pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_metadata(self, zip_path: str, extract_path: str) -> Dict[str, Any]:
        """Build metadata dict from extracted config directory."""
        metadata: Dict[str, Any] = {
            "file_count": 0,
            "directory_count": 0,
            "root_files": [],
            "root_folders": [],
            "structure": {"root": {"files": [], "directories": {}}},
            "zip_size": 0,
        }
        try:
            metadata["zip_size"] = os.path.getsize(zip_path)
            for root, dirs, files in os.walk(extract_path):
                metadata["directory_count"] += len(dirs)
                metadata["file_count"] += len(files)
                if root == extract_path:
                    metadata["root_files"] = sorted(files)
                    metadata["root_folders"] = sorted(dirs)

            root_structure: dict = metadata["structure"]["root"]
            root_structure["files"] = metadata["root_files"]
            for folder in metadata["root_folders"]:
                folder_path = os.path.join(extract_path, folder)
                folder_structure: Dict[str, Any] = {"files": [], "directories": {}}
                if os.path.isdir(folder_path):
                    for item in os.listdir(folder_path):
                        item_path = os.path.join(folder_path, item)
                        if os.path.isfile(item_path):
                            folder_structure["files"].append(item)
                        elif os.path.isdir(item_path):
                            folder_structure["directories"][item] = {
                                "files": [],
                                "directories": {},
                            }
                root_structure["directories"][folder] = folder_structure
        except Exception as e:
            self.logger.warning("Metadata extraction incomplete: %s", str(e))
        return metadata
