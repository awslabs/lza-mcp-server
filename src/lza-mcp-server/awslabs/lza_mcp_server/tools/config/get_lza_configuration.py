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

Downloaded configuration is extracted into a workspace managed by
WorkspaceManager, replacing the previous temp-directory approach.
"""

import logging
import os
import posixpath
import tempfile
import zipfile
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
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import validate_s3_bucket_name
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)

logger = logging.getLogger(__name__)


class LzaConfigRetrieval:
    """Retrieve and extract LZA configuration from S3 into a workspace.

    Handles both standard and external pipeline (qualifier-based) deployments.
    Uses WorkspaceManager for all file operations.
    """

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        self.logger = logger
        self.s3_manager = S3Manager()
        self._workspace_manager = workspace_manager

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def get_configuration(
        self,
        ctx: Context,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Download and extract LZA configuration from S3 into a workspace.

        Args:
            ctx: MCP context for progress reporting.
            qualifier: Accelerator Qualifier for external pipeline deployments.
                       Omit for standard (management account) deployments.
            bucket_name: Explicit bucket name override. When omitted the bucket
                         is derived from the deployment type and qualifier.
            workspace_id: Optional workspace ID. If omitted a new workspace is
                          created automatically.
            path: Optional relative path within the workspace to extract into.
                  Defaults to the workspace root.

        Returns:
            Dictionary with extraction results, workspace_id, paths, and metadata.
        """
        temp_zip_path: Optional[str] = None
        created_workspace = False

        try:
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

            # --- workspace resolution ---
            if workspace_id:
                try:
                    self._workspace_manager.list_files(workspace_id, ctx)
                except WorkspaceNotFoundError:
                    return create_structured_error_response(
                        error="Workspace not found",
                        category=ErrorCategory.CONFIGURATION,
                        error_code="WORKSPACE_NOT_FOUND",
                        troubleshooting=[
                            "Verify the workspace_id is correct",
                            "Use createWorkspace() to create a new workspace first",
                        ],
                        context={"workspace_id": workspace_id},
                    )
            else:
                workspace_id = self._workspace_manager.create_workspace(ctx)
                created_workspace = True
                await ctx.info(f"Created new workspace: {workspace_id}")

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

            # --- extract into workspace ---
            base_path = path or ""
            await ctx.info(
                f"Extracting into workspace {workspace_id}"
                + (f" at path '{base_path}'" if base_path else "")
            )

            zip_size = os.path.getsize(temp_zip_path)
            file_count = 0
            directory_count = 0
            root_files: list[str] = []
            root_folders: set[str] = set()

            with zipfile.ZipFile(temp_zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        directory_count += 1
                        # Create the folder in the workspace
                        folder_path = (
                            posixpath.join(base_path, info.filename)
                            if base_path
                            else info.filename
                        )
                        # Strip trailing slash for folder creation
                        folder_path = folder_path.rstrip("/")
                        if folder_path:
                            self._workspace_manager.create_folder(
                                workspace_id, folder_path, ctx
                            )
                        continue

                    file_count += 1
                    file_data = zf.read(info.filename)
                    ws_file_path = (
                        posixpath.join(base_path, info.filename)
                        if base_path
                        else info.filename
                    )
                    self._workspace_manager.write_file(
                        workspace_id, ws_file_path, file_data, ctx
                    )

                    # Track root-level entries for metadata
                    top_level = info.filename.split("/")[0]
                    if "/" not in info.filename:
                        root_files.append(info.filename)
                    else:
                        root_folders.add(top_level)

            root_files = sorted(root_files)
            root_folders_list = sorted(root_folders)

            await ctx.info(
                f"Extracted {file_count} files into workspace {workspace_id}"
            )

            # Build structure metadata
            directories: dict[str, dict[str, list[str] | dict[str, Any]]] = {}
            structure: dict[str, Any] = {
                "root": {"files": root_files, "directories": directories}
            }
            for folder in root_folders_list:
                structure["root"]["directories"][folder] = {
                    "files": [],
                    "directories": {},
                }

            return {
                "success": True,
                "workspace_id": workspace_id,
                "workspace_created": created_workspace,
                "path": base_path or "/",
                "file_count": file_count,
                "directory_count": directory_count,
                "root_files": root_files,
                "root_folders": root_folders_list,
                "structure": structure,
                "zip_size": zip_size,
                "bucket_name": location.bucket_name,
                "object_key": location.object_key,
                "qualifier": qualifier,
                "message": "Configuration retrieved and extracted into workspace successfully",
                "llm_instructions": (
                    f"IMPORTANT - Configuration Workflow:\n"
                    f"1. Configuration has been extracted into workspace '{workspace_id}'"
                    + (f" at path '{base_path}'" if base_path else "")
                    + "\n"
                    f"2. Use readLzaConfigFile or workspace tools to inspect/edit files\n"
                    f"3. After making changes, call putLzaConfiguration("
                    f"workspace_id='{workspace_id}'"
                    + (f", path='{base_path}'" if base_path else "")
                    + (f", qualifier={repr(qualifier)}" if qualifier else "")
                    + ")\n"
                    "4. Then call startDeployment()"
                    + (f" with qualifier={repr(qualifier)}" if qualifier else "")
                    + "\n"
                    f"\n"
                    f"TYPICAL WORKFLOW:\n"
                    f"  - getLzaConfiguration() ← You are here\n"
                    f"  - Edit files in workspace '{workspace_id}'\n"
                    f"  - putLzaConfiguration("
                    f"workspace_id='{workspace_id}'"
                    + (f", path='{base_path}'" if base_path else "")
                    + (f", qualifier={repr(qualifier)}" if qualifier else "")
                    + ")\n"
                    "  - startDeployment()"
                    + (f" qualifier={repr(qualifier)}" if qualifier else "")
                ),
            }

        except (WorkspaceValidationError, WorkspaceStorageError) as e:
            self.logger.error("Workspace operation failed: %s", str(e))
            return create_structured_error_response(
                error=f"Workspace operation failed: {str(e)}",
                category=ErrorCategory.CONFIGURATION,
                error_code="WORKSPACE_ERROR",
                troubleshooting=[
                    "Check workspace storage is accessible",
                    "Verify workspace_id is valid",
                ],
                context={
                    "workspace_id": workspace_id,
                    "path": path,
                },
            )
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
                    "workspace_id": workspace_id,
                    "error_type": type(e).__name__,
                },
            )
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except Exception:  # nosec B110 - temp file cleanup is best-effort
                    pass
