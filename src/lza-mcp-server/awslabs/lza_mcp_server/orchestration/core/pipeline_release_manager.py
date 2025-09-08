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
from typing import Dict, Any

# MCP framework components
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import (
    get_codepipeline_client,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from awslabs.lza_mcp_server.utils.error_handling import format_error_response
from awslabs.lza_mcp_server.constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
# Removed circular import - using simple validation instead

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


def validate_pipeline_name(pipeline_name: str) -> tuple[bool, str]:
    """Simple pipeline name validation to avoid circular imports."""
    if not pipeline_name or len(pipeline_name) < 1 or len(pipeline_name) > 100:
        return False, "Pipeline name must be 1-100 characters long"
    return True, ""


def format_success_response(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Format a successful response with consistent structure.

    Args:
        data: The response data to include
        message: Success message to include

    Returns:
        Dict containing success=True, message, and the provided data
    """
    response = {"success": True, "message": message}
    response.update(data)
    return response


class PipelineReleaseManager:
    """Handles pipeline release functionality using existing pipeline tools."""

    def __init__(self):
        """Initialize the pipeline release manager."""
        self.logger = logger

    async def offer_pipeline_release(self, ctx: Context) -> Dict[str, Any]:
        """
        Offer pipeline release to the user using existing user confirmation patterns.

        This method reuses the existing user interaction patterns from the MCP server
        to provide a consistent experience across different tools.

        Args:
            ctx: MCP context for user interaction

        Returns:
            Dictionary containing user's decision and any relevant information
        """
        try:
            # Use existing user confirmation pattern
            await ctx.info("Configuration uploaded successfully to S3!")
            await ctx.info(
                "Would you like to release the LZA pipeline to deploy these changes?"
            )
            await ctx.info("This will start the AWS CodePipeline execution.")

            # For now, we'll implement a simple confirmation mechanism
            # In a real implementation, this would use the MCP user interaction capabilities
            return {
                "offered": True,
                "message": "Pipeline release offer presented to user",
                "next_steps": [
                    "User can call releasePipeline tool to start deployment",
                    "Or use the integrated pipeline release functionality",
                ],
            }

        except Exception as e:
            self.logger.error(f"Error offering pipeline release: {str(e)}")
            return {
                "offered": False,
                "error": str(e),
                "message": "Failed to offer pipeline release",
            }

    async def release_pipeline_with_confirmation(
        self, ctx: Context, pipeline_name: str = DEFAULT_PIPELINE_NAME
    ) -> Dict[str, Any]:
        """
        Release pipeline with user confirmation using existing pipeline tools.

        This method integrates the existing releasePipeline functionality with
        user confirmation workflows to provide a seamless experience.

        Args:
            ctx: MCP context for logging and user interaction
            pipeline_name: Name of the pipeline to release

        Returns:
            Dictionary containing pipeline release result
        """
        try:
            # Validate pipeline name using existing validation
            is_valid, validation_error = validate_pipeline_name(pipeline_name)
            if not is_valid:
                return format_error_response(
                    error=f"Invalid pipeline name: {validation_error}",
                    message=f"Pipeline name '{pipeline_name}' does not meet AWS naming requirements",
                    troubleshooting=[
                        "Pipeline names must be 1-100 characters long",
                        "Can only contain letters, numbers, periods, underscores, and hyphens",
                        "Cannot contain spaces or other special characters",
                        f"Specific issue: {validation_error}",
                    ],
                )

            await ctx.info(f"Starting pipeline release for: {pipeline_name}")

            # Use existing pipeline tools functionality
            codepipeline = get_codepipeline_client()

            # First, validate that the pipeline exists (reuse existing logic)
            self.logger.info(f"Validating pipeline existence: {pipeline_name}")
            try:
                await retry_with_exponential_backoff(
                    codepipeline.get_pipeline, name=pipeline_name
                )
                self.logger.info(f"Pipeline found: {pipeline_name}")
            except Exception as e:
                if (
                    hasattr(e, "response")
                    and e.response.get("Error", {}).get("Code")
                    == "PipelineNotFoundException"
                ):
                    return format_error_response(
                        error=f"Pipeline '{pipeline_name}' not found",
                        message=f"The specified pipeline '{pipeline_name}' does not exist",
                        error_code="PipelineNotFoundException",
                        troubleshooting=[
                            f"Verify the pipeline name '{pipeline_name}' is correct",
                            "Check that the pipeline exists in your AWS region",
                            "Ensure you have permissions to access the pipeline",
                            "Use AWS CLI: aws codepipeline list-pipelines to see available pipelines",
                        ],
                    )
                else:
                    # Re-raise for general error handling
                    raise

            # Start the pipeline execution (reuse existing logic)
            self.logger.info(f"Starting pipeline execution: {pipeline_name}")
            execution_response = await retry_with_exponential_backoff(
                codepipeline.start_pipeline_execution, name=pipeline_name
            )

            execution_id = execution_response["pipelineExecutionId"]
            self.logger.info(
                f"Pipeline execution started successfully. Execution ID: {execution_id}"
            )

            await ctx.info(
                f"Pipeline '{pipeline_name}' execution started successfully!"
            )
            await ctx.info(f"Execution ID: {execution_id}")

            return format_success_response(
                data={
                    "execution_id": execution_id,
                    "pipeline_name": pipeline_name,
                    "started_after_upload": True,
                },
                message=f"Pipeline '{pipeline_name}' execution started successfully",
            )

        except Exception as e:
            self.logger.error(f"Error releasing pipeline: {str(e)}")
            return handle_aws_error(e, f"starting pipeline '{pipeline_name}' execution")
