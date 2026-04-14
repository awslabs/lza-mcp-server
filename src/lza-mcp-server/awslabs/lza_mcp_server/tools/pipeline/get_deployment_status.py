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

"""Unified LZA deployment status for both standard pipeline and ECS container deployments."""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
from .common import (
    validate_pipeline_name_local,
    validate_execution_id_local,
    validate_qualifier,
)

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    get_ecs_client,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from ...utils.input_validation import validate_string_input

# ECS task statuses that indicate the task is not yet running
_ECS_PENDING_STATUSES = {"PROVISIONING", "PENDING", "ACTIVATING"}

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)

# Simple cache implementation
_pipeline_cache: dict[str, dict] = {}
_cache_timestamps: dict[str, datetime] = {}


def get_cached_pipeline_metadata(pipeline_name: str):
    """Get cached pipeline metadata if available."""
    cache_key = f"pipeline_metadata_{pipeline_name}"
    return _pipeline_cache.get(cache_key)


def cache_pipeline_metadata(pipeline_name: str, metadata):
    """Cache pipeline metadata."""
    cache_key = f"pipeline_metadata_{pipeline_name}"
    _pipeline_cache[cache_key] = metadata
    _cache_timestamps[cache_key] = datetime.now()


def get_stage_description(stage_name: str) -> str:
    """Get a description of what happens in a specific LZA pipeline stage."""
    stage_descriptions = {
        "Source": "Retrieves LZA source code from GitHub and configuration files from the aws-accelerator-config repository",
        "Prepare": "Creates and validates AWS accounts, generates accounts via Control Tower Account Factory, and creates/validates OUs",
        "Accounts": "Validates all accounts are part of the AWS Organization and creates/attaches Service Control Policies (SCPs)",
        "Bootstrap": "Runs AWS CDK bootstrap to initialize environments and deploys CDK toolkit CloudFormation templates",
        "Logging": "Deploys centralized KMS keys, logging infrastructure, S3 buckets, Kinesis streams, and Data Firehose",
        "Organization": "Deploys AWS Organization-wide resources like trusted services, policies, Cost and Usage Reports, and Budgets",
        "SecurityAudit": "Deploys security service dependencies for Macie, GuardDuty, Security Hub in the audit account",
        "Deploy": "Deploys infrastructure across multiple sub-actions including networking, security, operations, and customizations",
    }
    return stage_descriptions.get(stage_name, f"Stage: {stage_name}")


def get_action_description(action_name: str) -> str:
    """Get a description of what happens in a specific LZA pipeline action."""
    action_descriptions = {
        "Network_Prepare": "Creates Transit Gateway and RAM shares",
        "Network_VPCs": "Deploys VPCs, subnets, endpoints, and DNS resources",
    }
    return action_descriptions.get(action_name, f"Action: {action_name}")


async def _check_ecs_task_status(
    ctx: Context,
    qualifier: str,
) -> Optional[Dict[str, Any]]:
    """Check for active ECS tasks matching the qualifier's cluster.

    Discovers the ECS cluster by scanning for a cluster name containing the
    qualifier, then lists RUNNING tasks and describes them to get lastStatus.

    Returns a dict with task status info if an active task is found
    (PROVISIONING, PENDING, ACTIVATING, or RUNNING with no logs yet),
    or None if no active tasks exist (fall through to log-based status).
    """
    try:
        ecs_client = get_ecs_client()

        # Find the cluster for this qualifier
        cluster_arn = None
        paginator = ecs_client.get_paginator("list_clusters")
        for page in paginator.paginate():
            for arn in page.get("clusterArns", []):
                cluster_name = arn.split("/")[-1]
                if qualifier.lower() in cluster_name.lower():
                    cluster_arn = arn
                    break
            if cluster_arn:
                break

        if not cluster_arn:
            logger.info(f"No ECS cluster found for qualifier '{qualifier}'")
            return None

        # List tasks with desiredStatus=RUNNING (default)
        list_response = await retry_with_exponential_backoff(
            ecs_client.list_tasks, cluster=cluster_arn
        )
        task_arns = list_response.get("taskArns", [])

        if not task_arns:
            return None

        # Describe tasks to get lastStatus
        describe_response = await retry_with_exponential_backoff(
            ecs_client.describe_tasks, cluster=cluster_arn, tasks=task_arns
        )
        tasks = describe_response.get("tasks", [])

        if not tasks:
            return None

        # Use the most recently created task
        tasks.sort(key=lambda t: t.get("createdAt", 0), reverse=True)
        task = tasks[0]
        last_status = task.get("lastStatus", "UNKNOWN")
        task_arn = task.get("taskArn", "")
        task_id = task_arn.split("/")[-1] if task_arn else "unknown"
        created_at = task.get("createdAt")

        if last_status in _ECS_PENDING_STATUSES:
            return {
                "success": True,
                "deployment_type": "ecs_container",
                "qualifier": qualifier,
                "task_id": task_id,
                "deployment_status": last_status,
                "phase_reached": None,
                "has_errors": False,
                "specific_error": None,
                "first_event_time": None,
                "last_event_time": None,
                "total_log_events": 0,
                "created_at": created_at.isoformat() if created_at else None,
                "message": f"ECS task is {last_status} — container has not started yet",
            }

        # Task is RUNNING — caller will check if logs exist yet
        return {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": qualifier,
            "task_id": task_id,
            "deployment_status": "RUNNING",
            "last_status": last_status,
            "created_at": created_at.isoformat() if created_at else None,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ClusterNotFoundException":
            logger.info(f"ECS cluster not found for qualifier '{qualifier}'")
        else:
            logger.warning(f"Error checking ECS tasks for qualifier '{qualifier}': {e}")
        return None
    except Exception as e:
        logger.warning(f"Error checking ECS tasks for qualifier '{qualifier}': {e}")
        return None


async def tool_get_deployment_status(
    ctx: Context,
    qualifier: Optional[str] = None,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get current deployment status and execution progress for LZA deployments.

    Supports both standard CodePipeline deployments and ECS container deployments.
    Call checkAwsConnectivity first to determine deployment type and qualifier.
    For standard deployments, omit the qualifier.
    For external pipeline deployments, pass the qualifier from checkAwsConnectivity.
    When a qualifier is provided, both CodePipeline ({qualifier}-pipeline) and
    ECS container logs (/ecs/{qualifier}-lza-deployment) are checked, since
    customers may deploy either or both installer stacks for the same qualifier.

    LZA Pipeline Stage Descriptions:
    1. **Source** - Retrieves LZA source code from GitHub and configuration files
    2. **Build** - Transpiles the LZA source code and performs input/type validation
    3. **Prepare** - Creates and validates AWS accounts via Control Tower Account Factory
    4. **Accounts** - Validates accounts are part of the AWS Organization, attaches SCPs
    5. **Bootstrap** - Runs AWS CDK bootstrap to initialize environments
    6. **Review** (optional) - Runs CDK diff and provides manual approval gate
    7. **Logging** - Deploys centralized KMS keys, logging infrastructure, S3 buckets
    8. **Organization** - Deploys Organization-wide resources like trusted services, policies
    9. **SecurityAudit** - Deploys security service dependencies for Macie, GuardDuty, Security Hub
    10. **Deploy** - Contains multiple sub-actions (networking, security, operations, customizations)

    Args:
        ctx: MCP context for logging and user feedback
        qualifier: LZA Accelerator Qualifier for external pipeline deployments (e.g. "container-dev-1").
            Obtained from checkAwsConnectivity. When provided, checks both the
            CodePipeline ({qualifier}-pipeline) and ECS container CloudWatch Logs.
        pipeline_name: Name of the CodePipeline (standard deployments only, defaults to "AWSAccelerator-Pipeline")
        execution_id: Specific execution ID (standard deployments only, defaults to most recent)

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation succeeded
        - deployment_type: "standard" or "external_pipeline"
        - For standard: execution_id, pipeline_name, status, stage_progress, etc.
        - For external: qualifier, sources_checked, pipeline_status, container_status
        - message: Success or error message

    Example:
        await get_deployment_status(ctx)
        {
            "success": True,
            "deployment_type": "standard",
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "pipeline_name": "AWSAccelerator-Pipeline",
            "status": "IN_PROGRESS",
            "stage_progress": {...},
            "message": "Pipeline is on stage 'Deploy' (stage 10 of 10)"
        }
    """
    # Branch A: Standard pipeline deployment (no qualifier)
    if qualifier is None:
        logger.info("No qualifier provided — using standard pipeline status path")
        result = await _get_standard_pipeline_status(ctx, pipeline_name, execution_id)

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
    logger.info(
        f"Qualifier provided: {qualifier} — checking both CodePipeline and ECS container"
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
            ],
        )

    qualifier_pipeline_name = f"{qualifier}-pipeline"
    log_group_name = f"/ecs/{qualifier}-lza-deployment"

    await ctx.info(f"Getting deployment status for qualifier: {qualifier}")

    # Check CodePipeline ({qualifier}-pipeline)
    pipeline_status = None
    try:
        await ctx.info(f"Checking CodePipeline: {qualifier_pipeline_name}")
        pipeline_result = await _get_standard_pipeline_status(
            ctx, qualifier_pipeline_name, execution_id
        )
        if pipeline_result.get("error_code") != "PipelineNotFoundException":
            pipeline_status = pipeline_result
        else:
            logger.info(
                f"CodePipeline '{qualifier_pipeline_name}' not found — skipping"
            )
    except Exception as e:
        logger.warning(
            f"Error checking CodePipeline for qualifier '{qualifier}': {str(e)}"
        )

    # Check ECS task status first — detect pending/provisioning tasks
    container_status = None
    try:
        await ctx.info(f"Checking ECS task status for qualifier: {qualifier}")
        ecs_task_info = await _check_ecs_task_status(ctx, qualifier)

        if (
            ecs_task_info
            and ecs_task_info.get("deployment_status") in _ECS_PENDING_STATUSES
        ):
            # Task exists but hasn't started yet — report immediately
            container_status = {
                "success": True,
                "deployment_type": "ecs_container",
                "qualifier": qualifier,
                "log_group": log_group_name,
                "task_id": ecs_task_info.get("task_id"),
                "deployment_status": ecs_task_info["deployment_status"],
                "phase_reached": None,
                "has_errors": False,
                "specific_error": None,
                "first_event_time": None,
                "last_event_time": None,
                "total_log_events": 0,
                "created_at": ecs_task_info.get("created_at"),
                "message": ecs_task_info["message"],
            }
        else:
            # No pending task or task is RUNNING — check logs
            await ctx.info(f"Checking ECS container logs: {log_group_name}")
            from .diagnose_deployment_errors import (
                _find_most_recent_deployment_stream,
                _find_deployment_stream_by_task_id,
                _analyze_deployment_log_stream,
                _ECS_LOG_STREAM_PREFIX,
            )
            from ...aws_access import get_logs_client

            logs_client = get_logs_client()

            # When an active ECS task is detected, look for its specific
            # log stream so we don't accidentally read a previous deployment's logs.
            # Fall back to most-recent-stream only when no task is detected.
            active_task_id = ecs_task_info.get("task_id") if ecs_task_info else None

            if active_task_id:
                target_stream = await _find_deployment_stream_by_task_id(
                    logs_client, log_group_name, active_task_id
                )
            else:
                target_stream = await _find_most_recent_deployment_stream(
                    logs_client, log_group_name
                )

            if target_stream:
                stream_name = target_stream["logStreamName"]
                task_id = stream_name[len(_ECS_LOG_STREAM_PREFIX) :]
                detail = await _analyze_deployment_log_stream(
                    ctx,
                    logs_client,
                    log_group_name,
                    stream_name,
                    task_id,
                    target_stream,
                )
                if detail:
                    deployment_status = detail.get("deployment_status", "UNKNOWN")
                    container_status = {
                        "success": True,
                        "deployment_type": "ecs_container",
                        "qualifier": qualifier,
                        "log_group": log_group_name,
                        "task_id": detail.get("task_id"),
                        "deployment_status": deployment_status,
                        "phase_reached": detail.get("phase_reached"),
                        "has_errors": detail.get("specific_error") is not None,
                        "specific_error": detail.get("specific_error"),
                        "first_event_time": detail.get("first_event_time"),
                        "last_event_time": detail.get("last_event_time"),
                        "total_log_events": detail.get("total_log_events"),
                        "message": f"ECS container deployment status: {deployment_status}",
                    }
                elif active_task_id:
                    # Task's stream exists but analysis returned nothing
                    container_status = {
                        "success": True,
                        "deployment_type": "ecs_container",
                        "qualifier": qualifier,
                        "log_group": log_group_name,
                        "task_id": active_task_id,
                        "deployment_status": "RUNNING",
                        "phase_reached": None,
                        "has_errors": False,
                        "specific_error": None,
                        "first_event_time": None,
                        "last_event_time": None,
                        "total_log_events": 0,
                        "created_at": ecs_task_info.get("created_at"),
                        "message": "ECS task is RUNNING but no deployment logs available yet",
                    }
            elif active_task_id:
                # Task is RUNNING but its log stream doesn't exist yet
                container_status = {
                    "success": True,
                    "deployment_type": "ecs_container",
                    "qualifier": qualifier,
                    "log_group": log_group_name,
                    "task_id": active_task_id,
                    "deployment_status": "RUNNING",
                    "phase_reached": None,
                    "has_errors": False,
                    "specific_error": None,
                    "first_event_time": None,
                    "last_event_time": None,
                    "total_log_events": 0,
                    "created_at": ecs_task_info.get("created_at"),
                    "message": "ECS task is RUNNING but no deployment logs available yet",
                }
            else:
                logger.info(f"No deployment streams found in '{log_group_name}'")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            logger.info(f"Log group '{log_group_name}' not found — skipping")
        else:
            logger.warning(
                f"Error checking ECS container logs for qualifier '{qualifier}': {str(e)}"
            )
    except Exception as e:
        logger.warning(
            f"Error checking ECS container logs for qualifier '{qualifier}': {str(e)}"
        )

    # Build combined response
    sources_found = []
    if pipeline_status:
        sources_found.append("CodePipeline")
    if container_status:
        sources_found.append("ECS container")

    if not sources_found:
        return format_error_response(
            error="No deployment infrastructure found for the specified qualifier",
            message="Neither the CodePipeline nor the ECS log group were found",
            troubleshooting=[
                "Verify the qualifier is correct",
                "Check that the deployment exists in your configured region",
                "Run checkAwsConnectivity to detect available qualifiers",
                "The deployment may not have run yet",
            ],
        )

    message = (
        f"Deployment status for qualifier '{qualifier}' via: {', '.join(sources_found)}"
    )

    result = {
        "success": True,
        "deployment_type": "external_pipeline",
        "qualifier": qualifier,
        "sources_checked": sources_found,
        "message": message,
    }
    if pipeline_status:
        result["pipeline_status"] = pipeline_status
    if container_status:
        result["container_status"] = container_status

    return result


# ---------------------------------------------------------------------------
# Branch A: Standard CodePipeline status
# ---------------------------------------------------------------------------


async def _get_standard_pipeline_status(
    ctx: Context,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get status for a standard CodePipeline deployment.

    Retrieves pipeline structure, execution details, and stage progression
    for the specified CodePipeline.
    """
    logger.info(f"Getting pipeline status for: {pipeline_name}")

    # Save whether a specific execution ID was provided
    original_execution_id_provided = execution_id is not None

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
            message="Pipeline name does not meet AWS naming requirements",
            troubleshooting=[
                "Pipeline names must be 1-100 characters long",
                "Can only contain letters, numbers, periods, underscores, and hyphens",
                "Cannot contain spaces or other special characters",
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
                ],
            )

    try:
        codepipeline = get_codepipeline_client()

        # Step 1: Get pipeline structure
        logger.info(f"Step 1: Getting pipeline structure for {pipeline_name}")

        cached_metadata = get_cached_pipeline_metadata(pipeline_name)
        if cached_metadata:
            pipeline_stages = cached_metadata["stages"]
            total_stages = len(pipeline_stages)
            logger.info(f"Using cached pipeline metadata with {total_stages} stages")
        else:
            try:
                pipeline_response = await retry_with_exponential_backoff(
                    codepipeline.get_pipeline, name=pipeline_name
                )
                pipeline_stages = pipeline_response["pipeline"]["stages"]
                total_stages = len(pipeline_stages)

                cache_pipeline_metadata(
                    pipeline_name,
                    {"stages": pipeline_stages, "total_stages": total_stages},
                )

                stage_names = [stage["name"] for stage in pipeline_stages]
                logger.info(f"Pipeline found with {total_stages} stages: {stage_names}")
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    == "PipelineNotFoundException"
                ):
                    return format_error_response(
                        error="Pipeline not found",
                        message="The specified pipeline does not exist",
                        error_code="PipelineNotFoundException",
                        troubleshooting=[
                            "Verify the pipeline name is correct",
                            "Check that the pipeline exists in your configured region",
                            "Ensure you have permissions to access the pipeline",
                        ],
                    )
                raise

        # Step 2: Get recent executions
        if execution_id:
            logger.info(
                f"Step 2: Getting recent pipeline executions (specific execution ID provided: {execution_id})"
            )
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=5,
            )

            executions = executions_response["pipelineExecutionSummaries"]
            logger.info(f"Step 2: Found {len(executions)} recent executions")

            target_execution = None
            for exec_summary in executions:
                if exec_summary["pipelineExecutionId"] == execution_id:
                    target_execution = exec_summary
                    break

            if target_execution:
                logger.info(f"Found requested execution: {execution_id}")
            else:
                logger.info(
                    f"Execution not found in recent list, will try direct access: {execution_id}"
                )
        else:
            logger.info("Step 2: Getting most recent pipeline execution")
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=1,
            )

            executions = executions_response["pipelineExecutionSummaries"]
            logger.info(f"Step 2: Found {len(executions)} recent executions")

            if not executions:
                return {
                    "success": True,
                    "pipeline_name": pipeline_name,
                    "status": "NO_EXECUTIONS",
                    "total_stages": total_stages,
                    "stage_progress": {
                        "current_stage_number": 0,
                        "total_stages": total_stages,
                        "current_stage_name": None,
                        "current_action_name": None,
                        "progress_text": f"No executions found for pipeline (pipeline has {total_stages} stages)",
                    },
                    "message": f"No executions found for pipeline '{pipeline_name}'",
                }

            target_execution = executions[0]
            execution_id = target_execution["pipelineExecutionId"]
            logger.info(f"Using most recent execution: {execution_id}")

        # Step 3: Get detailed execution information
        logger.info(
            f"Step 3: Getting detailed execution information for: {execution_id}"
        )
        try:
            execution_response = await retry_with_exponential_backoff(
                codepipeline.get_pipeline_execution,
                pipelineName=pipeline_name,
                pipelineExecutionId=execution_id,
            )
            execution = execution_response["pipelineExecution"]
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                == "PipelineExecutionNotFoundException"
            ):
                return format_error_response(
                    error="Execution not found",
                    message="The specified execution ID does not exist for this pipeline",
                    error_code="PipelineExecutionNotFoundException",
                    troubleshooting=[
                        "Verify the execution ID is correct",
                        "The execution may have been deleted or expired",
                    ],
                )
            raise

        status = execution["status"].upper()
        execution_mode = execution.get("executionMode", "NORMAL")
        start_time = (
            execution["creationTime"].isoformat()
            if "creationTime" in execution
            else None
        )
        end_time = (
            execution.get("lastUpdateTime", {}).isoformat()
            if execution.get("lastUpdateTime")
            else None
        )

        logger.info(f"Execution {execution_id}: status={status}, mode={execution_mode}")

        # Step 4: Get current pipeline state
        logger.info("Step 4: Getting current pipeline state")
        state_response = await retry_with_exponential_backoff(
            codepipeline.get_pipeline_state, name=pipeline_name
        )
        stage_states = state_response["stageStates"]

        # Step 5: Find in-progress stages
        current_stage = None
        current_action = None
        current_stage_number = 0
        in_progress_stages = []
        completed_stages = 0

        if stage_states:
            for i, stage_state in enumerate(stage_states):
                stage_name = stage_state["stageName"]
                if "latestExecution" in stage_state:
                    latest_execution = stage_state["latestExecution"]
                    stage_status = latest_execution.get("status", "Unknown")

                    if stage_status.upper() == "INPROGRESS":
                        in_progress_stages.append(
                            {
                                "stage_number": i + 1,
                                "stage_name": stage_name,
                                "execution_id": latest_execution.get(
                                    "pipelineExecutionId", "Unknown"
                                ),
                            }
                        )
                    elif stage_status.upper() == "SUCCEEDED":
                        completed_stages += 1

            logger.info(
                f"Found {len(in_progress_stages)} in-progress stages and {completed_stages} completed stages"
            )

            if in_progress_stages:
                current_stage_info = in_progress_stages[0]
                current_stage = current_stage_info["stage_name"]
                current_stage_number = current_stage_info["stage_number"]

                stage_state = stage_states[current_stage_number - 1]
                if "actionStates" in stage_state:
                    for action_state in stage_state["actionStates"]:
                        if "latestExecution" in action_state:
                            action_execution = action_state["latestExecution"]
                            if (
                                action_execution.get("status", "").upper()
                                == "INPROGRESS"
                            ):
                                current_action = action_state["actionName"]
                                break

        # Determine current stage from execution status if not found from stage states
        if not current_stage:
            if status.upper() == "INPROGRESS":
                current_stage_number = 1
                current_stage = pipeline_stages[0]["name"] if pipeline_stages else None
            elif status in ["SUCCEEDED", "FAILED", "STOPPED", "STOPPING"]:
                current_stage_number = total_stages
                current_stage = pipeline_stages[-1]["name"] if pipeline_stages else None
            else:
                current_stage_number = 0
                current_stage = None

        # Create stage progress information
        if current_stage:
            progress_text = f"Currently on stage {current_stage_number} of {total_stages}: {current_stage}"
            if current_action:
                progress_text += f" (action: {current_action})"
            if completed_stages > 0:
                progress_text += f" - {completed_stages} stages completed"
        elif status.upper() in ["SUCCEEDED", "FAILED", "STOPPED", "STOPPING"]:
            progress_text = f"Pipeline execution {status.lower()}"
        else:
            progress_text = f"Pipeline has {total_stages} stages (status: {status})"

        stage_progress = {
            "current_stage_number": current_stage_number,
            "total_stages": total_stages,
            "current_stage_name": current_stage,
            "current_action_name": current_action,
            "completed_stages": completed_stages,
            "progress_text": progress_text,
            "current_stage_description": get_stage_description(current_stage)
            if current_stage
            else None,
            "current_action_description": get_action_description(current_action)
            if current_action
            else None,
        }

        response_data = {
            "execution_id": execution_id,
            "pipeline_name": pipeline_name,
            "status": status,
            "stage_progress": stage_progress,
        }

        if start_time:
            response_data["start_time"] = start_time
        if end_time:
            response_data["end_time"] = end_time
        if current_stage:
            response_data["current_stage"] = current_stage
        if current_action:
            response_data["current_action"] = current_action

        # Create message based on status
        if status.upper() == "INPROGRESS":
            if current_stage:
                message = f"Pipeline is on stage '{current_stage}' (stage {current_stage_number} of {total_stages})"
                if completed_stages > 0:
                    message += f" - {completed_stages} stages completed"
            else:
                message = "Pipeline execution is in progress but no stages are currently active"
        elif current_stage and original_execution_id_provided:
            message = f"Pipeline is on stage '{current_stage}' (stage {current_stage_number} of {total_stages})"
        elif status.upper() == "FAILED":
            message = "Pipeline execution failed"
        elif status.upper() == "SUCCEEDED":
            message = "Pipeline execution completed successfully"
        elif status.upper() in ["STOPPED", "STOPPING"]:
            message = "Pipeline execution was stopped"
        else:
            message = f"Pipeline execution status: {status}"

        logger.info(
            f"Pipeline status retrieved successfully. Status: {status}, Stage: {current_stage_number}/{total_stages}"
        )

        response = {"success": True, "message": message}
        response.update(response_data)
        return response

    except Exception as e:
        logger.error(f"Error getting pipeline status: {str(e)}")
        return handle_aws_error(e, f"getting pipeline status for '{pipeline_name}'")
