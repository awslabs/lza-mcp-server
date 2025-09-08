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


import logging
import os
import tempfile
from typing import Dict, Any, Optional

# MCP framework components
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.constants import DEFAULT_REGION, S3_OBJECT_KEY
from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    ConfigurationManager,
    create_configuration_zip,
    cleanup_configuration_zip,
    select_configuration,
)
from awslabs.lza_mcp_server.orchestration.core.pipeline_release_manager import (
    PipelineReleaseManager,
)
from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.common import (
    categorize_configuration_error,
)
from awslabs.lza_mcp_server.aws_access import (
    create_structured_error_response,
    verify_aws_connectivity,
)

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


class S3UploadUtils:
    """Main tool class for S3 configuration upload functionality."""

    def __init__(self):
        """Initialize the S3 upload tool with AWS integration."""
        self.logger = logger
        self.s3_manager = S3Manager()
        self.config_manager = ConfigurationManager()
        self.pipeline_manager = PipelineReleaseManager()
        self._aws_connectivity_verified = False
        self._aws_context = None

    async def ensure_aws_connectivity(self, ctx: Context) -> Dict[str, Any]:
        """
        Ensure AWS connectivity is verified using existing AWS tools.

        This method leverages the existing checkAwsConnectivity functionality
        and caches the result to avoid repeated checks.

        Args:
            ctx: MCP context for logging

        Returns:
            AWS connectivity result with account information

        Raises:
            Exception: If AWS connectivity cannot be established
        """
        if self._aws_connectivity_verified and self._aws_context:
            return self._aws_context

        # Use existing AWS connectivity verification
        connectivity_result = await verify_aws_connectivity(ctx)

        if not connectivity_result["connected"]:
            raise Exception(
                f"AWS connectivity failed: {connectivity_result['message']}"
            )

        # Cache the result
        self._aws_connectivity_verified = True
        self._aws_context = connectivity_result

        return connectivity_result

    async def upload_configuration_with_custom_bucket(
        self,
        ctx: Context,
        config_path: Optional[str] = None,
        custom_bucket_name: str = None,
        offer_pipeline_release: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload configuration with a user-provided custom bucket name.

        This method is called when the user provides a custom bucket name after
        the default bucket was not found. It reuses configuration discovery
        functionality from the validation workflow.

        Args:
            ctx: MCP context
            config_path: Optional path to configuration folder
            custom_bucket_name: Custom bucket name provided by user
            offer_pipeline_release: Whether to offer pipeline release after upload

        Returns:
            Upload result with success status and details
        """
        try:
            # Step 1: Verify AWS connectivity
            await ctx.info("Verifying AWS connectivity...")
            aws_context = await self.ensure_aws_connectivity(ctx)

            # Step 2: Discover and select configuration using existing logic
            await ctx.info("Discovering and selecting LZA configuration...")
            config_result = await self._discover_and_select_configuration(
                ctx, config_path
            )

            if not config_result["success"]:
                # Return configuration discovery error with AWS context
                config_result["aws_context"] = aws_context
                return config_result

            selected_config_path = config_result["selected_config"]
            await ctx.info(f"Selected configuration for upload: {selected_config_path}")

            # Step 3: Validate the custom bucket name
            await ctx.info(f"Validating custom bucket name: {custom_bucket_name}")
            validation_result = await self.s3_manager.validate_custom_bucket_name(
                custom_bucket_name
            )

            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "error_type": validation_result["error_type"],
                    "message": f"Custom bucket name validation failed: {validation_result['error']}",
                    "troubleshooting": validation_result.get("troubleshooting", []),
                    "aws_context": aws_context,
                    "config_discovery": config_result,
                }

            # Step 4: Proceed with upload using the validated custom bucket
            await ctx.info(f"Using validated custom bucket: {custom_bucket_name}")

            # Step 5: Create ZIP file using existing validation workflow logic
            await ctx.info("Creating ZIP file from configuration...")
            selected_config_path = config_result["selected_config"]

            # Create temporary ZIP file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
                temp_zip_path = temp_zip.name

            try:
                # Use the reused ZIP creation logic from validation workflow
                zip_result = await create_configuration_zip(
                    ctx, selected_config_path, temp_zip_path
                )

                if not zip_result["success"]:
                    return {
                        "success": False,
                        "error": zip_result["error"],
                        "message": f"Failed to create configuration ZIP: {zip_result['error']}",
                        "aws_context": aws_context,
                        "config_discovery": config_result,
                        "bucket_name": custom_bucket_name,
                        "bucket_validation": validation_result,
                        "troubleshooting": [
                            "Ensure the configuration directory is accessible",
                            "Check file system permissions",
                            "Verify the 'zip' command is available on the system",
                        ],
                    }

                await ctx.info(
                    f"ZIP file created successfully: {zip_result['file_size']} bytes"
                )

                # Step 6: Upload ZIP file to S3
                await ctx.info(
                    f"Uploading configuration to S3 bucket: {custom_bucket_name}"
                )
                upload_result = await self.s3_manager.upload_zip_file(
                    zip_path=temp_zip_path,
                    bucket_name=custom_bucket_name,
                    key=S3_OBJECT_KEY,
                )

                if not upload_result["success"]:
                    return {
                        "success": False,
                        "error": upload_result["error"],
                        "error_code": upload_result.get("error_code"),
                        "message": f"S3 upload failed: {upload_result['error']}",
                        "troubleshooting": upload_result.get("troubleshooting", []),
                        "aws_context": aws_context,
                        "config_discovery": config_result,
                        "bucket_name": custom_bucket_name,
                        "bucket_validation": validation_result,
                        "zip_creation": zip_result,
                    }

                await ctx.info(
                    f"Successfully uploaded configuration to s3://{custom_bucket_name}/{S3_OBJECT_KEY}"
                )

                # Step 7: Prepare final success response
                final_result = {
                    "success": True,
                    "message": "Configuration successfully uploaded to S3",
                    "aws_context": aws_context,
                    "config_discovery": config_result,
                    "bucket_name": custom_bucket_name,
                    "bucket_validation": validation_result,
                    "zip_creation": zip_result,
                    "s3_upload": upload_result,
                    "s3_location": f"s3://{custom_bucket_name}/{S3_OBJECT_KEY}",
                    "upload_size": upload_result["file_size"],
                }

                # Step 8: Offer pipeline release if requested
                if offer_pipeline_release:
                    pipeline_offer_result = (
                        await self.pipeline_manager.offer_pipeline_release(ctx)
                    )
                    final_result["pipeline_release_offered"] = pipeline_offer_result[
                        "offered"
                    ]
                    final_result["pipeline_offer_details"] = pipeline_offer_result

                return final_result

            finally:
                # Clean up temporary ZIP file using existing cleanup logic
                cleanup_result = await cleanup_configuration_zip(ctx, temp_zip_path)
                if not cleanup_result["success"]:
                    await ctx.error(
                        f"Failed to cleanup temporary ZIP file: {cleanup_result['error']}"
                    )

        except S3UploadError as e:
            # Handle structured S3 upload errors
            error_dict = e.to_dict()
            await ctx.error(
                f"Configuration upload with custom bucket failed: {e.message}"
            )
            return error_dict

        except Exception as e:
            error_message = f"Configuration upload with custom bucket failed: {str(e)}"
            await ctx.error(error_message)

            # Create structured error response for unexpected errors
            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.INTEGRATION,
                error_code="UNEXPECTED_CUSTOM_BUCKET_ERROR",
                troubleshooting=[
                    "Check AWS credentials configuration",
                    "Verify the custom bucket name is correct",
                    "Ensure you have access permissions to the bucket",
                    "Verify workspace contains valid LZA configurations",
                    "Check system resources and disk space",
                    "Review application logs for more details",
                ],
                context={
                    "config_path": config_path,
                    "custom_bucket_name": custom_bucket_name,
                    "offer_pipeline_release": offer_pipeline_release,
                    "operation": "upload_configuration_with_custom_bucket",
                    "error_type": type(e).__name__,
                },
                operation="upload_configuration_with_custom_bucket",
            )

    async def _discover_and_select_configuration(
        self, ctx: Context, config_path: Optional[str] = None, workspace_path: str = "."
    ) -> Dict[str, Any]:
        """
        Discover and select LZA configuration using existing validation workflow patterns.

        This method reuses the exact same logic as the validation workflow to ensure
        consistent behavior and user experience across the MCP server.

        Args:
            ctx: MCP context for logging and user interaction
            config_path: Optional specific configuration path
            workspace_path: Workspace path to search for configurations

        Returns:
            Dictionary with selected configuration path and discovery results
        """
        try:
            # If specific config path is provided, validate it
            if config_path is not None:
                await ctx.info(f"Validating provided configuration path: {config_path}")

                try:
                    if await self.config_manager.validate_configuration_path(
                        config_path
                    ):
                        await ctx.info(
                            f"Using provided configuration path: {config_path}"
                        )
                        return {
                            "success": True,
                            "selected_config": config_path,
                            "discovery_method": "provided_path",
                            "message": f"Using provided configuration: {config_path}",
                        }
                except S3UploadError as e:
                    # Convert S3UploadError to discovery result format
                    error_dict = e.to_dict()
                    error_dict["message"] = "Invalid configuration path provided"
                    return error_dict

            # Discover configurations in workspace using existing logic
            await ctx.info(
                f"Discovering LZA configurations in workspace: {workspace_path}"
            )
            discovered_configs = await self.config_manager.discover_configurations(
                ctx, workspace_path
            )

            if not discovered_configs:
                return {
                    "success": False,
                    "error": "No valid LZA configurations found in workspace",
                    "message": "No LZA configurations discovered",
                    "workspace_searched": workspace_path,
                    "troubleshooting": [
                        "Ensure your workspace contains LZA configuration directories",
                        "Each configuration directory must contain both:",
                        "  - accounts-config.yaml",
                        "  - organization-config.yaml",
                        "Check that configuration files are properly named and located",
                    ],
                }

            # Select configuration using existing selection logic
            selected_config = await select_configuration(ctx, discovered_configs)

            return {
                "success": True,
                "selected_config": selected_config,
                "discovered_configs": discovered_configs,
                "discovery_method": "workspace_search",
                "message": f"Selected configuration: {selected_config}",
            }

        except S3UploadError as e:
            # Handle structured S3 upload errors
            error_dict = e.to_dict()
            await ctx.error(f"Configuration discovery failed: {e.message}")
            return error_dict

        except Exception as e:
            error_message = f"Configuration discovery failed: {str(e)}"
            await ctx.error(error_message)

            # Create structured error response for unexpected errors
            error_info = categorize_configuration_error(e)
            return create_structured_error_response(
                error=error_message,
                category=error_info["category"],
                error_code=error_info["error_code"],
                troubleshooting=error_info["troubleshooting"],
                context={
                    "config_path": config_path,
                    "workspace_path": workspace_path,
                    "operation": "configuration_discovery",
                    "error_type": type(e).__name__,
                },
                operation="configuration_discovery",
            )

    async def upload_configuration(
        self,
        ctx: Context,
        config_path: Optional[str] = None,
        bucket_name: Optional[str] = None,
        offer_pipeline_release: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload validated LZA configuration to S3 bucket.

        This method integrates with existing AWS connectivity and session management
        to provide a seamless upload experience. It reuses configuration discovery
        functionality from the validation workflow.

        Args:
            ctx: MCP context
            config_path: Optional path to configuration folder
            bucket_name: Optional custom bucket name
            offer_pipeline_release: Whether to offer pipeline release after upload

        Returns:
            Upload result with success status and details
        """
        try:
            # Step 1: Verify AWS connectivity using existing tools
            await ctx.info("Verifying AWS connectivity...")
            aws_context = await self.ensure_aws_connectivity(ctx)

            # Step 2: Discover and select configuration using existing logic
            await ctx.info("Discovering and selecting LZA configuration...")
            config_result = await self._discover_and_select_configuration(
                ctx, config_path
            )

            if not config_result["success"]:
                # Return configuration discovery error with AWS context
                config_result["aws_context"] = aws_context
                return config_result

            selected_config_path = config_result["selected_config"]
            await ctx.info(f"Selected configuration for upload: {selected_config_path}")

            # Step 3: Determine bucket name if not provided
            if bucket_name is None:
                await ctx.info("Determining default S3 bucket name...")
                bucket_name = await self.s3_manager.determine_bucket_name(
                    account_id=aws_context["account_id"], region=aws_context["region"]
                )
            else:
                await ctx.info(f"Using provided bucket name: {bucket_name}")
                # Validate the provided bucket name
                validation_result = await self.s3_manager.validate_custom_bucket_name(
                    bucket_name
                )
                if not validation_result["valid"]:
                    return {
                        "success": False,
                        "error": validation_result["error"],
                        "error_type": validation_result["error_type"],
                        "message": f"Provided bucket name validation failed: {validation_result['error']}",
                        "troubleshooting": validation_result.get("troubleshooting", []),
                        "aws_context": aws_context,
                        "config_discovery": config_result,
                    }

            # Step 4: Verify bucket exists
            await ctx.info(f"Verifying bucket exists: {bucket_name}")
            bucket_exists = await self.s3_manager.verify_bucket_exists(bucket_name)

            if not bucket_exists:
                # Generate user prompt for custom bucket name
                prompt_response = await self.s3_manager.prompt_for_custom_bucket_name(
                    default_bucket_name=bucket_name,
                    account_id=aws_context["account_id"],
                    region=aws_context["region"],
                )

                return {
                    "success": False,
                    "error": f"Bucket '{bucket_name}' does not exist",
                    "message": f"S3 bucket '{bucket_name}' was not found",
                    "user_prompt": prompt_response,
                    "aws_context": aws_context,
                    "config_discovery": config_result,
                    "next_steps": [
                        "Provide a custom bucket name that exists in your AWS account",
                        f"Or create the default bucket: aws s3 mb s3://{bucket_name} --region {aws_context['region']}",
                        "Ensure you have s3:PutObject permissions for the bucket",
                    ],
                }

            # Step 5: Create ZIP file using existing validation workflow logic
            await ctx.info("Creating ZIP file from configuration...")

            # Create temporary ZIP file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
                temp_zip_path = temp_zip.name

            try:
                # Use the reused ZIP creation logic from validation workflow
                zip_result = await create_configuration_zip(
                    ctx, selected_config_path, temp_zip_path
                )

                if not zip_result["success"]:
                    return {
                        "success": False,
                        "error": zip_result["error"],
                        "message": f"Failed to create configuration ZIP: {zip_result['error']}",
                        "aws_context": aws_context,
                        "config_discovery": config_result,
                        "bucket_name": bucket_name,
                        "troubleshooting": [
                            "Ensure the configuration directory is accessible",
                            "Check file system permissions",
                            "Verify the 'zip' command is available on the system",
                        ],
                    }

                await ctx.info(
                    f"ZIP file created successfully: {zip_result['file_size']} bytes"
                )

                # Step 6: Upload ZIP file to S3
                await ctx.info(f"Uploading configuration to S3 bucket: {bucket_name}")
                upload_result = await self.s3_manager.upload_zip_file(
                    zip_path=temp_zip_path, bucket_name=bucket_name, key=S3_OBJECT_KEY
                )

                if not upload_result["success"]:
                    return {
                        "success": False,
                        "error": upload_result["error"],
                        "error_code": upload_result.get("error_code"),
                        "message": f"S3 upload failed: {upload_result['error']}",
                        "troubleshooting": upload_result.get("troubleshooting", []),
                        "aws_context": aws_context,
                        "config_discovery": config_result,
                        "bucket_name": bucket_name,
                        "zip_creation": zip_result,
                    }

                await ctx.info(
                    f"Successfully uploaded configuration to s3://{bucket_name}/{S3_OBJECT_KEY}"
                )

                # Step 7: Prepare final success response
                final_result = {
                    "success": True,
                    "message": "Configuration successfully uploaded to S3",
                    "aws_context": aws_context,
                    "config_discovery": config_result,
                    "bucket_name": bucket_name,
                    "zip_creation": zip_result,
                    "s3_upload": upload_result,
                    "s3_location": f"s3://{bucket_name}/{S3_OBJECT_KEY}",
                    "upload_size": upload_result["file_size"],
                }

                # Step 8: Offer pipeline release if requested
                if offer_pipeline_release:
                    pipeline_offer_result = (
                        await self.pipeline_manager.offer_pipeline_release(ctx)
                    )
                    final_result["pipeline_release_offered"] = pipeline_offer_result[
                        "offered"
                    ]
                    final_result["pipeline_offer_details"] = pipeline_offer_result

                return final_result

            finally:
                # Clean up temporary ZIP file using existing cleanup logic
                cleanup_result = await cleanup_configuration_zip(ctx, temp_zip_path)
                if not cleanup_result["success"]:
                    await ctx.error(
                        f"Failed to cleanup temporary ZIP file: {cleanup_result['error']}"
                    )

        except S3UploadError as e:
            # Handle structured S3 upload errors
            error_dict = e.to_dict()
            await ctx.error(f"Configuration upload failed: {e.message}")
            return error_dict

        except Exception as e:
            error_message = f"Configuration upload failed: {str(e)}"
            await ctx.error(error_message)

            # Create structured error response for unexpected errors
            return create_structured_error_response(
                error=error_message,
                category=ErrorCategory.INTEGRATION,
                error_code="UNEXPECTED_UPLOAD_ERROR",
                troubleshooting=[
                    "Check AWS credentials configuration",
                    "Verify network connectivity to AWS",
                    "Ensure proper IAM permissions for S3 operations",
                    "Verify workspace contains valid LZA configurations",
                    "Check system resources and disk space",
                    "Review application logs for more details",
                ],
                context={
                    "config_path": config_path,
                    "bucket_name": bucket_name,
                    "offer_pipeline_release": offer_pipeline_release,
                    "operation": "upload_configuration",
                    "error_type": type(e).__name__,
                },
                operation="upload_configuration",
            )
