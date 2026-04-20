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

"""Unified LZA deployment error diagnosis for both standard pipeline and ECS container deployments."""

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
    validate_qualifier,
    extract_create_failed_error,
    determine_ecs_deployment_status,
)

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    get_codebuild_client,
    get_logs_client,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from ...utils.input_validation import validate_string_input

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)

# Phase markers used in ECS container deployment logs
_ECS_PHASE_MARKERS = ["Phase 1:", "Phase 2:", "Phase 3:"]

# Log stream prefix used by ECS container deployments
_ECS_LOG_STREAM_PREFIX = "ecs/lza-deployment-container/"


async def tool_diagnose_deployment_errors(
    ctx: Context,
    qualifier: Optional[str] = None,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Diagnose failed LZA deployments — supports standard pipeline, ECS container, and combined deployments.

    Call checkAwsConnectivity first to determine deployment type and qualifier.
    For standard deployments, omit the qualifier.
    For external pipeline deployments, pass the qualifier from checkAwsConnectivity.
    When a qualifier is provided, both CodePipeline ({qualifier}-pipeline) and
    ECS container logs (/ecs/{qualifier}-lza-deployment) are checked, since
    customers may deploy either or both installer stacks for the same qualifier.

    Args:
        ctx: MCP context for logging and user feedback
        qualifier: LZA Accelerator Qualifier for external pipeline deployments (e.g. "container-dev-1").
            Obtained from checkAwsConnectivity. When provided, diagnoses both the
            CodePipeline ({qualifier}-pipeline) and ECS container CloudWatch Logs.
        pipeline_name: Name of the CodePipeline (standard deployments only, defaults to "AWSAccelerator-Pipeline")
        execution_id: Specific execution ID (standard deployments only, defaults to most recent failed)

    Returns:
        Dict with success, deployment_type, qualifier, and diagnosis results from
        both CodePipeline (pipeline_diagnosis) and ECS container (container_diagnosis)
        when a qualifier is provided, or failed_actions for standard deployments.
    """
    # Branch A: Standard pipeline deployment (no qualifier)
    if qualifier is None:
        logger.info("No qualifier provided — using standard pipeline diagnosis path")
        result = await _diagnose_standard_pipeline(ctx, pipeline_name, execution_id)

        # If the pipeline wasn't found, hint about qualifier
        if (
            not result.get("success")
            and result.get("error_code") == "PipelineNotFoundException"
        ):
            result["troubleshooting"] = result.get("troubleshooting", []) + [
                "If this is an external pipeline / ECS container deployment, provide the qualifier parameter.",
                "Run checkAwsConnectivity first to detect the deployment type and available qualifiers.",
            ]

        result["deployment_type"] = "standard"
        return result

    # Branch B: External pipeline deployment (qualifier provided)
    # Checks both CodePipeline ({qualifier}-pipeline) and ECS container logs
    logger.info(
        f"Qualifier provided: {qualifier} — diagnosing both CodePipeline and ECS container"
    )

    is_valid, validation_error = validate_string_input(
        qualifier, "qualifier", min_length=1, max_length=100
    )
    if not is_valid:
        return format_error_response(
            error=f"Invalid qualifier: {validation_error}",
            message=validation_error,
            troubleshooting=[
                "Qualifier must be 1-100 characters long",
                "Run checkAwsConnectivity to get valid qualifiers",
            ],
        )

    is_valid, validation_error = validate_qualifier(qualifier)
    if not is_valid:
        return format_error_response(
            error=f"Invalid qualifier: {validation_error}",
            message="Qualifier does not meet format requirements",
            troubleshooting=[
                "Qualifiers can only contain letters, numbers, and hyphens",
                "Run checkAwsConnectivity to get valid qualifiers",
                f"Specific issue: {validation_error}",
            ],
        )

    # Deterministic pipeline name from LZA installer-stack.ts convention
    qualifier_pipeline_name = f"{qualifier}-pipeline"
    log_group_name = f"/ecs/{qualifier}-lza-deployment"

    await ctx.info(
        f"Diagnosing external pipeline deployment for qualifier: {qualifier}"
    )

    # Check CodePipeline ({qualifier}-pipeline)
    pipeline_diagnosis = None
    try:
        await ctx.info(f"Checking CodePipeline: {qualifier_pipeline_name}")
        pipeline_result = await _diagnose_standard_pipeline(
            ctx, qualifier_pipeline_name, execution_id
        )
        # Only include if the pipeline actually exists
        if pipeline_result.get("error_code") != "PipelineNotFoundException":
            pipeline_diagnosis = pipeline_result
        else:
            logger.info(
                f"CodePipeline '{qualifier_pipeline_name}' not found — skipping"
            )
    except Exception as e:
        logger.warning(
            f"Error checking CodePipeline for qualifier '{qualifier}': {str(e)}"
        )

    # Check ECS container logs
    container_diagnosis = None
    try:
        await ctx.info(f"Checking ECS container logs: {log_group_name}")
        container_result = await _diagnose_container_deployment(
            ctx, qualifier, log_group_name
        )
        # Only include if the log group actually exists
        if container_result.get("error_code") != "ResourceNotFoundException":
            container_diagnosis = container_result
        else:
            logger.info(f"Log group '{log_group_name}' not found — skipping")
    except Exception as e:
        logger.warning(
            f"Error checking ECS container logs for qualifier '{qualifier}': {str(e)}"
        )

    # Build combined response
    sources_found = []
    if pipeline_diagnosis:
        sources_found.append("CodePipeline")
    if container_diagnosis:
        sources_found.append("ECS container")

    if not sources_found:
        return format_error_response(
            error=f"No deployment infrastructure found for qualifier '{qualifier}'",
            message=f"Neither CodePipeline '{qualifier_pipeline_name}' nor "
            f"log group '{log_group_name}' were found in region {AWS_REGION}",
            troubleshooting=[
                f"Verify the qualifier '{qualifier}' is correct",
                f"Check that the deployment exists in region: {AWS_REGION}",
                "Run checkAwsConnectivity to detect available qualifiers",
                "The deployment may not have run yet",
            ],
        )

    message = f"Diagnosed deployment for qualifier '{qualifier}' via: {', '.join(sources_found)}"

    return {
        "success": True,
        "deployment_type": "external_pipeline",
        "qualifier": qualifier,
        "sources_checked": sources_found,
        "pipeline_diagnosis": pipeline_diagnosis,
        "container_diagnosis": container_diagnosis,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Branch A: Standard CodePipeline diagnosis
# ---------------------------------------------------------------------------


async def _diagnose_standard_pipeline(
    ctx: Context,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Diagnose failed standard CodePipeline executions.

    Identifies failed actions, retrieves CodeBuild logs, and extracts
    CloudFormation CREATE_FAILED errors for actionable troubleshooting.
    """
    logger.info(f"Diagnosing pipeline errors for: {pipeline_name}")

    # Validate pipeline_name
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
            message="Pipeline name does not meet AWS naming requirements",
            troubleshooting=[
                "Pipeline names must be 1-100 characters long",
                "Can only contain letters, numbers, periods, underscores, and hyphens",
                f"Specific issue: {validation_error}",
            ],
        )

    if execution_id is not None:
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
                message="Execution ID does not meet AWS format requirements",
                troubleshooting=[
                    "Execution IDs must be valid UUIDs (36 characters with hyphens)",
                    "Format: 12345678-1234-1234-1234-123456789012",
                    f"Specific issue: {validation_error}",
                ],
            )

    try:
        codepipeline = get_codepipeline_client()

        # Validate pipeline exists
        try:
            await retry_with_exponential_backoff(
                codepipeline.get_pipeline, name=pipeline_name
            )
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
                    ],
                )
            raise

        # Get execution details
        if execution_id:
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
                        ],
                    )
                raise
        else:
            # Find most recent failed execution
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=10,
            )

            failed_execution = None
            for summary in executions_response["pipelineExecutionSummaries"]:
                if summary["status"].upper() == "FAILED":
                    failed_execution = summary
                    break

            if not failed_execution:
                return {
                    "success": True,
                    "pipeline_name": pipeline_name,
                    "failed_actions": [],
                    "message": f"No failed executions found for pipeline '{pipeline_name}'",
                }

            execution_id = failed_execution["pipelineExecutionId"]
            execution_response = await retry_with_exponential_backoff(
                codepipeline.get_pipeline_execution,
                pipelineName=pipeline_name,
                pipelineExecutionId=execution_id,
            )
            execution = execution_response["pipelineExecution"]

        # Check if execution actually failed
        if execution["status"].upper() != "FAILED":
            return {
                "success": True,
                "pipeline_name": pipeline_name,
                "execution_id": execution_id,
                "status": execution["status"],
                "failed_actions": [],
                "message": f"Execution '{execution_id}' has status '{execution['status']}' - no failures to diagnose",
            }

        # Get pipeline state to find failed actions
        state_response = await retry_with_exponential_backoff(
            codepipeline.get_pipeline_state, name=pipeline_name
        )
        failed_actions: list[dict] = []

        for stage_state in state_response["stageStates"]:
            await _find_failures_in_stage(execution_id, failed_actions, stage_state)

        # Build message
        if failed_actions:
            has_specific = sum(1 for a in failed_actions if a.get("specific_error"))
            has_logs = sum(1 for a in failed_actions if a.get("codebuild_logs"))
            if has_specific > 0:
                message = f"Found {len(failed_actions)} failed action(s) with CREATE_FAILED error details"
            elif has_logs > 0:
                message = f"Found {len(failed_actions)} failed action(s) with CodeBuild logs retrieved"
            else:
                message = f"Found {len(failed_actions)} failed action(s) with basic error details"
        else:
            message = f"No failed actions found in execution '{execution_id}'"

        return {
            "success": True,
            "pipeline_name": pipeline_name,
            "execution_id": execution_id,
            "failed_actions": failed_actions,
            "message": message,
        }

    except Exception as e:
        logger.error(f"Error diagnosing pipeline errors: {str(e)}")
        return handle_aws_error(e, f"diagnosing errors for pipeline '{pipeline_name}'")


async def _find_failures_in_stage(
    execution_id: str, failed_actions: list, stage_state: dict
) -> None:
    """Find failed actions within a pipeline stage for the given execution."""
    stage_name = stage_state["stageName"]
    if "actionStates" not in stage_state:
        return

    for action_state in stage_state["actionStates"]:
        action_name = action_state["actionName"]
        action_type_id = action_state.get("actionTypeId", {})
        action_type = (
            action_type_id.get("provider", "Unknown")
            if isinstance(action_type_id, dict)
            else "Unknown"
        )

        if "latestExecution" not in action_state:
            continue

        action_execution = action_state["latestExecution"]
        stage_execution = stage_state.get("latestExecution", {})
        stage_execution_id = stage_execution.get("pipelineExecutionId")

        if (
            action_execution.get("status", "").upper() != "FAILED"
            or stage_execution_id != execution_id
        ):
            continue

        error_details = action_execution.get("errorDetails", {})
        error_code = error_details.get("code", "Unknown")
        error_message = error_details.get("message", "No error message available")

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

        external_execution_id = action_execution.get("externalExecutionId")
        if external_execution_id:
            try:
                await _pull_codebuild_details(
                    action_name, external_execution_id, failure_details
                )
            except Exception as build_error:
                logger.warning(
                    f"Could not retrieve CodeBuild details for {external_execution_id}: {build_error}"
                )

        failed_actions.append(failure_details)


async def _pull_codebuild_details(
    action_name: str, external_execution_id: str, failure_details: dict
) -> None:
    """Retrieve CodeBuild logs and extract errors for a failed action."""
    codebuild = get_codebuild_client()
    build_response = await retry_with_exponential_backoff(
        codebuild.batch_get_builds, ids=[external_execution_id]
    )

    if not build_response["builds"]:
        return

    build = build_response["builds"][0]
    if (
        "logs" not in build
        or "groupName" not in build["logs"]
        or "streamName" not in build["logs"]
    ):
        return

    logs_client = get_logs_client()
    log_response = await retry_with_exponential_backoff(
        logs_client.get_log_events,
        logGroupName=build["logs"]["groupName"],
        logStreamName=build["logs"]["streamName"],
        limit=2000,
        startFromHead=True,
    )

    log_events = log_response.get("events", [])
    if not log_events:
        return

    logs_content = "\n".join(event["message"] for event in log_events)

    create_failed = extract_create_failed_error(logs_content)
    if create_failed:
        failure_details["specific_error"] = create_failed
        failure_details["error_summary"] = f"CREATE_FAILED: {create_failed}"
    else:
        error_line = _extract_codebuild_error_line(logs_content)
        if error_line:
            failure_details["specific_error"] = error_line
            failure_details["error_summary"] = f"Error: {error_line}"

    failure_details["codebuild_logs"] = truncate_logs(logs_content)


def _extract_codebuild_error_line(logs_content: str) -> str:
    """Extract the first '| error |' line from CodeBuild logs."""
    if not logs_content:
        return ""
    for line in logs_content.split("\n"):
        if "| error |" in line:
            clean_line = line.strip()
            if clean_line:
                return clean_line
    return ""


# ---------------------------------------------------------------------------
# Branch B: ECS container deployment diagnosis via CloudWatch Logs
# ---------------------------------------------------------------------------


async def _diagnose_container_deployment(
    ctx: Context,
    qualifier: str,
    log_group_name: str,
) -> Dict[str, Any]:
    """Diagnose a container deployment by querying CloudWatch Logs directly.

    Uses DescribeLogStreams ordered by LastEventTime (descending) and paginates
    until the first stream matching the deployment prefix is found. This
    guarantees we get the most recent deployment regardless of how many
    streams exist. Works regardless of whether ECS tasks still exist.
    """
    logs_client = get_logs_client()

    logger.info(f"Finding most recent deployment log stream in: {log_group_name}")
    try:
        most_recent = await _find_most_recent_deployment_stream(
            logs_client, log_group_name
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            return format_error_response(
                error=f"Log group '{log_group_name}' not found",
                message=f"The CloudWatch log group '{log_group_name}' does not exist in region {AWS_REGION}",
                error_code="ResourceNotFoundException",
                troubleshooting=[
                    f"Verify the qualifier '{qualifier}' is correct",
                    f"Check that the log group exists in region: {AWS_REGION}",
                    "The deployment may not have run yet, or logs may have been deleted",
                    "Run checkAwsConnectivity to detect available qualifiers",
                ],
            )
        raise

    if not most_recent:
        return {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": qualifier,
            "log_group": log_group_name,
            "failed_deployments": [],
            "message": f"No deployment log streams found in '{log_group_name}'. No deployments have run, or logs have expired.",
        }

    stream_name = most_recent["logStreamName"]
    task_id = stream_name[len(_ECS_LOG_STREAM_PREFIX) :]
    detail = await _analyze_deployment_log_stream(
        ctx, logs_client, log_group_name, stream_name, task_id, most_recent
    )

    failed_deployments = [detail] if detail else []

    if failed_deployments:
        has_errors = sum(1 for d in failed_deployments if d.get("specific_error"))
        message = (
            "Found most recent deployment with specific error details"
            if has_errors > 0
            else "Found most recent deployment with log data"
        )
    else:
        message = (
            "Found most recent log stream but could not extract deployment details"
        )

    return {
        "success": True,
        "deployment_type": "ecs_container",
        "qualifier": qualifier,
        "log_group": log_group_name,
        "failed_deployments": failed_deployments,
        "message": message,
    }


async def _find_most_recent_deployment_stream(
    logs_client: Any,
    log_group_name: str,
) -> Optional[Dict[str, Any]]:
    """Find the most recent deployment log stream by paginating DescribeLogStreams.

    Uses orderBy=LastEventTime descending so the most recent streams come first.
    Paginates until a stream matching the deployment prefix is found, guaranteeing
    correctness even with thousands of streams.

    Args:
        logs_client: CloudWatch Logs boto3 client
        log_group_name: CloudWatch log group name

    Returns:
        The most recent deployment stream metadata dict, or None if not found
    """
    next_token = None

    while True:
        kwargs: Dict[str, Any] = {
            "logGroupName": log_group_name,
            "orderBy": "LastEventTime",
            "descending": True,
        }
        if next_token:
            kwargs["nextToken"] = next_token

        response = await retry_with_exponential_backoff(
            logs_client.describe_log_streams, **kwargs
        )

        for stream in response.get("logStreams", []):
            if stream.get("logStreamName", "").startswith(_ECS_LOG_STREAM_PREFIX):
                return stream

        next_token = response.get("nextToken")
        if not next_token:
            return None


async def _find_deployment_stream_by_task_id(
    logs_client: Any,
    log_group_name: str,
    task_id: str,
) -> Optional[Dict[str, Any]]:
    """Find a specific deployment log stream by ECS task ID.

    Constructs the expected stream name from the task ID and describes it directly,
    avoiding the ambiguity of selecting by LastEventTime which can return a
    previous deployment's stream.

    Args:
        logs_client: CloudWatch Logs boto3 client
        log_group_name: CloudWatch log group name
        task_id: ECS task ID to look up

    Returns:
        The stream metadata dict if found, or None if the stream doesn't exist yet
    """
    stream_name = f"{_ECS_LOG_STREAM_PREFIX}{task_id}"

    try:
        response = await retry_with_exponential_backoff(
            logs_client.describe_log_streams,
            logGroupName=log_group_name,
            logStreamNamePrefix=stream_name,
        )

        for stream in response.get("logStreams", []):
            if stream.get("logStreamName") == stream_name:
                return stream

    except ClientError:
        pass

    return None


async def _analyze_deployment_log_stream(
    ctx: Context,
    logs_client: Any,
    log_group_name: str,
    log_stream_name: str,
    task_id: str,
    stream_metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Analyze a single deployment log stream for errors.

    Paginates through all log events to ensure complete analysis.
    CloudWatch Logs GetLogEvents returns up to 1MB or 10,000 events per page.
    Pagination stops when nextForwardToken equals the token we sent.
    """
    max_events = 50000
    all_events: list[dict] = []
    next_token = None

    try:
        while len(all_events) < max_events:
            kwargs: Dict[str, Any] = {
                "logGroupName": log_group_name,
                "logStreamName": log_stream_name,
                "startFromHead": True,
                "limit": 10000,
            }
            if next_token:
                kwargs["nextToken"] = next_token

            log_response = await retry_with_exponential_backoff(
                logs_client.get_log_events, **kwargs
            )

            events = log_response.get("events", [])
            all_events.extend(events)

            new_token = log_response.get("nextForwardToken")
            if not new_token or new_token == next_token:
                break
            next_token = new_token
    except ClientError as e:
        if e.response.get("Error", {}).get("Code", "") == "ResourceNotFoundException":
            return None
        raise

    if not all_events:
        return None

    log_lines = [event["message"] for event in all_events]
    logs_content = "\n".join(log_lines)

    # Determine deployment status from log content
    deployment_status = determine_ecs_deployment_status(log_lines)

    # Detect last phase marker reached
    phase_reached = None
    for line in log_lines:
        for marker in _ECS_PHASE_MARKERS:
            if marker in line:
                phase_reached = line.strip()

    # Extract errors
    specific_error = None
    create_failed = extract_create_failed_error(logs_content)
    if create_failed:
        specific_error = create_failed
    else:
        error_line = _extract_ecs_error_line(logs_content)
        if error_line:
            specific_error = error_line

    return {
        "task_id": task_id,
        "log_stream": log_stream_name,
        "deployment_status": deployment_status,
        "phase_reached": phase_reached,
        "specific_error": specific_error,
        "first_event_time": stream_metadata.get("firstEventTimestamp"),
        "last_event_time": stream_metadata.get("lastEventTimestamp"),
        "total_log_events": len(all_events),
        "logs": truncate_logs(logs_content),
    }


def _extract_ecs_error_line(logs_content: str) -> Optional[str]:
    """Extract error lines from ECS container deployment logs."""
    if not logs_content:
        return None
    for line in logs_content.split("\n"):
        for pattern in ["| error |", "Error:", "FAILED", "[ERROR]"]:
            if pattern in line:
                clean_line = line.strip()
                if clean_line:
                    return clean_line
    return None
