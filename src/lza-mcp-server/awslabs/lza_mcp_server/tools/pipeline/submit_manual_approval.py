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

"""Submit manual approval for LZA CodePipeline deployments."""

import logging
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_PIPELINE_NAME
from ...utils.input_validation import (
    validate_pipeline_name,
    validate_qualifier,
    validate_string_input,
)

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    retry_with_exponential_backoff,
)

logger = logging.getLogger(__name__)

# Valid action values (case-insensitive)
VALID_ACTIONS = {"approve": "Approved", "reject": "Rejected"}


async def tool_submit_manual_approval(
    ctx: Context,
    action: str,
    token: str,
    stage_name: str,
    action_name: str,
    qualifier: Optional[str] = None,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit a manual approval decision for an LZA CodePipeline deployment.

    Approves or rejects a pending manual approval action in the pipeline.
    Call getDeploymentStatus first — when a pending approval is detected,
    it returns the approval_token, approval_stage_name, and
    approval_action_name required for this tool.

    Args:
        ctx: MCP context for logging and user feedback
        action: Approval decision — "Approve" or "Reject" (case-insensitive)
        token: Approval token from getDeploymentStatus
        stage_name: Pipeline stage name containing the approval action
        action_name: Name of the approval action within the stage
        qualifier: LZA Accelerator Qualifier for external pipeline deployments.
            When provided, submits to the CodePipeline named '{qualifier}-pipeline'.
        pipeline_name: Name of the CodePipeline (standard deployments only,
            defaults to 'AWSAccelerator-Pipeline')
        summary: Optional comment to include with the approval/rejection

    Returns:
        Dict containing success status, action taken, and confirmation details
    """
    # --- Validate action parameter ---
    if not action or not isinstance(action, str):
        return format_error_response(
            error="Invalid action: action cannot be empty",
            message="The 'action' parameter is required and must be a string",
            troubleshooting=[
                "Valid action values are: 'Approve' or 'Reject' (case-insensitive)",
            ],
        )

    action_lower = action.strip().lower()
    if action_lower not in VALID_ACTIONS:
        logger.warning(
            f"Invalid action: '{action}'. Valid values are: 'Approve', 'Reject'"
        )
        return format_error_response(
            error="Invalid action value",
            message="The action is not recognized. Use 'Approve' or 'Reject' (case-insensitive)",
            troubleshooting=[
                "Valid action values are: 'Approve' or 'Reject' (case-insensitive)",
                "Example: action='Approve' or action='Reject'",
            ],
        )

    normalized_status = VALID_ACTIONS[action_lower]

    # --- Validate required string parameters ---
    for param_name, param_value in [
        ("token", token),
        ("stage_name", stage_name),
        ("action_name", action_name),
    ]:
        is_valid, validation_error = validate_string_input(
            param_value, param_name, min_length=1, max_length=1000
        )
        if not is_valid:
            logger.warning(f"Invalid {param_name}: {validation_error}")
            return format_error_response(
                error=f"Invalid {param_name}",
                message=f"The '{param_name}' parameter failed validation",
                troubleshooting=[
                    f"The '{param_name}' parameter is required and cannot be empty",
                    "Use getDeploymentStatus to obtain the correct values",
                ],
            )

    # --- Resolve pipeline name ---
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

    # --- Validate resolved pipeline name ---
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

    # --- Validate summary if provided ---
    if summary is not None:
        is_valid, validation_error = validate_string_input(
            summary, "summary", min_length=0, max_length=2048, allow_empty=True
        )
        if not is_valid:
            return format_error_response(
                error=f"Invalid summary: {validation_error}",
                message=validation_error,
                troubleshooting=[
                    "Summary must not exceed 2048 characters",
                ],
            )

    # --- Build PutApprovalResult parameters ---
    approval_result: Dict[str, Any] = {"status": normalized_status}
    if summary:
        approval_result["summary"] = summary

    put_params = {
        "pipelineName": resolved_name,
        "stageName": stage_name,
        "actionName": action_name,
        "result": approval_result,
        "token": token,
    }

    # --- Call CodePipeline PutApprovalResult ---
    try:
        codepipeline = get_codepipeline_client()

        logger.info(
            f"Submitting {normalized_status} for pipeline '{resolved_name}' "
            f"stage '{stage_name}' action '{action_name}'"
        )
        await retry_with_exponential_backoff(
            codepipeline.put_approval_result, **put_params
        )

        logger.info(f"Approval result submitted successfully: {normalized_status}")

        return {
            "success": True,
            "action": normalized_status,
            "pipeline_name": resolved_name,
            "stage_name": stage_name,
            "action_name": action_name,
            "message": f"Manual approval '{normalized_status}' submitted successfully. The pipeline will proceed based on the approval decision.",
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "InvalidApprovalTokenException":
            logger.warning(
                f"Invalid approval token for pipeline '{resolved_name}': {str(e)}"
            )
            return {
                "success": False,
                "error": "The approval token is no longer valid",
                "message": "The approval token is no longer valid. The pipeline execution may have moved past the approval stage or the token may have expired.",
                "error_code": "InvalidApprovalTokenException",
                "troubleshooting": [
                    "The approval token may have expired (tokens are valid for 7 days)",
                    "The pipeline execution may have moved past the approval stage",
                    "Use getDeploymentStatus to get a fresh approval token",
                ],
            }

        # All other AWS errors
        logger.error(f"Error submitting approval result: {str(e)}")
        return format_error_response(
            error="Failed to submit approval result",
            message="An AWS API error occurred while submitting the approval result",
            troubleshooting=[
                "Verify the pipeline name, stage name, and action name are correct",
                "Use getDeploymentStatus to obtain the correct values",
                "Check IAM permissions for codepipeline:PutApprovalResult",
            ],
        )

    except Exception as e:
        logger.error(f"Error submitting approval result: {str(e)}")
        return format_error_response(
            error="Failed to submit approval result",
            message="An unexpected error occurred while submitting the approval result",
            troubleshooting=[
                "Check network connectivity to AWS services",
                "Verify AWS region configuration",
                "Use getDeploymentStatus to verify the pipeline state",
            ],
        )
