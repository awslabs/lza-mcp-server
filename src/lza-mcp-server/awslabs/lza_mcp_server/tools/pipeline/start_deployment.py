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

"""Unified LZA deployment trigger for both standard pipeline and ECS container deployments."""

import logging
import os
from typing import Dict, Any, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context
from ...constants import DEFAULT_REGION, DEFAULT_PIPELINE_NAME
from .common import validate_pipeline_name_local, validate_qualifier

from ...aws_access import (
    format_error_response,
    get_codepipeline_client,
    get_ssm_client,
    retry_with_exponential_backoff,
    handle_aws_error,
)
from ...utils.input_validation import validate_string_input

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_start_deployment(
    ctx: Context,
    qualifier: Optional[str] = None,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
) -> Dict[str, Any]:
    """Start an LZA deployment — supports standard pipeline, external CodePipeline, and ECS container deployments.

    Call checkAwsConnectivity first to determine deployment type and qualifier.
    For standard deployments, omit the qualifier — the tool starts the default
    AWSAccelerator-Pipeline (or the pipeline_name you provide).
    For external pipeline deployments, pass the qualifier from checkAwsConnectivity.
    When a qualifier is provided, the tool checks both CodePipeline ({qualifier}-pipeline)
    and the SSM Automation document ({qualifier}-RunEngine) to start whichever
    deployment infrastructure exists. If both exist, both are started.

    Args:
        ctx: MCP context for logging and user feedback
        qualifier: LZA Accelerator Qualifier for external pipeline deployments (e.g. "container-dev-1").
            Obtained from checkAwsConnectivity. When provided, starts both the
            CodePipeline ({qualifier}-pipeline) and/or the SSM Automation
            ({qualifier}-RunEngine) if they exist.
        pipeline_name: Name of the CodePipeline (standard deployments only, defaults to "AWSAccelerator-Pipeline")

    Returns:
        Dict containing:
        - success: Boolean indicating if at least one deployment was started
        - deployment_type: "standard" or "external_pipeline"
        - For standard: execution_id, pipeline_name
        - For external: qualifier, sources_started, pipeline_result, container_result
        - message: Success or error message
        - troubleshooting: List of troubleshooting steps if there was an error

    Example:
        # Standard deployment
        await start_deployment(ctx)
        {
            "success": True,
            "deployment_type": "standard",
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "pipeline_name": "AWSAccelerator-Pipeline",
            "message": "Pipeline 'AWSAccelerator-Pipeline' execution started successfully"
        }

        # External pipeline deployment with qualifier
        await start_deployment(ctx, qualifier="container-dev-1")
        {
            "success": True,
            "deployment_type": "external_pipeline",
            "qualifier": "container-dev-1",
            "sources_started": ["SSM Automation"],
            "container_result": {
                "automation_execution_id": "...",
                "document_name": "container-dev-1-RunEngine"
            },
            "message": "Started deployment for qualifier 'container-dev-1' via: SSM Automation"
        }
    """
    # Branch A: Standard pipeline deployment (no qualifier)
    if qualifier is None:
        logger.info("No qualifier provided — using standard pipeline release path")
        result = await _start_standard_pipeline(ctx, pipeline_name)

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
        f"Qualifier provided: {qualifier} — checking both CodePipeline and SSM Automation"
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
            message=f"Qualifier '{qualifier}' does not meet format requirements",
            troubleshooting=[
                "Qualifiers can only contain letters, numbers, and hyphens",
                "Run checkAwsConnectivity to get valid qualifiers",
                f"Specific issue: {validation_error}",
            ],
        )

    qualifier_pipeline_name = f"{qualifier}-pipeline"
    ssm_document_name = f"{qualifier}-RunEngine"

    await ctx.info(f"Starting deployment for qualifier: {qualifier}")

    # Try CodePipeline ({qualifier}-pipeline)
    pipeline_result = None
    try:
        await ctx.info(f"Checking CodePipeline: {qualifier_pipeline_name}")
        cp_result = await _start_standard_pipeline(ctx, qualifier_pipeline_name)
        if cp_result.get("error_code") != "PipelineNotFoundException":
            pipeline_result = cp_result
        else:
            logger.info(
                f"CodePipeline '{qualifier_pipeline_name}' not found — skipping"
            )
    except Exception as e:
        logger.warning(
            f"Error starting CodePipeline for qualifier '{qualifier}': {str(e)}"
        )

    # Try SSM Automation ({qualifier}-RunEngine)
    container_result = None
    try:
        await ctx.info(f"Checking SSM Automation document: {ssm_document_name}")
        ssm_result = await _start_ssm_automation(ctx, qualifier, ssm_document_name)
        if ssm_result.get("error_code") != "InvalidDocument":
            container_result = ssm_result
        else:
            logger.info(f"SSM document '{ssm_document_name}' not found — skipping")
    except Exception as e:
        logger.warning(
            f"Error starting SSM Automation for qualifier '{qualifier}': {str(e)}"
        )

    # Build combined response
    sources_started = []
    if pipeline_result and pipeline_result.get("success"):
        sources_started.append("CodePipeline")
    if container_result and container_result.get("success"):
        sources_started.append("SSM Automation")

    if not sources_started:
        # Neither source could be started — check if neither was found at all
        neither_found = (pipeline_result is None) and (container_result is None)
        if neither_found:
            return format_error_response(
                error=f"No deployment infrastructure found for qualifier '{qualifier}'",
                message=f"Neither CodePipeline '{qualifier_pipeline_name}' nor "
                f"SSM document '{ssm_document_name}' were found in region {AWS_REGION}",
                troubleshooting=[
                    f"Verify the qualifier '{qualifier}' is correct",
                    f"Check that the deployment exists in region: {AWS_REGION}",
                    "Run checkAwsConnectivity to detect available qualifiers",
                    "The deployment infrastructure may not have been provisioned yet",
                ],
            )

        # At least one was found but failed to start
        errors = []
        if pipeline_result and not pipeline_result.get("success"):
            errors.append(
                f"CodePipeline: {pipeline_result.get('error', 'unknown error')}"
            )
        if container_result and not container_result.get("success"):
            errors.append(
                f"SSM Automation: {container_result.get('error', 'unknown error')}"
            )

        return format_error_response(
            error=f"Failed to start deployment for qualifier '{qualifier}': {'; '.join(errors)}",
            message="Deployment infrastructure was found but could not be started",
            troubleshooting=[
                "Check IAM permissions for codepipeline:StartPipelineExecution and/or ssm:StartAutomationExecution",
                f"Verify the qualifier '{qualifier}' is correct",
                "Review the specific error details above",
            ],
        )

    message = f"Started deployment for qualifier '{qualifier}' via: {', '.join(sources_started)}"

    response: Dict[str, Any] = {
        "success": True,
        "deployment_type": "external_pipeline",
        "qualifier": qualifier,
        "sources_started": sources_started,
        "message": message,
    }
    if pipeline_result:
        response["pipeline_result"] = pipeline_result
    if container_result:
        response["container_result"] = container_result

    return response


# ---------------------------------------------------------------------------
# Branch A: Standard CodePipeline release
# ---------------------------------------------------------------------------


async def _start_standard_pipeline(
    ctx: Context,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
) -> Dict[str, Any]:
    """Start a standard CodePipeline execution.

    Validates the pipeline exists, then triggers start_pipeline_execution.
    """
    logger.info(f"Starting pipeline release for: {pipeline_name}")

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
            message=f"Pipeline name '{pipeline_name}' does not meet AWS naming requirements",
            troubleshooting=[
                "Pipeline names must be 1-100 characters long",
                "Can only contain letters, numbers, periods, underscores, and hyphens",
                "Cannot contain spaces or other special characters",
                f"Specific issue: {validation_error}",
            ],
        )

    try:
        codepipeline = get_codepipeline_client()

        # Validate pipeline exists
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
            raise

        # Start the pipeline execution
        logger.info(f"Starting pipeline execution: {pipeline_name}")
        execution_response = await retry_with_exponential_backoff(
            codepipeline.start_pipeline_execution, name=pipeline_name
        )

        execution_id = execution_response["pipelineExecutionId"]
        logger.info(
            f"Pipeline execution started successfully. Execution ID: {execution_id}"
        )

        return {
            "success": True,
            "execution_id": execution_id,
            "pipeline_name": pipeline_name,
            "message": f"Pipeline '{pipeline_name}' execution started successfully",
        }

    except Exception as e:
        logger.error(f"Error starting pipeline execution: {str(e)}")
        return handle_aws_error(e, f"starting pipeline '{pipeline_name}' execution")


# ---------------------------------------------------------------------------
# Branch B: SSM Automation for ECS container deployment
# ---------------------------------------------------------------------------


async def _start_ssm_automation(
    ctx: Context,
    qualifier: str,
    document_name: str,
) -> Dict[str, Any]:
    """Start an LZA deployment via SSM Automation document.

    The LZA container installer creates an SSM Automation document named
    {qualifier}-RunEngine that orchestrates the ECS task execution.
    This function validates the document exists, then starts the automation.

    Args:
        ctx: MCP context for logging
        qualifier: The LZA Accelerator Qualifier
        document_name: SSM Automation document name ({qualifier}-RunEngine)

    Returns:
        Dict with success status and automation execution ID
    """
    logger.info(f"Starting SSM Automation: {document_name}")

    try:
        ssm = get_ssm_client()

        # Validate the SSM document exists by describing it
        logger.info(f"Validating SSM document existence: {document_name}")
        try:
            await retry_with_exponential_backoff(
                ssm.describe_document, Name=document_name
            )
            logger.info(f"SSM document found: {document_name}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "InvalidDocument":
                return format_error_response(
                    error=f"SSM document '{document_name}' not found",
                    message=f"The SSM Automation document '{document_name}' does not exist",
                    error_code="InvalidDocument",
                    troubleshooting=[
                        f"Verify the qualifier '{qualifier}' is correct",
                        f"Check that the SSM document exists in region: {AWS_REGION}",
                        "The container installer stack may not have been deployed for this qualifier",
                        f"Use AWS CLI: aws ssm list-documents --filters Key=Name,Values={document_name}",
                    ],
                )
            raise

        # Start the automation execution
        logger.info(f"Starting SSM Automation execution: {document_name}")
        automation_response = await retry_with_exponential_backoff(
            ssm.start_automation_execution, DocumentName=document_name
        )

        automation_execution_id = automation_response["AutomationExecutionId"]
        logger.info(
            f"SSM Automation started successfully. Execution ID: {automation_execution_id}"
        )

        await ctx.info(
            f"SSM Automation '{document_name}' started. Execution ID: {automation_execution_id}"
        )

        return {
            "success": True,
            "automation_execution_id": automation_execution_id,
            "document_name": document_name,
            "qualifier": qualifier,
            "message": f"SSM Automation '{document_name}' started successfully",
        }

    except Exception as e:
        logger.error(f"Error starting SSM Automation: {str(e)}")
        return handle_aws_error(
            e, f"starting SSM Automation '{document_name}' for qualifier '{qualifier}'"
        )
