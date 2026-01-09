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
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
from .common import (
    truncate_logs,
    validate_pipeline_name_local,
    validate_execution_id_local,
    extract_create_failed_error,
)

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    retry_with_exponential_backoff,
    handle_aws_error,
    get_codebuild_client,
    get_logs_client,
)
from ...utils.input_validation import validate_string_input

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_diagnose_pipeline_errors(
    ctx: Context,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Automatically detect and retrieve detailed error information for failed pipeline executions.

    This tool identifies failed actions in a pipeline execution and retrieves both
    the error details from pipeline state and detailed CodeBuild logs when available.
    For LZA pipelines, it extracts specific CloudFormation stack failures and CDK errors
    to provide actionable troubleshooting information.

    Args:
        ctx: MCP context for logging and user feedback
        pipeline_name: Name of the CodePipeline to diagnose (defaults to "AWSAccelerator-Pipeline")
        execution_id: Specific execution ID to diagnose (optional, defaults to most recent failed execution)

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation succeeded
        - pipeline_name: Name of the pipeline that was diagnosed
        - execution_id: The execution ID that was diagnosed
        - failed_actions: List of failed actions with error details, CodeBuild logs, and specific error extraction
        - message: Success or error message
        - error: Error details if the operation failed
        - troubleshooting: List of troubleshooting steps if there was an error

    Example:
        await diagnose_pipeline_errors(ctx, "AWSAccelerator-Pipeline")
        {
            "success": True,
            "pipeline_name": "AWSAccelerator-Pipeline",
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "failed_actions": [
                {
                    "stage_name": "Organization",
                    "action_name": "Organizations",
                    "action_type": "CodeBuild",
                    "error_code": "JobFailed",
                    "error_message": "Build terminated with state: FAILED...",
                    "error_summary": "Failed CodeBuild action: AWSAccelerator-OrganizationsStack CREATE_FAILED",
                    "external_execution_id": "AWSAccelerator-ToolkitProject:6e1cb627-7a7e-4d7a-bb2a-dad4f58ce775",
                    "external_execution_url": "https://console.aws.amazon.com/codebuild/...",
                    "codebuild_logs": "Full CodeBuild log content...",
                    "specific_error": "AWSAccelerator-OrganizationsStack-222634393892-eu-north-1 | 0/8 | 10:26:03 AM | CREATE_FAILED | Custom::CreatePolicy | AWSAccelerator-BackupPolicy/Resource/Default"
                }
            ],
            "message": "Found 1 failed action(s) with detailed error analysis"
        }
    """
    logger.info(f"Diagnosing pipeline errors for: {pipeline_name}")

    # Validate pipeline_name input
    is_valid, validation_error = validate_string_input(
        pipeline_name, "pipeline_name", min_length=1, max_length=100
    )
    if not is_valid:
        return format_error_response(
            error=f"Invalid pipeline name: {validation_error}",
            message=validation_error,
            troubleshooting=[
                "Pipeline names must be 1-100 characters long",
                "Provide a valid pipeline name",
            ],
        )

    is_valid, validation_error = validate_pipeline_name_local(pipeline_name)
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

    if execution_id is not None:
        # Validate execution_id input
        is_valid, validation_error = validate_string_input(
            execution_id, "execution_id", min_length=1, max_length=100
        )
        if not is_valid:
            return format_error_response(
                error=f"Invalid execution ID: {validation_error}",
                message=validation_error,
                troubleshooting=[
                    "Execution IDs must be valid strings",
                    "Provide a valid execution ID",
                ],
            )

        is_valid, validation_error = validate_execution_id_local(execution_id)
        if not is_valid:
            return format_error_response(
                error=f"Invalid execution ID: {validation_error}",
                message=f"Execution ID '{execution_id}' does not meet AWS format requirements",
                troubleshooting=[
                    "Execution IDs must be valid UUIDs (36 characters with hyphens)",
                    "Format: 12345678-1234-1234-1234-123456789012",
                    f"Specific issue: {validation_error}",
                ],
            )

    try:
        # Create AWS clients
        codepipeline = get_codepipeline_client()

        # First, validate that the pipeline exists
        logger.info(f"Validating pipeline existence: {pipeline_name}")
        try:
            await retry_with_exponential_backoff(
                codepipeline.get_pipeline, name=pipeline_name
            )
            logger.info(f"Pipeline found: {pipeline_name}")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "PipelineNotFoundException":
                return format_error_response(
                    error=f"Pipeline '{pipeline_name}' not found",
                    message=f"The specified pipeline '{pipeline_name}' does not exist",
                    error_code="PipelineNotFoundException",
                    troubleshooting=[
                        f"Verify the pipeline name '{pipeline_name}' is correct",
                        f"Check that the pipeline exists in region: {AWS_REGION}",
                        "Ensure you have permissions to access the pipeline",
                        "Use AWS CLI: aws codepipeline list-pipelines to see available pipelines",
                    ],
                )
            else:
                # Re-raise for general error handling
                raise

        # Get execution details
        if execution_id:
            # Get specific execution
            logger.info(f"Getting specific execution: {execution_id}")
            try:
                execution_response = codepipeline.get_pipeline_execution(
                    pipelineName=pipeline_name, pipelineExecutionId=execution_id
                )
                execution = execution_response["pipelineExecution"]
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    == "PipelineExecutionNotFoundException"
                ):
                    return format_error_response(
                        error=f"Execution '{execution_id}' not found",
                        message=f"The specified execution ID '{execution_id}' does not exist for pipeline '{pipeline_name}'",
                        error_code="PipelineExecutionNotFoundException",
                        troubleshooting=[
                            "Verify the execution ID is correct",
                            "Check that the execution exists for this pipeline",
                            "Use AWS CLI: aws codepipeline list-pipeline-executions to see available executions",
                        ],
                    )
                else:
                    # Re-raise for general error handling
                    raise
        else:
            # Find most recent failed execution
            logger.info(
                f"Finding most recent failed execution for pipeline: {pipeline_name}"
            )
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=10,  # Check last 10 executions for failures
            )

            failed_execution = None
            for execution_summary in executions_response["pipelineExecutionSummaries"]:
                if execution_summary["status"].upper() == "FAILED":
                    failed_execution = execution_summary
                    break

            if not failed_execution:
                response = {
                    "success": True,
                    "pipeline_name": pipeline_name,
                    "failed_actions": [],
                    "message": f"No failed executions found for pipeline '{pipeline_name}'",
                }
                return response

            execution_id = failed_execution["pipelineExecutionId"]

            # Get detailed execution information
            execution_response = await retry_with_exponential_backoff(
                codepipeline.get_pipeline_execution,
                pipelineName=pipeline_name,
                pipelineExecutionId=execution_id,
            )
            execution = execution_response["pipelineExecution"]

        # Check if execution actually failed (case-insensitive comparison)
        if execution["status"].upper() != "FAILED":
            response = {
                "success": True,
                "pipeline_name": pipeline_name,
                "execution_id": execution_id,
                "status": execution["status"],
                "failed_actions": [],
                "message": f"Execution '{execution_id}' has status '{execution['status']}' - no failures to diagnose",
            }
            return response

        # Get pipeline state to find failed actions
        logger.info(
            f"Getting pipeline state to identify failed actions: {execution_id}"
        )
        state_response = await retry_with_exponential_backoff(
            codepipeline.get_pipeline_state, name=pipeline_name
        )
        stage_states = state_response["stageStates"]

        failed_actions = []

        # Iterate through stages to find failed actions - simplified approach using pipeline state
        for stage_state in stage_states:
            await find_failures_in_stages(execution_id, failed_actions, stage_state)

        # Create response
        if failed_actions:
            # Count actions with detailed logs vs basic error info
            actions_with_logs = sum(
                1 for action in failed_actions if action.get("codebuild_logs")
            )
            actions_with_specific_errors = sum(
                1 for action in failed_actions if action.get("specific_error")
            )

            if actions_with_specific_errors > 0:
                message = f"Found {len(failed_actions)} failed action(s) with CREATE_FAILED error details"
            elif actions_with_logs > 0:
                message = f"Found {len(failed_actions)} failed action(s) with CodeBuild logs retrieved"
            else:
                message = f"Found {len(failed_actions)} failed action(s) with basic error details"
        else:
            message = f"No failed actions found in execution '{execution_id}'"

        logger.info(
            f"Pipeline error diagnosis completed. Found {len(failed_actions)} failed actions"
        )

        response = {
            "success": True,
            "pipeline_name": pipeline_name,
            "execution_id": execution_id,
            "failed_actions": failed_actions,
            "message": message,
        }
        return response

    except Exception as e:
        logger.error(f"Error diagnosing pipeline errors: {str(e)}")
        return handle_aws_error(e, f"diagnosing errors for pipeline '{pipeline_name}'")


async def find_failures_in_stages(execution_id, failed_actions, stage_state):
    stage_name = stage_state["stageName"]
    logger.info(f"Analyzing stage: {stage_name}")
    if "actionStates" in stage_state:
        for action_state in stage_state["actionStates"]:
            action_name = action_state["actionName"]
            # Get action type - handle both nested and flat structures
            action_type_id = action_state.get("actionTypeId", {})
            if isinstance(action_type_id, dict):
                action_type = action_type_id.get("provider", "Unknown")
            else:
                action_type = "Unknown"

            # Check if this action failed in our execution
            if "latestExecution" in action_state:
                action_execution = action_state["latestExecution"]
                action_status = action_execution.get("status", "Unknown")
                logger.info(
                    f"  Action: {action_name} ({action_type}) - Status: {action_status}"
                )

                # Check if this action failed
                # Note: We check the stage's latestExecution to see if it belongs to our pipeline execution
                stage_execution = stage_state.get("latestExecution", {})
                stage_execution_id = stage_execution.get("pipelineExecutionId")

                # Only process actions from the execution we're diagnosing
                if (
                    action_execution.get("status", "").upper() == "FAILED"
                    and stage_execution_id == execution_id
                ):
                    # Get error details directly from pipeline state (much simpler and more reliable!)
                    error_details = action_execution.get("errorDetails", {})
                    error_code = error_details.get("code", "Unknown")
                    error_message = error_details.get(
                        "message", "No error message available"
                    )

                    # Create failure details with all available information
                    failure_details = await build_failure_details_object(
                        action_execution,
                        action_name,
                        action_type,
                        error_code,
                        error_message,
                        stage_name,
                    )

                    # Try to get CREATE_FAILED error from CodeBuild logs
                    external_execution_id = action_execution.get("externalExecutionId")
                    if external_execution_id:
                        try:
                            await pull_codebuild_details(
                                action_name, external_execution_id, failure_details
                            )

                        except Exception as build_error:
                            logger.warning(
                                f"Could not retrieve CodeBuild details for {external_execution_id}: {build_error}"
                            )

                    logger.info(
                        f"Found failed action: {stage_name}/{action_name} - {error_code}: {error_message}"
                    )

                    # Add to failed actions list
                    failed_actions.append(failure_details)


async def build_failure_details_object(
    action_execution, action_name, action_type, error_code, error_message, stage_name
):
    failure_details = {
        "stage_name": stage_name,
        "action_name": action_name,
        "action_type": action_type,
        "error_code": error_code,
        "error_message": error_message,
        "error_summary": f"Failed {action_type} action ({error_code}): {error_message}",
        "external_execution_id": action_execution.get("externalExecutionId"),
        "external_execution_url": action_execution.get("externalExecutionUrl"),
        "last_status_change": action_execution.get("lastStatusChange"),
        "codebuild_logs": None,
        "specific_error": None,
    }
    return failure_details


async def pull_codebuild_details(action_name, external_execution_id, failure_details):
    logger.info(
        f"Retrieving CodeBuild logs for CREATE_FAILED error: {external_execution_id}"
    )
    # Get CodeBuild client
    codebuild = get_codebuild_client()
    # Get build details
    build_response = await retry_with_exponential_backoff(
        codebuild.batch_get_builds, ids=[external_execution_id]
    )
    if build_response["builds"]:
        build = build_response["builds"][0]

        # Get CloudWatch logs if available
        if (
            "logs" in build
            and "groupName" in build["logs"]
            and "streamName" in build["logs"]
        ):
            log_group = build["logs"]["groupName"]
            log_stream = build["logs"]["streamName"]

            try:
                await get_cloudwatch_logs(
                    action_name,
                    external_execution_id,
                    failure_details,
                    log_group,
                    log_stream,
                )

            except Exception as log_error:
                logger.warning(f"Could not retrieve CloudWatch logs: {log_error}")
        else:
            logger.info(
                f"No CloudWatch logs available for build {external_execution_id}"
            )
    else:
        logger.warning(f"No build details found for {external_execution_id}")


async def get_cloudwatch_logs(
    action_name, external_execution_id, failure_details, log_group, log_stream
):
    # Get CloudWatch Logs client
    logs_client = get_logs_client()
    logger.info(f"Retrieving CloudWatch logs from {log_group}/{log_stream}")
    # Get log events - get more events to find CREATE_FAILED
    log_response = await retry_with_exponential_backoff(
        logs_client.get_log_events,
        logGroupName=log_group,
        logStreamName=log_stream,
        limit=2000,  # Get more logs to find CREATE_FAILED
        startFromHead=True,  # Start from beginning to get all events
    )
    # Format log events and look for CREATE_FAILED
    log_events = log_response["events"]
    if log_events:
        await format_log_events_for_create_failed(
            action_name, failure_details, log_events
        )
    else:
        logger.warning(f"No log events found for {external_execution_id}")


async def format_log_events_for_create_failed(action_name, failure_details, log_events):
    log_lines = []
    for event in log_events:
        message = event["message"]
        log_lines.append(message)
    logs_content = "\n".join(log_lines)
    # Look specifically for CREATE_FAILED error first
    create_failed_error = extract_create_failed_error(logs_content)
    if create_failed_error:
        failure_details["specific_error"] = create_failed_error
        failure_details["error_summary"] = f"CREATE_FAILED: {create_failed_error}"
        logger.info(f"Found CREATE_FAILED error for {action_name}")
    else:
        logger.info(f"No CREATE_FAILED error found in logs for {action_name}")
        # If no CloudFormation CREATE_FAILED error found, search for general error pattern
        error_line = extract_error_line(logs_content)
        if error_line:
            failure_details["specific_error"] = error_line
            failure_details["error_summary"] = f"Error: {error_line}"
            logger.info(f"Found general error pattern for {action_name}")
        else:
            logger.info(f"No specific error patterns found in logs for {action_name}")
    # Store truncated logs for reference
    failure_details["codebuild_logs"] = truncate_logs(logs_content)


def extract_error_line(logs_content: str) -> str:
    """Extract the first '| error |' line from CodeBuild logs.

    This searches for general error patterns when CloudFormation CREATE_FAILED
    errors are not found, providing additional error detection capability.

    Args:
        logs_content: The full build log content

    Returns:
        str: The first '| error |' line found, or None if none found
    """
    if not logs_content:
        return ""

    lines = logs_content.split("\n")

    # Look specifically for '| error |' lines
    for line in lines:
        if "| error |" in line:
            clean_line = line.strip()
            if clean_line:
                return clean_line

    return ""
