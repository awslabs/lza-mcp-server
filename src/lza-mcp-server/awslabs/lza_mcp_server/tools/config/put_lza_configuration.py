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
"""

import logging
import os
import tempfile
import zipfile
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.tools.config.config_s3_resolver import (
    ConfigS3Location,
    get_caller_identity,
    resolve_config_location,
)
from awslabs.lza_mcp_server.tools.pipeline.common import validate_qualifier
from awslabs.lza_mcp_server.tools.uc_merge.common import get_extracted_lza_config_path
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_file_path,
    validate_s3_bucket_name,
)

logger = logging.getLogger(__name__)


async def _detect_retrieved_config() -> Dict[str, Any]:
    """Check whether getLzaConfiguration() left an extracted config directory."""
    try:
        extracted_path = get_extracted_lza_config_path()
        if (
            extracted_path
            and os.path.exists(str(extracted_path))
            and os.path.isdir(str(extracted_path))
        ):
            required = ["accounts-config.yaml", "global-config.yaml"]
            has_files = all(
                os.path.exists(os.path.join(str(extracted_path), f)) for f in required
            )
            if has_files:
                return {"detected": True, "config_path": str(extracted_path)}
        return {"detected": False}
    except Exception:
        return {"detected": False}


async def _zip_and_upload(
    ctx: Context,
    config_path: str,
    location: ConfigS3Location,
) -> Dict[str, Any]:
    """Create a ZIP from *config_path* and upload it to *location*."""
    temp_zip_path: Optional[str] = None
    try:
        await ctx.info(f"Creating ZIP from: {config_path}")
        temp_zip_fd, temp_zip_path = tempfile.mkstemp(
            suffix=".zip", prefix="lza-config-upload-"
        )
        os.close(temp_zip_fd)

        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(config_path):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, config_path)
                    zf.write(full, arcname)

        zip_size = os.path.getsize(temp_zip_path)
        await ctx.info(f"ZIP created ({zip_size} bytes)")

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
            "bucket_name": location.bucket_name,
            "object_key": location.object_key,
            "qualifier": location.qualifier,
            "zip_size": zip_size,
            "config_path": config_path,
            "upload_details": upload_result,
        }

    except Exception as e:
        logger.error("Upload failed: %s", str(e))
        return create_structured_error_response(
            error=f"Upload failed: {str(e)}",
            category=ErrorCategory.INTEGRATION,
            error_code="UPLOAD_ERROR",
            troubleshooting=[
                "Check AWS credentials and S3 permissions",
                "Verify network connectivity",
                "Ensure configuration files are valid",
            ],
            context={
                "config_path": config_path,
                "bucket_name": location.bucket_name,
                "object_key": location.object_key,
            },
        )
    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception:  # nosec B110 - temp file cleanup is best-effort
                pass


async def tool_put_lza_configuration(
    ctx: Context,
    qualifier: Optional[str] = None,
    config_path: Optional[str] = None,
    bucket_name: Optional[str] = None,
    offer_pipeline_release: bool = True,
) -> Dict[str, Any]:
    """Upload LZA configuration to S3.

    Supports both standard and external pipeline (qualifier-based) deployments.

    IMPORTANT - Docker Container Context:
    This MCP server runs inside a Docker container.
    - If you retrieved config with getLzaConfiguration(), leave config_path EMPTY.
    - The tool will automatically find and use the retrieved configuration.
    - DO NOT pass host paths (e.g. /Users/...) — they are not accessible.

    Args:
        ctx: MCP context for logging and progress.
        qualifier: Accelerator Qualifier for external pipeline deployments.
                   Omit for standard (management account) deployments.
                   When provided, uploads to {qualifier}-config-{account}-{region}
                   with key lza/aws-accelerator-config.zip.
        config_path: Optional path to configuration folder WITHIN the container.
                     Leave empty to auto-detect from getLzaConfiguration().
        bucket_name: Explicit bucket name override.
        offer_pipeline_release: Whether to suggest startDeployment() after upload.

    Returns:
        Dictionary with upload results.

    TYPICAL WORKFLOW:
        1. checkAwsConnectivity() — verify credentials
        2. getLzaConfiguration(qualifier=...) — download config
        3. Edit files via host_path
        4. putLzaConfiguration(qualifier=...) — upload (no path needed)
        5. startDeployment(qualifier=...) — deploy
    """
    try:
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

        if config_path:
            is_valid, err = validate_file_path(config_path, allow_absolute=False)
            if not is_valid:
                return create_structured_error_response(
                    error=f"Invalid config_path: {err}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_CONFIG_PATH",
                    troubleshooting=[
                        "Provide a relative path within the container",
                        "If you used getLzaConfiguration(), leave config_path empty",
                    ],
                    context={"config_path": config_path},
                )

        # Reject host paths (common mistake)
        if config_path and (
            config_path.startswith("/Users/") or config_path.startswith("~/")
        ):
            return create_structured_error_response(
                error=(
                    f"'{config_path}' is a host path. This server runs in Docker and "
                    "cannot access host paths. Call putLzaConfiguration() without "
                    "config_path to auto-detect the retrieved configuration."
                ),
                category=ErrorCategory.CONFIGURATION,
                error_code="HOST_PATH_PROVIDED",
                troubleshooting=[
                    "Remove the config_path parameter",
                    "The tool auto-detects config from getLzaConfiguration()",
                ],
                context={"config_path": config_path},
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

        # --- auto-detect retrieved config ---
        if not config_path:
            detected = await _detect_retrieved_config()
            if detected["detected"]:
                await ctx.info(
                    f"Using config from getLzaConfiguration(): {detected['config_path']}"
                )
                result = await _zip_and_upload(ctx, detected["config_path"], location)
                if result.get("success") and offer_pipeline_release:
                    qualifier_hint = f" qualifier={qualifier!r}" if qualifier else ""
                    await ctx.info(f"Use startDeployment({qualifier_hint}) to deploy")
                return result

        # --- direct upload via S3UploadUtils ---
        if config_path:
            await ctx.info(f"Uploading from container path: {config_path}")
        else:
            await ctx.info("Discovering configuration in workspace...")

        upload_tool = S3UploadUtils()
        result = await upload_tool.upload_configuration(
            ctx=ctx,
            config_path=config_path,
            bucket_name=location.bucket_name,
            offer_pipeline_release=offer_pipeline_release,
        )
        return result

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
                "config_path": config_path,
                "bucket_name": bucket_name,
            },
        )
