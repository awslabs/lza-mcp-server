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

"""S3 implementation for putLzaConfiguration.

Zips workspace files and uploads the archive to the LZA configuration S3 bucket.
"""

import io
import logging
import os
import tempfile
import zipfile
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.config.config_s3_resolver import (
    get_caller_identity,
    resolve_config_location,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


async def _zip_workspace_files(
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    matching_files: list,
    prefix: str,
    context: Any = None,
) -> bytes:
    """Read matching workspace files and return ZIP bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in matching_files:
            content = workspace_manager.read_file(workspace_id, file_path, context)
            arcname = file_path[len(prefix) :] if prefix else file_path
            zf.writestr(arcname, content)
    return buf.getvalue()


async def put_config_to_s3(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    matching_files: list,
    qualifier: Optional[str],
    bucket_name: Optional[str],
) -> Dict[str, Any]:
    """Zip workspace files and upload to S3.

    Args:
        ctx: MCP context for progress reporting.
        workspace_manager: WorkspaceManager instance for file operations.
        workspace_id: Workspace containing the configuration files.
        path: Relative path within the workspace (for response metadata).
        matching_files: List of workspace file paths to include in the ZIP.
        qualifier: Accelerator Qualifier for external pipeline deployments.
        bucket_name: Explicit S3 bucket name override.

    Returns:
        Dictionary with upload results and metadata.
    """
    temp_zip_path: Optional[str] = None
    prefix = path.rstrip("/") + "/" if path else ""

    try:
        identity = get_caller_identity()
        location = resolve_config_location(
            account_id=identity["account_id"],
            region=identity["region"],
            qualifier=qualifier,
            bucket_name_override=bucket_name,
        )

        await ctx.info(f"Target: s3://{location.bucket_name}/{location.object_key}")

        await ctx.info(
            "Creating ZIP from workspace" + (f" path '{path}'" if path else "")
        )
        zip_bytes = await _zip_workspace_files(
            workspace_manager, workspace_id, path, matching_files, prefix, ctx
        )

        temp_zip_fd, temp_zip_path = tempfile.mkstemp(
            suffix=".zip", prefix="lza-config-upload-"
        )
        os.close(temp_zip_fd)
        with open(temp_zip_path, "wb") as f:
            f.write(zip_bytes)

        zip_size = len(zip_bytes)
        await ctx.info(f"ZIP created ({zip_size} bytes, {len(matching_files)} files)")

        s3_manager = S3Manager()
        upload_result = await s3_manager.upload_zip_file(
            zip_path=temp_zip_path,
            bucket_name=location.bucket_name,
            key=location.object_key,
        )

        if not upload_result.get("success"):
            return upload_result

        await ctx.info(f"Uploaded to s3://{location.bucket_name}/{location.object_key}")

        return {
            "success": True,
            "message": "Configuration uploaded successfully",
            "workspace_id": workspace_id,
            "path": path,
            "config_source": "s3",
            "bucket_name": location.bucket_name,
            "object_key": location.object_key,
            "qualifier": location.qualifier,
            "zip_size": zip_size,
            "file_count": len(matching_files),
            "upload_details": upload_result,
        }

    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:  # nosec B110 - temp file cleanup is best-effort
                pass
