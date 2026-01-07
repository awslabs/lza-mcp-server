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
from .common import validate_pipeline_name_local, validate_execution_id_local

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from ...utils.input_validation import validate_string_input

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)

# Simple cache implementation
_pipeline_cache = {}
_cache_timestamps = {}


def get_cached_pipeline_metadata(pipeline_name: str):
    """Get cached pipeline metadata if available."""
    cache_key = f"pipeline_metadata_{pipeline_name}"
    return _pipeline_cache.get(cache_key)


def cache_pipeline_metadata(pipeline_name: str, metadata):
    """Cache pipeline metadata."""
    cache_key = f"pipeline_metadata_{pipeline_name}"
    _pipeline_cache[cache_key] = metadata
    from datetime import datetime

    _cache_timestamps[cache_key] = datetime.now()


def get_stage_description(stage_name: str) -> str:
    """Get a description of what happens in a specific LZA pipeline stage."""
    stage_descriptions = {
        "Source": "Retrieves LZA source code from GitHub and configuration files from the aws-accelerator-config repository",
        "Build": "Transpiles the LZA source code and performs input/type validation for configuration files",
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


async def tool_get_pipeline_status(
    ctx: Context,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve current status and execution details for the specified CodePipeline.

    This tool provides comprehensive status information about a pipeline execution,
    including current stage progression, execution timeline, and detailed status.
    Uses the same approach as AWS CLI commands for accurate and reliable reporting.

    LZA Pipeline Stage Descriptions:
    1. **Source** - Retrieves LZA source code from GitHub and configuration files from the aws-accelerator-config repository
    2. **Build** - Transpiles the LZA source code and performs input/type validation for configuration files
    3. **Prepare** - Creates and validates AWS accounts, generates accounts via Control Tower Account Factory, and creates/validates OUs
    4. **Accounts** - Validates all accounts are part of the AWS Organization and creates/attaches Service Control Policies (SCPs)
    5. **Bootstrap** - Runs AWS CDK bootstrap to initialize environments and deploys CDK toolkit CloudFormation templates
    6. **Review** (optional) - Runs CDK diff against target accounts and provides manual approval gate for changes
    7. **Logging** - Deploys centralized KMS keys, logging infrastructure, S3 buckets, Kinesis streams, and Data Firehose
    8. **Organization** - Deploys AWS Organization-wide resources like trusted services, policies, Cost and Usage Reports, and Budgets
    9. **SecurityAudit** - Deploys security service dependencies for Macie, GuardDuty, Security Hub in the audit account
    10. **Deploy** - Contains multiple sub-actions:
        • **Network_Prepare** - Creates Transit Gateway and RAM shares
        • **Security** - Configures member account security services
        • **Operations** - Deploys users, groups, roles, and SAML providers
        • **Network_VPCs** - Deploys VPCs, subnets, endpoints, and DNS resources
        • **Security_Resources** - Deploys Config, CloudWatch metrics, and alarms
        • **Network_Associations** - Creates network associations and Gateway Load Balancer endpoints
        • **Customizations** (optional) - Deploys custom CloudFormation stacks/stacksets
        • **Finalize** - Removes quarantine SCPs from new accounts

    Equivalent AWS CLI commands:
    1. aws codepipeline get-pipeline --name PIPELINE
    2. aws codepipeline list-pipeline-executions --pipeline-name PIPELINE --max-items 5
    3. aws codepipeline get-pipeline-state --name PIPELINE --query 'stageStates[?latestExecution.status==`InProgress`]'

    Args:
        ctx: MCP context for logging and user feedback
        pipeline_name: Name of the CodePipeline to check (defaults to "AWSAccelerator-Pipeline")
        execution_id: Specific execution ID to check (optional, defaults to most recent)

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation succeeded
        - execution_id: The execution ID that was checked
        - pipeline_name: Name of the pipeline
        - status: Current execution status (SUCCEEDED, FAILED, IN_PROGRESS, etc.)
        - start_time: When the execution started (ISO format)
        - end_time: When the execution ended (ISO format, if completed)
        - current_stage: Name of the current stage being executed
        - current_action: Name of the current action being executed
        - stage_progress: Object with stage progression details including descriptions of what each stage/action does
        - message: Success or error message
        - error: Error details if the operation failed

    Example:
        await get_pipeline_status(ctx, "AWSAccelerator-Pipeline")
        {
            "success": True,
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "pipeline_name": "AWSAccelerator-Pipeline",
            "status": "IN_PROGRESS",
            "start_time": "2024-01-15T10:30:00Z",
            "current_stage": "Deploy",
            "current_action": "Network_VPCs",
            "stage_progress": {
                "current_stage_number": 10,
                "total_stages": 10,
                "current_stage_name": "Deploy",
                "current_action_name": "Network_VPCs",
                "progress_text": "Currently on stage 10 of 10: Deploy (action: Network_VPCs)",
                "current_stage_description": "Deploys infrastructure across multiple sub-actions including networking, security, operations, and customizations",
                "current_action_description": "Deploys VPCs, subnets, endpoints, and DNS resources"
            },
            "message": "Pipeline execution is in progress on stage 'Deploy'"
        }
    """
    logger.info(f"Getting pipeline status for: {pipeline_name}")

    # Save whether a specific execution ID was provided (before it gets overwritten)
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
        # Create CodePipeline client
        codepipeline = get_codepipeline_client()

        # Step 1: Get pipeline structure (equivalent to: aws codepipeline get-pipeline --name PIPELINE)
        logger.info(f"Step 1: Getting pipeline structure for {pipeline_name}")

        # Check cache first
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

                # Cache the pipeline metadata
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

        # Step 2: Get recent executions (always check recent executions for context)
        if execution_id:
            # When a specific execution ID is provided, still get recent executions to provide context
            logger.info(
                f"🔍 Step 2: Getting recent pipeline executions (specific execution ID provided: {execution_id})"
            )
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=5,  # Get more executions when looking for a specific one
            )

            # Log all recent executions found
            executions = executions_response["pipelineExecutionSummaries"]
            logger.info(f"🔍 Step 2: Found {len(executions)} recent executions:")
            for i, exec_summary in enumerate(executions):
                exec_id = exec_summary["pipelineExecutionId"]
                exec_status = exec_summary.get("status", "Unknown")
                start_time = exec_summary.get("startTime", "Unknown")
                logger.info(
                    f"🔍   {i + 1}. {exec_id} - Status: {exec_status} - Started: {start_time}"
                )

            # Try to find the specific execution in recent executions
            target_execution = None
            logger.info(f"🔍 Step 3: Looking for SPECIFIC execution ID: {execution_id}")
            for i, exec_summary in enumerate(
                executions_response["pipelineExecutionSummaries"]
            ):
                logger.info(
                    f"🔍   Checking execution {i + 1}: {exec_summary['pipelineExecutionId']} (status: {exec_summary.get('status', 'Unknown')})"
                )
                if exec_summary["pipelineExecutionId"] == execution_id:
                    target_execution = exec_summary
                    logger.info(f"✅   FOUND requested execution: {execution_id}")
                    break

            if target_execution:
                logger.info(
                    f"🔍 Step 3: SELECTED execution for analysis: {execution_id}"
                )
            else:
                # Execution not found in recent list, but we'll still try to get it directly
                logger.info(
                    f"🔍 Step 3: Execution not found in recent list, will try direct access: {execution_id}"
                )
        else:
            # Get recent executions when no specific execution ID is provided
            logger.info("🔍 Step 2: Getting recent pipeline executions")
            executions_response = await retry_with_exponential_backoff(
                codepipeline.list_pipeline_executions,
                pipelineName=pipeline_name,
                maxResults=1,  # Only need the most recent when no specific ID provided
            )

            # Log all recent executions found
            executions = executions_response["pipelineExecutionSummaries"]
            logger.info(f"🔍 Step 2: Found {len(executions)} recent executions:")
            for i, exec_summary in enumerate(executions):
                exec_id = exec_summary["pipelineExecutionId"]
                exec_status = exec_summary.get("status", "Unknown")
                start_time = exec_summary.get("startTime", "Unknown")
                logger.info(
                    f"🔍   {i + 1}. {exec_id} - Status: {exec_status} - Started: {start_time}"
                )

            if not executions_response["pipelineExecutionSummaries"]:
                response = {
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
                return response

            # Use the most recent execution
            target_execution = executions_response["pipelineExecutionSummaries"][0]
            execution_id = target_execution["pipelineExecutionId"]
            logger.info(f"🔍 Step 3: Using MOST RECENT execution: {execution_id}")
            logger.info(f"🔍 Step 3: SELECTED execution for analysis: {execution_id}")

        # Step 4: Get detailed execution information
        logger.info(
            f"Step 4: Getting detailed execution information for: {execution_id}"
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
                    error=f"Execution '{execution_id}' not found",
                    message=f"The specified execution ID '{execution_id}' does not exist for pipeline '{pipeline_name}'",
                    error_code="PipelineExecutionNotFoundException",
                    troubleshooting=[
                        "Verify the execution ID is correct",
                        "The execution may have been deleted or expired",
                        "Use AWS CLI: aws codepipeline list-pipeline-executions to see available executions",
                    ],
                )
            else:
                # Re-raise for general error handling
                raise

        # Extract basic execution information
        status = execution["status"].upper()  # Normalize to uppercase for consistency
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

        logger.info("🔍 EXECUTION ANALYSIS:")
        logger.info(f"🔍   Execution ID: {execution_id}")
        logger.info(f"🔍   Status: {status}")
        logger.info(f"🔍   Execution Mode: {execution_mode}")
        logger.info(f"🔍   Start Time: {start_time}")
        logger.info(f"🔍   End Time: {end_time}")

        # Step 5: Get current pipeline state (equivalent to: aws codepipeline get-pipeline-state --name PIPELINE)
        # Get pipeline state when a specific execution ID was originally provided or when execution is in progress
        stage_states = []
        if original_execution_id_provided or status.upper() == "IN_PROGRESS":
            logger.info("🔍 Step 5: Getting current pipeline state")
            state_response = await retry_with_exponential_backoff(
                codepipeline.get_pipeline_state, name=pipeline_name
            )
            stage_states = state_response["stageStates"]
        else:
            logger.info(
                f"🔍 Step 5: Skipping pipeline state for most recent completed execution (status: {status})"
            )

        # Step 6: Find currently in-progress stages (equivalent to CLI query for InProgress stages)
        logger.info("🔍 Step 6: Finding in-progress stages")
        current_stage = None
        current_action = None
        current_stage_number = 0
        in_progress_stages = []

        if stage_states:
            # Find all stages that are currently InProgress (equivalent to CLI query)
            logger.info(
                f"🔍 Analyzing {len(stage_states)} stages for InProgress status:"
            )
            for i, stage_state in enumerate(stage_states):
                stage_name = stage_state["stageName"]
                if "latestExecution" in stage_state:
                    latest_execution = stage_state["latestExecution"]
                    stage_status = latest_execution.get("status", "Unknown")
                    stage_exec_id = latest_execution.get(
                        "pipelineExecutionId", "Unknown"
                    )

                    logger.info(
                        f"🔍   Stage {i + 1} ({stage_name}): status={stage_status}, exec_id={stage_exec_id}"
                    )

                    if stage_status.upper() == "INPROGRESS":
                        in_progress_stages.append(
                            {
                                "stage_number": i + 1,
                                "stage_name": stage_name,
                                "execution_id": stage_exec_id,
                            }
                        )
                        logger.info(
                            f"✅ Found in-progress stage: {stage_name} (stage {i + 1})"
                        )
                else:
                    logger.info(
                        f"🔍   Stage {i + 1} ({stage_name}): no latestExecution"
                    )

            logger.info(f"🔍 Found {len(in_progress_stages)} in-progress stages")

            # Determine current stage based on in-progress stages (ignore execution status)
            if in_progress_stages:
                # Use the first in-progress stage (there should typically be only one)
                current_stage_info = in_progress_stages[0]
                current_stage = current_stage_info["stage_name"]
                current_stage_number = current_stage_info["stage_number"]

                logger.info(
                    f"✅ Using in-progress stage: {current_stage} (stage {current_stage_number})"
                )

                # Find current action within this stage
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
                                logger.info(
                                    f"✅ Found in-progress action: {current_action}"
                                )
                                break

        # Determine current stage based on execution status if not found from stage states
        if not current_stage:
            if status.upper() == "IN_PROGRESS":
                # Pipeline execution is IN_PROGRESS but no stages show InProgress
                logger.warning(
                    "⚠️ Pipeline execution is IN_PROGRESS but no stages show InProgress status"
                )
                current_stage_number = 1  # Assume it's starting
                current_stage = pipeline_stages[0]["name"] if pipeline_stages else None
            elif status in ["SUCCEEDED", "FAILED", "STOPPED", "STOPPING"]:
                # For completed executions, show the final stage
                current_stage_number = total_stages
                current_stage = pipeline_stages[-1]["name"] if pipeline_stages else None
            else:
                # For other statuses, we can't determine the stage
                logger.info(f"🔍 Cannot determine stage for status: {status}")
                current_stage_number = 0
                current_stage = None

        # Create stage progress information
        if current_stage:
            progress_text = f"Currently on stage {current_stage_number} of {total_stages}: {current_stage}"
            if current_action:
                progress_text += f" (action: {current_action})"
        else:
            if len(in_progress_stages) == 0 and status.upper() == "IN_PROGRESS":
                progress_text = "Pipeline execution is in progress but no stages are currently active"
            elif status.upper() in ["SUCCEEDED", "FAILED", "STOPPED", "STOPPING"]:
                progress_text = f"Pipeline execution {status.lower()}"
            else:
                progress_text = f"Pipeline has {total_stages} stages (status: {status})"

        stage_progress = {
            "current_stage_number": current_stage_number,
            "total_stages": total_stages,
            "current_stage_name": current_stage,
            "current_action_name": current_action,
            "progress_text": progress_text,
            "current_stage_description": get_stage_description(current_stage)
            if current_stage
            else None,
            "current_action_description": get_action_description(current_action)
            if current_action
            else None,
        }

        # Create response data
        response_data = {
            "execution_id": execution_id,
            "pipeline_name": pipeline_name,
            "status": status,
            "stage_progress": stage_progress,
        }

        # Add timing information if available
        if start_time:
            response_data["start_time"] = start_time
        if end_time:
            response_data["end_time"] = end_time

        # Add current stage and action if available
        if current_stage:
            response_data["current_stage"] = current_stage
        if current_action:
            response_data["current_action"] = current_action

        # Create appropriate message based on status and current stage
        if status.upper() == "IN_PROGRESS":
            if current_stage:
                message = f"Pipeline is on stage '{current_stage}' (stage {current_stage_number} of {total_stages})"
            elif len(in_progress_stages) > 0:
                stage_names = [stage["stage_name"] for stage in in_progress_stages]
                message = f"Pipeline has {len(in_progress_stages)} active stages: {', '.join(stage_names)}"
            else:
                message = "Pipeline execution is in progress but no stages are currently active"
        elif current_stage and original_execution_id_provided:
            # When a specific execution ID is provided, show stage info even for completed executions
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
