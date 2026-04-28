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

"""S3 implementation for getLzaConfiguration.

Downloads the LZA configuration ZIP from S3 and extracts it into a workspace.
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
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


async def get_config_from_s3(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    s3_manager: S3Manager,
    workspace_id: str,
    created_workspace: bool,
    path: Optional[str],
    qualifier: Optional[str],
    bucket_name: Optional[str],
) -> Dict[str, Any]:
    """Download config ZIP from S3 and extract it into the workspace.

    Args:
        ctx: MCP context for progress reporting.
        workspace_manager: WorkspaceManager instance for file operations.
        s3_manager: S3Manager instance for S3 operations.
        workspace_id: Target workspace to extract files into.
        created_workspace: Whether the workspace was created by this call.
        path: Optional base path within the workspace to extract files under.
        qualifier: Accelerator Qualifier for external pipeline deployments.
        bucket_name: Explicit S3 bucket name override.

    Returns:
        Dictionary with extraction results, workspace_id, and metadata.
    """
    temp_zip_path: Optional[str] = None

    try:
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
        bucket_exists = await s3_manager.verify_bucket_exists(location.bucket_name)
        if not bucket_exists:
            return create_structured_error_response(
                error="Configuration bucket does not exist or is not accessible",
                category=ErrorCategory.S3,
                error_code="BUCKET_NOT_FOUND",
                troubleshooting=[
                    "Verify the S3 bucket exists in your AWS account",
                    "Check IAM permissions (s3:ListBucket, s3:GetObject)",
                    "Ensure the bucket is in the correct region",
                    "Run checkAwsConnectivity() to verify credentials and deployment type",
                ],
                context={},
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
            s3_client = s3_manager._get_s3_client()
            s3_client.download_file(
                location.bucket_name, location.object_key, temp_zip_path
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                return create_structured_error_response(
                    error="Configuration archive not found in S3",
                    category=ErrorCategory.S3,
                    error_code="OBJECT_NOT_FOUND",
                    troubleshooting=[
                        "Verify LZA has been deployed and configuration uploaded",
                        "Ensure s3:GetObject permission is granted",
                    ],
                    context={},
                )
            error_info = categorize_aws_error(e)
            return create_structured_error_response(
                error=f"S3 download failed: {str(e)}",
                category=error_info["category"],
                error_code=error_info["error_code"],
                troubleshooting=error_info["troubleshooting"],
                context={},
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
                context={},
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
                    folder_path = (
                        posixpath.join(base_path, info.filename)
                        if base_path
                        else info.filename
                    )
                    folder_path = folder_path.rstrip("/")
                    if folder_path:
                        workspace_manager.create_folder(workspace_id, folder_path, ctx)
                    continue

                file_count += 1
                file_data = zf.read(info.filename)
                ws_file_path = (
                    posixpath.join(base_path, info.filename)
                    if base_path
                    else info.filename
                )
                workspace_manager.write_file(workspace_id, ws_file_path, file_data, ctx)

                top_level = info.filename.split("/")[0]
                if "/" not in info.filename:
                    root_files.append(info.filename)
                else:
                    root_folders.add(top_level)

        root_files = sorted(root_files)
        root_folders_list = sorted(root_folders)

        await ctx.info(f"Extracted {file_count} files into workspace {workspace_id}")

        directories: dict[str, dict[str, list[str] | dict[str, Any]]] = {}
        structure: dict[str, Any] = {
            "root": {"files": root_files, "directories": directories}
        }
        for folder in root_folders_list:
            structure["root"]["directories"][folder] = {"files": [], "directories": {}}

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
            "config_source": "s3",
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
                + "\n\n"
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

    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:  # nosec B110 - temp file cleanup is best-effort
                pass
