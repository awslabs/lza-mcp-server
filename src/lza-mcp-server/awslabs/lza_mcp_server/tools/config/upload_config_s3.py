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
from typing import Dict, Any, Optional

# AWS SDK
import boto3

# MCP framework components
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.tools.config.common import (
    ErrorCategory,
)
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response

logger = logging.getLogger(__name__)

# S3 Configuration constants
S3_OBJECT_KEY = "zipped/aws-accelerator-config.zip"
BUCKET_NAME_PATTERN = "aws-accelerator-config-{account_id}-{region}"


def detect_lza_bucket() -> Optional[str]:
    """Detect LZA bucket name from AWS environment.

    This is a placeholder function for test compatibility.
    In real implementation, this would detect the actual LZA bucket.
    """
    try:
        # This is a simplified implementation for test compatibility
        # In practice, this would use AWS APIs to detect the actual bucket
        session = boto3.Session()
        sts = session.client("sts")
        account_id = sts.get_caller_identity()["Account"]
        region = session.region_name or "us-east-1"
        return f"aws-accelerator-config-{account_id}-{region}"
    except Exception:
        return None


async def _handle_share_to_s3_upload(
    ctx: Context, bucket_name: Optional[str], offer_pipeline_release: bool
) -> Dict[str, Any]:
    """
    Handle upload from share location to S3 for configurations validated via share workflow.

    This uploads the validated ZIP file from the Docker shared volume to S3.
    """
    try:
        await ctx.info(
            "📤 Uploading validated configuration from share location to S3..."
        )

        # Find the validation ZIP file
        zip_file_path = None
        zip_location_type = None

        possible_zip_paths = [
            ("host", os.path.expanduser("~/Documents/lza-config/config.zip")),
            (
                "container",
                os.path.join(
                    os.environ.get("LZA_CONFIG_CONTAINER_PATH", "/app/lza-config"),
                    "config.zip",
                ),
            ),
        ]

        for location_type, path in possible_zip_paths:
            if os.path.exists(path):
                zip_file_path = path
                zip_location_type = location_type
                await ctx.info(
                    f"✅ Found validation ZIP at {location_type} path: {path}"
                )
                break

        if not zip_file_path:
            error_message = "Validation ZIP file not found in share locations"
            await ctx.error(error_message)

            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.CONFIGURATION,
                error_code="VALIDATION_ZIP_NOT_FOUND",
                troubleshooting=[
                    "Run validateConfigurationFromShare first to create the ZIP file",
                    "Check that validation completed successfully",
                    "Verify Docker volume mounts are correct",
                ],
                context={"checked_paths": [path for _, path in possible_zip_paths]},
            )

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
            zip_path=zip_file_path, bucket_name=bucket_name, key=S3_OBJECT_KEY
        )

        if not upload_result["success"]:
            return upload_result

        await ctx.info("✅ Configuration uploaded successfully to S3!")
        await ctx.info(f"Bucket: {bucket_name}")
        await ctx.info(f"Key: {S3_OBJECT_KEY}")

        # Offer pipeline release
        if offer_pipeline_release:
            await ctx.info(
                "🚀 Use 'releasePipelineAfterUpload' to deploy the configuration"
            )

        return {
            "success": True,
            "message": "Configuration uploaded successfully from share validation workflow",
            "source": f"share_validation_{zip_location_type}",
            "zip_path": zip_file_path,
            "bucket_name": bucket_name,
            "object_key": S3_OBJECT_KEY,
            "aws_context": aws_context,
            "upload_details": upload_result,
        }

    except Exception as e:
        error_message = f"Share-to-S3 upload failed: {str(e)}"
        await ctx.error(error_message)

        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="SHARE_UPLOAD_ERROR",
            troubleshooting=[
                "Ensure the share location is accessible",
                "Verify AWS credentials and S3 permissions",
                "Check that the ZIP file exists and is readable",
                "Ensure network connectivity to AWS services",
            ],
            context={"bucket_name": bucket_name},
        )


async def _handle_s3_to_s3_copy(
    ctx: Context,
    s3_validation_context: Dict[str, Any],
    target_bucket_name: Optional[str],
    offer_pipeline_release: bool,
) -> Dict[str, Any]:
    """
    Handle S3-to-S3 copy for configurations validated via S3 workflow.

    This copies the validated ZIP file from the S3 validation location to the target config bucket.
    """
    try:
        await ctx.info(
            "📤 Copying validated configuration from S3 validation location to config bucket..."
        )

        source_s3_path = s3_validation_context["s3_path"]
        await ctx.info(f"Source S3 path: {source_s3_path}")

        # Parse source S3 path
        if source_s3_path.startswith("s3://"):
            source_s3_path = source_s3_path[5:]  # Remove 's3://' prefix

        # Split bucket and key
        path_parts = source_s3_path.split("/", 1)
        if len(path_parts) != 2:
            error_message = f"Invalid S3 path format: {source_s3_path}"
            await ctx.error(error_message)
            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.CONFIGURATION,
                error_code="INVALID_S3_PATH",
                troubleshooting=[
                    "S3 path must be in format: bucket-name/path/to/file.zip",
                    "Or s3://bucket-name/path/to/file.zip",
                ],
                context={"source_s3_path": source_s3_path},
            )

        source_bucket = path_parts[0]
        source_key = path_parts[1]

        # Verify AWS connectivity
        upload_tool = S3UploadUtils()
        aws_context = await upload_tool.ensure_aws_connectivity(ctx)

        # Determine target bucket name
        if not target_bucket_name:
            account_id = aws_context["account_id"]
            region = aws_context["region"]
            target_bucket_name = f"aws-accelerator-config-{account_id}-{region}"
            await ctx.info(f"Using auto-detected target bucket: {target_bucket_name}")

        # Perform S3-to-S3 copy
        await ctx.info(
            f"⬆️ Copying from s3://{source_bucket}/{source_key} to s3://{target_bucket_name}/{S3_OBJECT_KEY}"
        )

        s3_manager = S3Manager()
        copy_result = await s3_manager.copy_s3_object(
            source_bucket=source_bucket,
            source_key=source_key,
            target_bucket=target_bucket_name,
            target_key=S3_OBJECT_KEY,
        )

        if not copy_result["success"]:
            return copy_result

        await ctx.info("✅ Configuration copied successfully to config bucket!")
        await ctx.info(f"Target bucket: {target_bucket_name}")
        await ctx.info(f"Target key: {S3_OBJECT_KEY}")

        # Offer pipeline release
        if offer_pipeline_release:
            await ctx.info(
                "🚀 Use 'releasePipelineAfterUpload' to deploy the configuration"
            )

        return {
            "success": True,
            "operation": "s3_to_s3_copy",
            "source_bucket": source_bucket,
            "source_key": source_key,
            "target_bucket": target_bucket_name,
            "target_key": S3_OBJECT_KEY,
            "aws_context": aws_context,
            "validation_context": s3_validation_context,
            "pipeline_release_offered": offer_pipeline_release,
            "message": "Configuration copied successfully from S3 validation location to config bucket",
        }

    except Exception as e:
        error_message = f"S3-to-S3 copy failed: {str(e)}"
        await ctx.error(error_message)

        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.S3,
            error_code="S3_COPY_FAILED",
            troubleshooting=[
                "Verify source S3 bucket and key exist",
                "Check permissions for both source and target buckets",
                "Ensure AWS credentials have s3:GetObject and s3:PutObject permissions",
                "Verify network connectivity to AWS S3",
            ],
            context={
                "source_s3_path": s3_validation_context.get("s3_path"),
                "target_bucket": target_bucket_name,
                "operation": "s3_to_s3_copy",
            },
        )


async def _detect_share_validation_context(ctx: Context) -> Dict[str, Any]:
    """
    Detect if share validation was recently used by checking for ZIP files.

    Returns:
        Dict with detection result and share validation context
    """
    try:
        share_paths = [
            os.path.expanduser("~/Documents/lza-config/config.zip"),
            os.path.join(
                os.environ.get("LZA_CONFIG_CONTAINER_PATH", "/app/lza-config"),
                "config.zip",
            ),
        ]

        most_recent_path = None
        most_recent_age = float("inf")

        for path in share_paths:
            if os.path.exists(path):
                import time

                file_age = time.time() - os.path.getmtime(path)

                if file_age < most_recent_age:
                    most_recent_path = path
                    most_recent_age = file_age

        # Use the most recent file if it's within 2 hours
        if most_recent_path and most_recent_age < 7200:  # 2 hours
            return {
                "detected": True,
                "zip_path": most_recent_path,
                "age_seconds": most_recent_age,
                "location_type": "host"
                if "Documents" in most_recent_path
                else "container",
            }
        elif most_recent_path:
            await ctx.info(
                f"Found old share validation ZIP: {most_recent_path} (age: {most_recent_age:.0f}s) - may be stale"
            )

        return {"detected": False}

    except Exception as e:
        await ctx.error(f"Error detecting share validation context: {str(e)}")
        return {"detected": False, "error": str(e)}


async def _detect_s3_validation_context(ctx: Context) -> Dict[str, Any]:
    """
    Detect if S3 validation was recently used by checking for S3 validation context.

    This looks for indicators that S3 validation was recently performed, such as:
    - Recent S3 validation results stored in temporary files
    - Environment variables indicating S3 validation
    - Recent S3 validation tool execution context

    Returns:
        Dict with detection result and S3 context information
    """
    try:
        # Check for S3 validation context files or environment variables
        # This could be enhanced to check for recent tool execution context

        # For now, we'll check if there are any environment variables that indicate
        # recent S3 validation (this can be enhanced based on how S3 validation stores context)
        s3_validation_indicators = [
            "LZA_LAST_S3_VALIDATION_PATH",
            "LZA_S3_VALIDATION_BUCKET",
            "LZA_S3_VALIDATION_KEY",
        ]

        for indicator in s3_validation_indicators:
            if os.environ.get(indicator):
                s3_path = os.environ.get(indicator)
                await ctx.info(f"Found S3 validation indicator: {indicator}={s3_path}")

                # Validate that this is a recent validation (within 2 hours)
                timestamp_var = f"{indicator}_TIMESTAMP"
                if os.environ.get(timestamp_var):
                    try:
                        import time

                        validation_time = float(os.environ.get(timestamp_var))
                        age = time.time() - validation_time

                        if age < 7200:  # 2 hours
                            return {
                                "detected": True,
                                "s3_path": s3_path,
                                "age_seconds": age,
                                "source": indicator,
                            }
                        else:
                            await ctx.info(
                                f"S3 validation context is stale (age: {age:.0f}s)"
                            )
                    except (ValueError, TypeError):
                        await ctx.info(f"Invalid timestamp in {timestamp_var}")

        # TODO: This can be enhanced to check for other S3 validation indicators
        # such as recent tool execution results or temporary files

        return {"detected": False}

    except Exception as e:
        await ctx.error(f"Error detecting S3 validation context: {str(e)}")
        return {"detected": False, "error": str(e)}


async def _detect_validation_type(ctx: Context) -> Dict[str, Any]:
    """
    Detect which validation workflow was recently used.

    Returns:
        Dict containing validation type and relevant context:
        - type: "s3_validation", "share_validation", or "direct_upload"
        - context: Additional information like S3 path or share path
    """
    try:
        # Step 1: Check for recent S3 validation context
        # Look for environment variables or context that indicates S3 validation was used
        s3_validation_context = await _detect_s3_validation_context(ctx)
        if s3_validation_context["detected"]:
            await ctx.info(
                f"🔍 Detected recent S3 validation: {s3_validation_context['s3_path']}"
            )
            return {"type": "s3_validation", "context": s3_validation_context}

        # Step 2: Check for share validation ZIP files
        share_validation_context = await _detect_share_validation_context(ctx)
        if share_validation_context["detected"]:
            await ctx.info(
                f"🔍 Detected recent share validation: {share_validation_context['zip_path']}"
            )
            return {"type": "share_validation", "context": share_validation_context}

        # Step 3: No recent validation detected
        await ctx.info("🔍 No recent validation artifacts found, direct upload needed")
        return {"type": "direct_upload", "context": {"reason": "no_recent_validation"}}

    except Exception as e:
        await ctx.error(f"Error detecting validation type: {str(e)}")
        return {
            "type": "direct_upload",
            "context": {"reason": "detection_error", "error": str(e)},
        }


async def tool_upload_configuration_to_s3(
    ctx: Context,
    config_path: Optional[str] = None,
    bucket_name: Optional[str] = None,
    offer_pipeline_release: bool = True,
) -> Dict[str, Any]:
    """
    Upload validated LZA configuration to S3 bucket with smart validation detection.

    This tool enables uploading LZA configurations to S3 buckets for deployment through
    the LZA pipeline. It intelligently detects which validation workflow was used and
    handles the upload accordingly.

    Smart Detection Logic:
    1. **S3 Validation Detection**: Checks for recent S3 validation context and performs
       efficient S3-to-S3 copy from validation location to config bucket
    2. **Share Validation Detection**: Checks for recent ZIP files in share locations
       (Docker volumes) and uploads from there
    3. **Direct Upload Fallback**: If no recent validation detected, discovers and
       validates configuration, creates new ZIP, and uploads

    The tool automatically:
    - Detects validation type from recent validation workflows
    - Performs S3-to-S3 copy for S3 validation (most efficient)
    - Uploads from share location for share validation
    - Falls back to configuration discovery and ZIP creation for direct uploads
    - Verifies AWS connectivity using existing session management
    - Determines the appropriate S3 bucket name using AWS account and region
    - Provides comprehensive error handling with troubleshooting guidance
    - Optionally offers pipeline release functionality

    Args:
        config_path: Optional path to configuration folder. If not provided,
                    the tool will first check share locations for validation ZIP,
                    then search the workspace for valid LZA configurations.
        bucket_name: Optional custom bucket name. If not provided, the tool will
                    construct the default bucket name using the pattern:
                    "aws-accelerator-config-<accountID>-<region>"
        offer_pipeline_release: Whether to offer pipeline release after successful upload.
                               Defaults to True.

    Returns:
        Dictionary containing upload results with success status and details

    Example Usage:
        # Upload from validation workflow (checks share location first)
        result = await upload_configuration_to_s3(ctx)

        # Upload specific configuration directory
        result = await upload_configuration_to_s3(ctx, config_path="/path/to/config")

        # Upload to custom bucket
        result = await upload_configuration_to_s3(ctx, bucket_name="my-custom-bucket")
        :param offer_pipeline_release:
        :param bucket_name:
        :param config_path:
        :param ctx:
    """
    try:
        await ctx.info("📤 Starting LZA configuration upload to S3...")

        # Step 1: Detect which validation workflow was used
        validation_detection = await _detect_validation_type(ctx)
        validation_type = validation_detection["type"]
        validation_context = validation_detection["context"]

        await ctx.info(f"🔍 Detected validation type: {validation_type}")

        # Step 2: Handle upload based on validation type
        if validation_type == "s3_validation":
            # S3 validation was used - perform S3-to-S3 copy
            await ctx.info("✅ Using validated configuration from recent S3 validation")
            await ctx.info(
                "📤 This will copy the validated ZIP from S3 validation location to config bucket"
            )
            return await _handle_s3_to_s3_copy(
                ctx, validation_context, bucket_name, offer_pipeline_release
            )

        elif validation_type == "share_validation":
            # Share validation was used - upload from share location
            await ctx.info(
                "✅ Using validated configuration from recent share validation"
            )
            await ctx.info("📤 This will upload the already-validated ZIP file to S3")
            return await _handle_share_to_s3_upload(
                ctx, bucket_name, offer_pipeline_release
            )

        elif validation_type == "direct_upload":
            # No recent validation - use direct configuration upload
            if config_path:
                await ctx.info(
                    f"📁 Using direct configuration upload from: {config_path}"
                )
                await ctx.info(
                    "🔧 This will discover, validate, and create a new ZIP file"
                )
            else:
                await ctx.info(
                    "📁 No recent validation detected, using configuration discovery..."
                )
                await ctx.info(
                    "🔍 This will find your LZA configuration and create a new ZIP file"
                )

            # Use the original S3UploadTool workflow for direct uploads
            upload_tool = S3UploadUtils()
            result = await upload_tool.upload_configuration(
                ctx=ctx,
                config_path=config_path,
                bucket_name=bucket_name,
                offer_pipeline_release=offer_pipeline_release,
            )

            return result

        else:
            # Unknown validation type
            error_message = f"Unknown validation type detected: {validation_type}"
            await ctx.error(error_message)

            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.INTEGRATION,
                error_code="UNKNOWN_VALIDATION_TYPE",
                troubleshooting=[
                    "Run validateConfigurationFromS3 for S3-based validation workflow",
                    "Run validateConfigurationFromShare for share-based validation workflow",
                    "Or provide config_path parameter for direct upload",
                ],
                context={
                    "validation_type": validation_type,
                    "validation_context": validation_context,
                },
            )

    except Exception as e:
        error_message = f"Upload configuration to S3 failed: {str(e)}"
        await ctx.error(error_message)

        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="UPLOAD_ERROR",
            troubleshooting=[
                "If using validation workflow, ensure validateConfigurationFromShare was run first",
                "Check AWS credentials and S3 permissions",
                "Verify network connectivity to AWS services",
                "For direct upload, ensure config_path contains valid LZA configuration",
            ],
            context={
                "tool": "uploadConfigurationToS3",
                "config_path": config_path,
                "bucket_name": bucket_name,
            },
        )
