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

from typing import Optional, Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import create_structured_error_response
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils


async def tool_upload_configuration_to_s3_with_custom_bucket(
    ctx: Context,
    custom_bucket_name: str,
    config_path: Optional[str] = None,
    offer_pipeline_release: bool = True,
) -> Dict[str, Any]:
    """
    Upload configuration with a user-provided custom bucket name.

    This tool is designed to be called when the user provides a custom bucket name
    after the default bucket was not found. It provides the same functionality as
    the main upload tool but with a required custom bucket name parameter.

    Args:
        custom_bucket_name: Required custom bucket name provided by user
        config_path: Optional path to configuration folder
        offer_pipeline_release: Whether to offer pipeline release after upload

    Returns:
        Dictionary containing upload results (same structure as main upload tool)

    Requirements Addressed:
        - 3.3: User prompt functionality for custom bucket name when default doesn't exist
        :param offer_pipeline_release:
        :param config_path:
        :param custom_bucket_name:
        :param ctx:
    """
    try:
        # Initialize the S3 upload tool
        upload_tool = S3UploadUtils()

        # Execute the upload workflow with custom bucket
        result = await upload_tool.upload_configuration_with_custom_bucket(
            ctx=ctx,
            config_path=config_path,
            custom_bucket_name=custom_bucket_name,
            offer_pipeline_release=offer_pipeline_release,
        )

        # Log the final result
        if result["success"]:
            await ctx.info(
                f"S3 upload with custom bucket completed successfully: {result.get('s3_location', 'S3')}"
            )
        else:
            await ctx.error(
                f"S3 upload with custom bucket failed: {result.get('error', 'Unknown error')}"
            )

        return result

    except S3UploadError as e:
        # Handle structured S3 upload errors
        error_dict = e.to_dict()
        await ctx.error(f"S3 upload with custom bucket failed: {e.message}")
        return error_dict

    except Exception as e:
        error_message = (
            f"Unexpected error in uploadConfigurationToS3WithCustomBucket: {str(e)}"
        )
        await ctx.error(error_message)

        # Create structured error response for unexpected errors
        return create_structured_error_response(
            error=error_message,
            category=ErrorCategory.INTEGRATION,
            error_code="UNEXPECTED_TOOL_ERROR",
            troubleshooting=[
                "Verify the custom bucket name is correct and accessible",
                "Check AWS credentials and permissions",
                "Ensure the bucket exists in your AWS account",
                "Verify you have s3:PutObject permission for the bucket",
                "Review application logs for more details",
            ],
            context={
                "tool": "uploadConfigurationToS3WithCustomBucket",
                "config_path": config_path,
                "custom_bucket_name": custom_bucket_name,
                "offer_pipeline_release": offer_pipeline_release,
                "error_type": type(e).__name__,
            },
            operation="mcp_tool_execution",
        )
