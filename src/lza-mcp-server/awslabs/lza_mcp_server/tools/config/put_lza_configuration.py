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

"""Upload LZA configuration to S3 for both standard and external pipeline deployments.

Supports:
  - Standard deployments (management account, no qualifier)
  - External pipeline deployments with qualifier (CodePipeline or ECS)

Bucket / key resolution is delegated to config_s3_resolver.
All file reads come from a workspace via WorkspaceManager.
"""

import io
import logging
import os
import tempfile
import zipfile
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.config.config_s3_resolver import (
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


async def _zip_workspace_files(
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    context: Any = None,
) -> bytes:
    """Read all files under *path* in the workspace and return ZIP bytes."""
    all_files = workspace_manager.list_files(workspace_id, context)

    # Filter to files under the requested path prefix
    prefix = path.rstrip("/") + "/" if path else ""
    matching_files = [f for f in all_files if f.startswith(prefix) or not prefix]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in matching_files:
            content = workspace_manager.read_file(workspace_id, file_path, context)
            # Archive name is relative to the base path
            arcname = file_path[len(prefix) :] if prefix else file_path
            zf.writestr(arcname, content)
    return buf.getvalue()


async def tool_put_lza_configuration(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    qualifier: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload LZA configuration from a workspace to S3.

    Reads files from the specified workspace and path, creates a ZIP archive,
    and uploads it to the appropriate S3 location.

    Args:
        ctx: MCP context for logging and progress.
        workspace_manager: WorkspaceManager instance for file operations.
        workspace_id: Workspace containing the configuration files.
        path: Relative path within the workspace where config files reside.
        qualifier: Accelerator Qualifier for external pipeline deployments.
                   Omit for standard (management account) deployments.
        bucket_name: Explicit bucket name override.

    Returns:
        Dictionary with upload results.
    """
    temp_zip_path: Optional[str] = None
    try:
        # Normalize root-equivalent paths to empty string
        if path in ("/", "."):
            path = ""

        await ctx.info("Starting LZA configuration upload...")

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
                        "Bucket names must be 3-63 characters, lowercase",
                        "Must start and end with a letter or number",
                    ],
                    context={"bucket_name": bucket_name},
                )

        # --- validate workspace ---
        try:
            workspace_manager.list_files(workspace_id, ctx)
        except WorkspaceNotFoundError:
            return create_structured_error_response(
                error="Workspace not found",
                category=ErrorCategory.CONFIGURATION,
                error_code="WORKSPACE_NOT_FOUND",
                troubleshooting=[
                    "Verify the workspace_id is correct",
                    "Use getLzaConfiguration() to download config into a workspace first",
                ],
                context={},
            )

        # --- verify workspace has config files ---
        all_files = workspace_manager.list_files(workspace_id, ctx)
        prefix = path.rstrip("/") + "/" if path else ""
        matching_files = [f for f in all_files if f.startswith(prefix) or not prefix]

        if not matching_files:
            return create_structured_error_response(
                error="No files found in workspace"
                + (f" at path '{path}'" if path else ""),
                category=ErrorCategory.CONFIGURATION,
                error_code="EMPTY_CONFIGURATION",
                troubleshooting=[
                    "Verify the workspace contains LZA configuration files",
                    "Use getLzaConfiguration() to download config first",
                    "Check the path parameter points to the correct location",
                ],
                context={"path": path},
            )

        # --- resolve S3 location ---
        identity = get_caller_identity()
        location = resolve_config_location(
            account_id=identity["account_id"],
            region=identity["region"],
            qualifier=qualifier,
            bucket_name_override=bucket_name,
        )

        await ctx.info(f"Target: s3://{location.bucket_name}/{location.object_key}")

        # --- create ZIP from workspace files ---
        await ctx.info(
            "Creating ZIP from workspace" + (f" path '{path}'" if path else "")
        )
        zip_bytes = await _zip_workspace_files(
            workspace_manager, workspace_id, path, ctx
        )

        # Write to temp file for S3Manager upload
        temp_zip_fd, temp_zip_path = tempfile.mkstemp(
            suffix=".zip", prefix="lza-config-upload-"
        )
        os.close(temp_zip_fd)
        with open(temp_zip_path, "wb") as f:
            f.write(zip_bytes)

        zip_size = len(zip_bytes)
        await ctx.info(f"ZIP created ({zip_size} bytes, {len(matching_files)} files)")

        # --- upload ---
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
            "bucket_name": location.bucket_name,
            "object_key": location.object_key,
            "qualifier": location.qualifier,
            "zip_size": zip_size,
            "file_count": len(matching_files),
            "upload_details": upload_result,
        }

    except (WorkspaceValidationError, WorkspaceStorageError) as e:
        logger.error("Workspace operation failed: %s", str(e))
        return create_structured_error_response(
            error=f"Workspace operation failed: {str(e)}",
            category=ErrorCategory.CONFIGURATION,
            error_code="WORKSPACE_ERROR",
            troubleshooting=[
                "Check workspace storage is accessible",
                "Verify workspace_id and path are valid",
            ],
            context={
                "path": path,
            },
        )
    except Exception as e:
        logger.error("putLzaConfiguration failed: %s", str(e))
        return create_structured_error_response(
            error=f"Upload failed: {str(e)}",
            category=ErrorCategory.INTEGRATION,
            error_code="UPLOAD_ERROR",
            troubleshooting=[
                "Check AWS credentials and S3 permissions",
                "Verify network connectivity",
            ],
            context={
                "qualifier": qualifier,
                "path": path,
                "bucket_name": bucket_name,
            },
        )
    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:  # nosec B110 - temp file cleanup is best-effort
                pass
