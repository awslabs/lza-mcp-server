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

"""Get manual approval status for LZA CodePipeline deployments."""

import logging
import os
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
from .common import truncate_logs

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    get_codebuild_client,
    get_logs_client,
    get_s3_client,
    get_aws_account_id,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from ...server_config import is_s3_diff_enabled
from ...utils.input_validation import (
    validate_pipeline_name,
    validate_qualifier,
    validate_string_input,
)

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


def infer_s3_diff_bucket_name(
    pipeline_name: str, qualifier: Optional[str], account_id: str, region: str
) -> str:
    """Infer the S3 diff bucket name from the deployment context.

    Naming convention:
    - Standard deployments (no qualifier): extract prefix from pipeline name
      by removing '-Pipeline' suffix (e.g., 'AWSAccelerator-Pipeline' -> 'AWSAccelerator')
    - External deployments (with qualifier): use the qualifier as the prefix

    The resulting bucket name is: {prefix}-diff-{account_id}-{region}

    Args:
        pipeline_name: The resolved pipeline name
        qualifier: The qualifier string, or None for standard deployments
        account_id: The AWS account ID
        region: The AWS region

    Returns:
        The inferred S3 diff bucket name
    """
    if qualifier:
        prefix = qualifier
    else:
        # Standard deployment: strip '-Pipeline' suffix to get the prefix
        if pipeline_name.endswith("-Pipeline"):
            prefix = pipeline_name[: -len("-Pipeline")]
        else:
            prefix = pipeline_name

    return f"{prefix}-diff-{account_id}-{region}"


async def tool_get_manual_approval_status(
    ctx: Context,
    qualifier: Optional[str] = None,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
) -> Dict[str, Any]:
    """Get manual approval status for an LZA CodePipeline deployment.

    Detects whether a manual approval action is pending in the pipeline,
    retrieves the approval token and change context, and optionally
    fetches a deployment diff from S3 when ENABLE_S3_DIFF is enabled.

    Args:
        ctx: MCP context for logging and user feedback
        qualifier: LZA Accelerator Qualifier for external pipeline deployments.
            When provided, queries the CodePipeline named '{qualifier}-pipeline'.
        pipeline_name: Name of the CodePipeline (standard deployments only,
            defaults to 'AWSAccelerator-Pipeline')

    Returns:
        Dict containing approval status, token, change context, and optional S3 diff
    """
    # Resolve pipeline name
    if qualifier is not None:
        # Validate qualifier
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

        resolved_name = f"{qualifier}-pipeline"
    else:
        resolved_name = pipeline_name

    # Validate pipeline name
    is_valid, validation_error = validate_string_input(
        resolved_name, "pipeline_name", min_length=1, max_length=100
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

    is_valid, validation_error = validate_pipeline_name(resolved_name)
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

    try:
        codepipeline = get_codepipeline_client()

        # Get pipeline state
        logger.info(f"Getting pipeline state for: {resolved_name}")
        state_response = await retry_with_exponential_backoff(
            codepipeline.get_pipeline_state, name=resolved_name
        )

        stage_states = state_response.get("stageStates", [])

        # Search for a pending approval action
        for stage in stage_states:
            stage_name = stage.get("stageName", "")
            for action_state in stage.get("actionStates", []):
                latest_execution = action_state.get("latestExecution", {})
                action_name = action_state.get("actionName", "")
                status = latest_execution.get("status", "")

                # Check if this is an in-progress approval action
                if status == "InProgress":
                    # Check the action type category from the pipeline state
                    # The actionTypeId is available in the action configuration
                    # but we also check via the presence of a token which is
                    # unique to approval actions
                    token = latest_execution.get("token")
                    if token is None:
                        continue

                    pipeline_execution_id = latest_execution.get(
                        "pipelineExecutionId", ""
                    )

                    # Extract optional fields
                    custom_data = latest_execution.get("summary", "")
                    external_entity_url = action_state.get("entityUrl", "")

                    response: Dict[str, Any] = {
                        "success": True,
                        "approval_pending": True,
                        "pipeline_name": resolved_name,
                        "stage_name": stage_name,
                        "action_name": action_name,
                        "pipeline_execution_id": pipeline_execution_id,
                        "token": token,
                        "message": f"Manual approval is pending in stage '{stage_name}'",
                    }

                    # Include optional fields when present
                    if custom_data:
                        response["custom_data"] = custom_data
                    if external_entity_url:
                        response["external_entity_url"] = external_entity_url

                    # Review stage diff retrieval (CodeBuild logs — default, always attempted)
                    review_diff_result = await _retrieve_review_stage_diff(
                        stage_states, stage_name
                    )
                    if review_diff_result.get("success"):
                        response["review_diff"] = review_diff_result["content"]
                    elif review_diff_result.get("warning"):
                        response["review_diff_warning"] = review_diff_result["warning"]

                    # S3 diff retrieval (Task 3.2)
                    if is_s3_diff_enabled() and pipeline_execution_id:
                        s3_diff_result = await _retrieve_s3_diff(
                            resolved_name, qualifier, pipeline_execution_id
                        )
                        if s3_diff_result.get("success"):
                            response["s3_diff_content"] = s3_diff_result["content"]
                        elif s3_diff_result.get("warning"):
                            response["s3_diff_warning"] = s3_diff_result["warning"]

                    return response

        # No pending approval found — determine overall pipeline status
        pipeline_status = _determine_pipeline_status(stage_states)

        return {
            "success": True,
            "approval_pending": False,
            "pipeline_name": resolved_name,
            "pipeline_status": pipeline_status,
            "message": f"No manual approval is currently pending. Pipeline status: {pipeline_status}",
        }

    except Exception as e:
        logger.error(f"Error getting manual approval status: {str(e)}")
        return handle_aws_error(
            e, f"getting manual approval status for pipeline '{resolved_name}'"
        )


def _determine_pipeline_status(stage_states: list) -> str:
    """Determine the overall pipeline status from stage states.

    Scans stage states to find the most relevant status indicator.

    Args:
        stage_states: List of stage state dicts from GetPipelineState

    Returns:
        A string representing the overall pipeline status
    """
    has_in_progress = False
    has_failed = False
    all_succeeded = True

    for stage in stage_states:
        latest = stage.get("latestExecution", {})
        status = latest.get("status", "")

        if status == "InProgress":
            has_in_progress = True
            all_succeeded = False
        elif status == "Failed":
            has_failed = True
            all_succeeded = False
        elif status != "Succeeded":
            all_succeeded = False

    if has_in_progress:
        return "InProgress"
    if has_failed:
        return "Failed"
    if all_succeeded and stage_states:
        return "Succeeded"
    return "Unknown"


async def _retrieve_s3_diff(
    pipeline_name: str,
    qualifier: Optional[str],
    pipeline_execution_id: str,
) -> Dict[str, Any]:
    """Retrieve deployment diff from S3 when ENABLE_S3_DIFF is enabled.

    Infers the S3 bucket name from the deployment context and attempts
    to retrieve the diff object. On failure, returns a warning instead
    of raising an error.

    Args:
        pipeline_name: The resolved pipeline name
        qualifier: The qualifier string, or None for standard deployments
        pipeline_execution_id: The pipeline execution ID for the diff key

    Returns:
        Dict with 'success' and 'content' on success, or 'warning' on failure
    """
    try:
        # Validate pipeline_execution_id for S3 key safety
        import re

        is_valid, validation_error = validate_string_input(
            pipeline_execution_id,
            "pipeline_execution_id",
            min_length=1,
            max_length=200,
        )
        if not is_valid:
            return {
                "success": False,
                "warning": f"Invalid pipeline execution ID for S3 diff retrieval: {validation_error}",
            }

        if not re.match(r"^[a-zA-Z0-9\-]+$", pipeline_execution_id):
            return {
                "success": False,
                "warning": "Invalid pipeline execution ID format for S3 diff retrieval",
            }

        account_id = get_aws_account_id()
        region = AWS_REGION

        bucket_name = infer_s3_diff_bucket_name(
            pipeline_name, qualifier, account_id, region
        )
        diff_key = f"{pipeline_execution_id}/diff.txt"

        logger.info(f"Retrieving S3 diff from s3://{bucket_name}/{diff_key}")

        s3_client = get_s3_client()
        response = await retry_with_exponential_backoff(
            s3_client.get_object, Bucket=bucket_name, Key=diff_key
        )

        if "Body" not in response:
            logger.warning("S3 GetObject response missing Body field")
            return {
                "success": False,
                "warning": "Could not retrieve deployment diff from S3: response missing content",
            }

        content = response["Body"].read().decode("utf-8")
        return {"success": True, "content": content}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.warning(f"Failed to retrieve S3 diff: {error_code} - {error_message}")
        return {
            "success": False,
            "warning": "Could not retrieve deployment diff from S3",
        }
    except Exception as e:
        logger.warning(f"Failed to retrieve S3 diff: {str(e)}")
        return {
            "success": False,
            "warning": "Could not retrieve deployment diff from S3",
        }


async def _retrieve_review_stage_diff(
    stage_states: list,
    approval_stage_name: str,
) -> Dict[str, Any]:
    """Retrieve CDK diff output from the Review stage's CodeBuild logs.

    Scans the pipeline stage states for a CodeBuild action that ran before
    the approval action (same stage or preceding stage), retrieves its
    CloudWatch Logs, and returns the truncated log content.

    Follows the same pattern as ``_pull_codebuild_details()`` in
    ``diagnose_deployment_errors.py``.

    Args:
        stage_states: List of stage state dicts from GetPipelineState
        approval_stage_name: Name of the stage containing the approval action

    Returns:
        Dict with 'success' and 'content' on success, or 'success'=False
        and 'warning' on failure
    """
    try:
        # Find a CodeBuild action with an externalExecutionId.
        # Priority: same stage as the approval action, then preceding stages.
        external_execution_id = None

        # 1. Look in the same stage as the approval action
        for stage in stage_states:
            if stage.get("stageName") == approval_stage_name:
                for action_state in stage.get("actionStates", []):
                    latest = action_state.get("latestExecution", {})
                    ext_id = latest.get("externalExecutionId")
                    # Skip actions that don't have an externalExecutionId
                    # (approval actions won't have one — they have a token instead)
                    if ext_id:
                        external_execution_id = ext_id
                        break
                break

        # 2. If not found, look in preceding stages (reverse order — closest first)
        if not external_execution_id:
            found_stage_idx = -1
            for idx, stage in enumerate(stage_states):
                if stage.get("stageName") == approval_stage_name:
                    found_stage_idx = idx
                    break

            for idx in range(found_stage_idx - 1, -1, -1):
                stage = stage_states[idx]
                for action_state in stage.get("actionStates", []):
                    latest = action_state.get("latestExecution", {})
                    ext_id = latest.get("externalExecutionId")
                    if ext_id:
                        external_execution_id = ext_id
                        break
                if external_execution_id:
                    break

        if not external_execution_id:
            return {
                "success": False,
                "warning": "Could not retrieve Review stage diff: no CodeBuild action found in stage states",
            }

        # 3. Get build details from CodeBuild
        codebuild = get_codebuild_client()
        build_response = await retry_with_exponential_backoff(
            codebuild.batch_get_builds, ids=[external_execution_id]
        )

        if not build_response.get("builds"):
            logger.warning(
                f"Could not retrieve Review stage diff: build '{external_execution_id}' not found"
            )
            return {
                "success": False,
                "warning": "Could not retrieve Review stage diff: build not found",
            }

        build = build_response["builds"][0]
        if (
            "logs" not in build
            or "groupName" not in build["logs"]
            or "streamName" not in build["logs"]
        ):
            return {
                "success": False,
                "warning": "Could not retrieve Review stage diff: build has no log information",
            }

        # 4. Retrieve logs from CloudWatch
        logs_client = get_logs_client()
        log_response = await retry_with_exponential_backoff(
            logs_client.get_log_events,
            logGroupName=build["logs"]["groupName"],
            logStreamName=build["logs"]["streamName"],
            startFromHead=True,
            limit=2000,
        )

        log_events = log_response.get("events", [])
        if not log_events:
            return {
                "success": False,
                "warning": "Could not retrieve Review stage diff: no log events found",
            }

        # 5. Concatenate and truncate
        logs_content = "\n".join(event["message"] for event in log_events)
        truncated = truncate_logs(logs_content)

        return {"success": True, "content": truncated}

    except Exception as e:
        logger.warning(f"Failed to retrieve Review stage diff: {str(e)}")
        return {
            "success": False,
            "warning": "Could not retrieve Review stage diff",
        }
