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

"""S3 Configuration Upload tools for the LZA MCP Server."""

import logging
import os
import tempfile
import zipfile
from typing import Dict, Any, Optional

# MCP framework components
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.tools.config.common import (
    ErrorCategory,
)
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_file_path,
    validate_s3_bucket_name,
)
from awslabs.lza_mcp_server.tools.uc_merge.common import get_extracted_lza_config_path

logger = logging.getLogger(__name__)

# S3 Configuration constants
S3_OBJECT_KEY = "zipped/aws-accelerator-config.zip"
BUCKET_NAME_PATTERN = "aws-accelerator-config-{account_id}-{region}"


async def _detect_retrieved_config_context(ctx: Context) -> Dict[str, Any]:
    """
    Detect if getConfigurationFromS3() was recently used by checking for extracted config.

    This checks for the extracted configuration directory created by getConfigurationFromS3().

    Returns:
        Dict with detection result and retrieved config context
    """
    try:
        # Check if extracted config path is set
        extracted_path = get_extracted_lza_config_path()

        if (
            extracted_path
            and os.path.exists(extracted_path)
            and os.path.isdir(extracted_path)
        ):
            import time

            # Check directory age
            dir_age = time.time() - os.path.getmtime(extracted_path)

            # Check if directory has LZA config files
            required_files = ["accounts-config.yaml", "global-config.yaml"]
            has_config_files = all(
                os.path.exists(os.path.join(extracted_path, f)) for f in required_files
            )

            if has_config_files:
                await ctx.info(
                    f"✅ Detected extracted config from getConfigurationFromS3(): {extracted_path}"
                )
                return {
                    "detected": True,
                    "config_path": str(extracted_path),
                    "age_seconds": dir_age,
                    "source": "getConfigurationFromS3",
                }
            else:
                await ctx.info(
                    f"Found directory at {extracted_path} but missing required config files"
                )

        return {"detected": False}

    except Exception as e:
        await ctx.error(f"Error detecting retrieved config context: {str(e)}")
        return {"detected": False, "error": str(e)}


async def _handle_retrieved_config_upload(
    ctx: Context,
    retrieved_config_context: Dict[str, Any],
    bucket_name: Optional[str],
    offer_pipeline_release: bool,
) -> Dict[str, Any]:
    """
    Handle upload from retrieved config directory (from getConfigurationFromS3).

    This zips the extracted configuration directory and uploads it to S3.

    Args:
        ctx: MCP context for logging
        retrieved_config_context: Context from retrieved config detection
        bucket_name: Optional custom bucket name
        offer_pipeline_release: Whether to offer pipeline release

    Returns:
        Dictionary with upload results
    """
    temp_zip_path = None

    try:
        config_path = retrieved_config_context["config_path"]
        await ctx.info(f"📦 Creating ZIP from retrieved configuration: {config_path}")

        # Create temporary ZIP file
        temp_zip_fd, temp_zip_path = tempfile.mkstemp(
            suffix=".zip", prefix="lza-config-upload-"
        )
        os.close(temp_zip_fd)

        # Create ZIP file from directory
        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(config_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, config_path)
                    zipf.write(file_path, arcname)
                    await ctx.info(f"  Added: {arcname}")

        zip_size = os.path.getsize(temp_zip_path)
        await ctx.info(f"✅ Created ZIP file ({zip_size} bytes)")

        # Verify AWS connectivity
        upload_tool = S3UploadUtils()
        aws_context = await upload_tool.ensure_aws_connectivity(ctx)

        # Determine target bucket name
        if not bucket_name:
            account_id = aws_context["account_id"]
            region = aws_context["region"]
            bucket_name = f"aws-accelerator-config-{account_id}-{region}"
            await ctx.info(f"Using auto-detected target bucket: {bucket_name}")

        # Upload ZIP file to S3
        await ctx.info(f"⬆️ Uploading to S3 bucket: {bucket_name}")
        s3_manager = S3Manager()
        upload_result = await s3_manager.upload_zip_file(
            zip_path=temp_zip_path, bucket_name=bucket_name, key=S3_OBJECT_KEY
        )

        if not upload_result["success"]:
            return upload_result

        await ctx.info("✅ Configuration uploaded successfully to S3!")
        await ctx.info(f"Bucket: {bucket_name}")
        await ctx.info(f"Key: {S3_OBJECT_KEY}")

        # Offer pipeline release
        if offer_pipeline_release:
            await ctx.info("🚀 Use 'releasePipeline' to deploy the configuration")

        return {
            "success": True,
            "message": "Configuration uploaded successfully from retrieved config",
            "source": "retrieved_config",
            "config_path": config_path,
            "zip_size": zip_size,
            "bucket_name": bucket_name,
            "object_key": S3_OBJECT_KEY,
            "aws_context": aws_context,
            "upload_details": upload_result,
        }

    except Exception as e:
        error_message = f"Retrieved config upload failed: {str(e)}"
        await ctx.error(error_message)

        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="RETRIEVED_CONFIG_UPLOAD_ERROR",
            troubleshooting=[
                "Ensure the retrieved configuration directory is accessible",
                "Verify AWS credentials and S3 permissions",
                "Check that configuration files are valid",
                "Ensure network connectivity to AWS services",
            ],
            context={
                "config_path": retrieved_config_context.get("config_path"),
                "bucket_name": bucket_name,
            },
        )
    finally:
        # Clean up temporary ZIP file
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
                logger.info(f"Cleaned up temporary ZIP file: {temp_zip_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary ZIP file: {str(e)}")


async def tool_upload_configuration_to_s3(
    ctx: Context,
    config_path: Optional[str] = None,
    bucket_name: Optional[str] = None,
    offer_pipeline_release: bool = True,
) -> Dict[str, Any]:
    """
    Upload LZA configuration to S3 bucket.

    This tool uploads LZA configurations to S3 buckets for deployment through
    the LZA pipeline using direct upload workflow.

    IMPORTANT - Docker Container Context:
    This MCP server runs inside a Docker container. Paths work differently:
    - The tool operates on the CONTAINER filesystem, not the host filesystem
    - If you retrieved config with getConfigurationFromS3(), leave config_path EMPTY
    - The tool will automatically find and use the retrieved configuration
    - DO NOT pass the host_path from getConfigurationFromS3() - it won't work!

    The tool automatically:
    - Discovers configuration files in the workspace
    - Creates a ZIP file of the configuration
    - Uploads to the specified S3 bucket
    - Verifies AWS connectivity using existing session management
    - Determines the appropriate S3 bucket name using AWS account and region
    - Provides comprehensive error handling with troubleshooting guidance
    - Optionally offers pipeline release functionality

    Args:
        config_path: Optional path to configuration folder WITHIN the container workspace.
                    IMPORTANT: Leave this EMPTY if you used getConfigurationFromS3() -
                    the tool will automatically detect and use the retrieved config.
                    Only provide a path if you have a custom container-relative path.
                    DO NOT use the host_path from getConfigurationFromS3()!
        bucket_name: Optional custom bucket name. If not provided, the tool will
                    construct the default bucket name using the pattern:
                    "aws-accelerator-config-<accountID>-<region>"
        offer_pipeline_release: Whether to offer pipeline release after successful upload.
                               Defaults to True.

    Returns:
        Dictionary containing upload results with success status and details

    TYPICAL WORKFLOW:
        1. checkAwsConnectivity - ensure permissions and account information
        2. getConfigurationFromS3() - downloads config to container workspace
        3. User edits files using the host_path with bash/file tools
        4. uploadConfigurationToS3() - NO PATH NEEDED, auto-detects the retrieved config
        5. releasePipeline() - triggers deployment

    Example Usage:
        # Upload configuration after getConfigurationFromS3() (RECOMMENDED)
        result = await upload_configuration_to_s3(ctx)  # No path needed!

        # Upload to custom bucket
        result = await upload_configuration_to_s3(ctx, bucket_name="my-custom-bucket")

        # Upload specific container-relative path (advanced use only)
        result = await upload_configuration_to_s3(ctx, config_path="./my-config")
    """
    try:
        await ctx.info("📤 Starting LZA configuration upload to S3...")

        # Validate config_path if provided
        if config_path:
            is_valid, validation_error = validate_file_path(
                config_path, allow_absolute=False
            )
            if not is_valid:
                error_message = f"Invalid config_path: {validation_error}"
                await ctx.error(error_message)
                return create_structured_error_response(
                    error=error_message,
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_CONFIG_PATH",
                    troubleshooting=[
                        "Provide a valid relative path within the container",
                        "Do not use absolute paths or paths outside the workspace",
                        "If you used getConfigurationFromS3(), leave config_path empty",
                    ],
                    context={"config_path": config_path},
                )

        # Validate bucket_name if provided
        if bucket_name:
            is_valid, validation_error = validate_s3_bucket_name(bucket_name)
            if not is_valid:
                error_message = f"Invalid bucket_name: {validation_error}"
                await ctx.error(error_message)
                return create_structured_error_response(
                    error=error_message,
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_BUCKET_NAME",
                    troubleshooting=[
                        "Bucket names must be 3-63 characters",
                        "Use only lowercase letters, numbers, hyphens, and dots",
                        "Bucket name must start and end with a letter or number",
                    ],
                    context={"bucket_name": bucket_name},
                )

        # Check if user provided a host path (common mistake)
        if config_path and (
            config_path.startswith("/Users/") or config_path.startswith("~/")
        ):
            error_message = (
                f"The provided path '{config_path}' appears to be a host filesystem path. "
                "This MCP server runs in a Docker container and cannot access host paths directly. "
                "If you recently used getConfigurationFromS3(), simply call this function "
                "WITHOUT the config_path parameter - it will automatically detect and use "
                "the retrieved configuration."
            )
            await ctx.error(error_message)

            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.CONFIGURATION,
                error_code="HOST_PATH_PROVIDED",
                troubleshooting=[
                    "Remove the config_path parameter and call uploadConfigurationToS3() without arguments",
                    "The tool will automatically find the configuration from getConfigurationFromS3()",
                    "If you need to specify a path, use a container-relative path like './my-config'",
                ],
                context={
                    "provided_path": config_path,
                    "path_type": "host_path",
                    "recommendation": "Call uploadConfigurationToS3() without config_path parameter",
                },
            )

        # Check for retrieved config from getConfigurationFromS3()
        if not config_path:
            retrieved_config_context = await _detect_retrieved_config_context(ctx)
            if retrieved_config_context["detected"]:
                await ctx.info("✅ Using configuration from getConfigurationFromS3()")
                await ctx.info("📤 This will create a ZIP and upload to S3")
                return await _handle_retrieved_config_upload(
                    ctx, retrieved_config_context, bucket_name, offer_pipeline_release
                )

        # Use direct upload workflow
        if config_path:
            await ctx.info(f"📁 Uploading configuration from: {config_path}")
        else:
            await ctx.info("📁 Using configuration discovery to find LZA config...")

        await ctx.info("🔧 Will discover, ZIP, and upload configuration")

        # Use S3UploadUtils for direct upload
        upload_tool = S3UploadUtils()
        result = await upload_tool.upload_configuration(
            ctx=ctx,
            config_path=config_path,
            bucket_name=bucket_name,
            offer_pipeline_release=offer_pipeline_release,
        )

        return result

    except Exception as e:
        error_message = f"Upload configuration to S3 failed: {str(e)}"
        await ctx.error(error_message)

        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="UPLOAD_ERROR",
            troubleshooting=[
                "Check AWS credentials and S3 permissions",
                "Verify network connectivity to AWS services",
                "Ensure config_path contains valid LZA configuration",
            ],
            context={
                "tool": "uploadConfigurationToS3",
                "config_path": config_path,
                "bucket_name": bucket_name,
            },
        )
