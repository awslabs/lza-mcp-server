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

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
from .manage_pipeline_tools import validate_pipeline_name, format_success_response
from ...aws_access import format_error_response, get_codepipeline_client, retry_with_exponential_backoff, \
    handle_aws_error

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_release_pipeline(
            ctx: Context,
            pipeline_name: str = DEFAULT_PIPELINE_NAME
    ) -> Dict[str, Any]:
    """Trigger execution of the specified AWS CodePipeline.

    This tool starts a new execution of the specified CodePipeline, typically used
    to deploy LZA configuration changes. It validates that the pipeline exists
    before attempting to start the execution.

    Args:
        ctx: MCP context for logging and user feedback
        pipeline_name: Name of the CodePipeline to execute (defaults to "AWSAccelerator-Pipeline")

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation succeeded
        - execution_id: The unique ID of the started pipeline execution
        - pipeline_name: Name of the pipeline that was started
        - message: Success or error message
        - error: Error details if the operation failed
        - troubleshooting: List of troubleshooting steps if there was an error

    Example:
        await release_pipeline(ctx, "AWSAccelerator-Pipeline")
        {
            "success": True,
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "pipeline_name": "AWSAccelerator-Pipeline",
            "message": "Pipeline execution started successfully"
        }
    """
    logger.info(f"Starting pipeline release for: {pipeline_name}")

    # Validate pipeline name format
    is_valid, validation_error = validate_pipeline_name(pipeline_name)
    if not is_valid:
        return format_error_response(
            error=f"Invalid pipeline name: {validation_error}",
            message=f"Pipeline name '{pipeline_name}' does not meet AWS naming requirements",
            troubleshooting=[
                "Pipeline names must be 1-100 characters long",
                "Can only contain letters, numbers, periods, underscores, and hyphens",
                "Cannot contain spaces or other special characters",
                f"Specific issue: {validation_error}"
            ]
        )

    try:
        # Create CodePipeline client
        codepipeline = get_codepipeline_client()

        # First, validate that the pipeline exists
        logger.info(f"Validating pipeline existence: {pipeline_name}")
        try:
            pipeline_response = await retry_with_exponential_backoff(
                codepipeline.get_pipeline, name=pipeline_name
            )
            logger.info(f"Pipeline found: {pipeline_name}")
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'PipelineNotFoundException':
                return format_error_response(
                    error=f"Pipeline '{pipeline_name}' not found",
                    message=f"The specified pipeline '{pipeline_name}' does not exist",
                    error_code="PipelineNotFoundException",
                    troubleshooting=[
                        f"Verify the pipeline name '{pipeline_name}' is correct",
                        f"Check that the pipeline exists in region: {AWS_REGION}",
                        "Ensure you have permissions to access the pipeline",
                        "Use AWS CLI: aws codepipeline list-pipelines to see available pipelines"
                    ]
                )
            else:
                # Re-raise for general error handling
                raise

        # Start the pipeline execution
        logger.info(f"Starting pipeline execution: {pipeline_name}")
        execution_response = await retry_with_exponential_backoff(
            codepipeline.start_pipeline_execution, name=pipeline_name
        )

        execution_id = execution_response['pipelineExecutionId']
        logger.info(f"Pipeline execution started successfully. Execution ID: {execution_id}")

        return format_success_response(
            data={
                "execution_id": execution_id,
                "pipeline_name": pipeline_name
            },
            message=f"Pipeline '{pipeline_name}' execution started successfully"
        )

    except Exception as e:
        logger.error(f"Error starting pipeline execution: {str(e)}")
        return handle_aws_error(e, f"starting pipeline '{pipeline_name}' execution")
