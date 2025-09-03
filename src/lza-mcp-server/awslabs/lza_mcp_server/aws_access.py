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

import asyncio
import logging
import os
from typing import Dict, Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from .constants import DEFAULT_REGION, MAX_RETRY_ATTEMPTS, INITIAL_RETRY_DELAY

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)
logger = logging.getLogger(__name__)


def get_aws_account_id():
    """Get the AWS account ID for the current session."""
    session = get_aws_session()
    sts_client = session.client("sts")
    return sts_client.get_caller_identity()["Account"]


def get_aws_session() -> boto3.Session:
    """Create an AWS session using boto3's default credential provider chain.

    Returns:
        boto3.Session: Configured AWS session with the specified region

    Raises:
        NoCredentialsError: If AWS credentials are not properly configured
    """
    logger.info(f"Creating AWS session with region: {AWS_REGION}")
    return boto3.Session(region_name=AWS_REGION)


def get_codepipeline_client() -> boto3.client:
    """Create a CodePipeline client using the configured AWS session with retry configuration.

    Returns:
        boto3.client: CodePipeline client configured with the current session and retry logic

    Raises:
        NoCredentialsError: If AWS credentials are not properly configured
        ClientError: If there are issues creating the client
    """
    session = get_aws_session()
    config = Config(
        retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "adaptive"},
        max_pool_connections=50,
    )
    return session.client("codepipeline", config=config)


def get_codebuild_client() -> boto3.client:
    """Create a CodeBuild client using the configured AWS session with retry configuration.

    Returns:
        boto3.client: CodeBuild client configured with the current session and retry logic

    Raises:
        NoCredentialsError: If AWS credentials are not properly configured
        ClientError: If there are issues creating the client
    """
    session = get_aws_session()
    config = Config(
        retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "adaptive"},
        max_pool_connections=50,
    )
    return session.client("codebuild", config=config)


def get_logs_client() -> boto3.client:
    """Create a CloudWatch Logs client using the configured AWS session with retry configuration.

    Returns:
        boto3.client: CloudWatch Logs client configured with the current session and retry logic

    Raises:
        NoCredentialsError: If AWS credentials are not properly configured
        ClientError: If there are issues creating the client
    """
    session = get_aws_session()
    config = Config(
        retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "adaptive"},
        max_pool_connections=50,
    )
    return session.client("logs", config=config)


async def retry_with_exponential_backoff(func, *args, **kwargs):
    """Execute a function with exponential backoff retry logic.

    Args:
        func: The function to execute
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None
    delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code in [
                "ThrottlingException",
                "Throttling",
                "RequestLimitExceeded",
                "ServiceUnavailable",
            ]:
                last_exception = e
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    logger.warning(
                        f"AWS API throttled, retrying in {delay} seconds (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS})"
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue
            raise
        except Exception:
            raise

    raise last_exception


def format_error_response(
    error: str,
    message: str,
    error_code: Optional[str] = None,
    troubleshooting: Optional[list] = None,
) -> Dict[str, Any]:
    """Format an error response with consistent structure and troubleshooting guidance.

    Args:
        error: The specific error that occurred
        message: User-friendly error message
        error_code: AWS error code if applicable
        troubleshooting: List of troubleshooting steps

    Returns:
        Dict containing success=False, error details, and troubleshooting guidance
    """
    response = {"success": False, "error": error, "message": message}

    if error_code:
        response["error_code"] = error_code

    if troubleshooting:
        response["troubleshooting"] = troubleshooting
    else:
        # Default troubleshooting steps
        response["troubleshooting"] = [
            "Ensure AWS credentials are configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)",
            "Check if AWS_REGION is set correctly",
            "Verify IAM permissions for CodePipeline operations",
            "Confirm the pipeline name exists in the specified region",
        ]

    return response


def handle_aws_error(e: Exception, operation: str) -> Dict[str, Any]:
    """Handle AWS API errors with appropriate error categorization and guidance.

    Args:
        e: The exception that occurred
        operation: Description of the operation that failed

    Returns:
        Dict containing formatted error response with specific troubleshooting guidance
    """
    if isinstance(e, NoCredentialsError):
        return format_error_response(
            error=str(e),
            message=f"AWS credentials not configured for {operation}",
            troubleshooting=[
                "Configure AWS credentials using one of these methods:",
                "  - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                "  - Set AWS_PROFILE environment variable to use a named profile",
                "  - Use IAM roles if running on EC2/ECS/Lambda",
                "  - Configure credentials using 'aws configure' command",
            ],
        )

    elif isinstance(e, ClientError):
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Handle specific AWS error codes
        if error_code == "PipelineNotFoundException":
            return format_error_response(
                error=error_message,
                message=f"Pipeline not found during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Verify the pipeline name is correct",
                    "Check that the pipeline exists in the specified AWS region",
                    "Ensure you have permissions to access the pipeline",
                    f"Current region: {AWS_REGION}",
                ],
            )

        elif error_code == "AccessDenied" or error_code == "UnauthorizedOperation":
            # Provide operation-specific permission guidance
            permission_guidance = get_iam_permission_guidance(operation, error_message)
            return format_error_response(
                error=error_message,
                message=f"Insufficient permissions for {operation}",
                error_code=error_code,
                troubleshooting=permission_guidance,
            )

        elif error_code == "ThrottlingException" or error_code == "Throttling":
            return format_error_response(
                error=error_message,
                message=f"AWS API rate limit exceeded during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Wait a few seconds and retry the operation",
                    "AWS API calls are being throttled due to high request volume",
                    "Consider implementing exponential backoff for repeated operations",
                    "If this persists, check AWS Service Health Dashboard for any issues",
                ],
            )

        elif error_code == "PipelineExecutionNotFoundException":
            return format_error_response(
                error=error_message,
                message=f"Pipeline execution not found during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Verify the execution ID is correct and exists",
                    "Check that the execution belongs to the specified pipeline",
                    "The execution may have been deleted or expired",
                    "Use AWS CLI: aws codepipeline list-pipeline-executions to see available executions",
                ],
            )

        elif (
            error_code == "InvalidParameterException"
            or error_code == "ValidationException"
        ):
            return format_error_response(
                error=error_message,
                message=f"Invalid parameters provided for {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Check that all required parameters are provided",
                    "Verify parameter formats match AWS requirements",
                    "Pipeline names must be 1-100 characters with only letters, numbers, periods, underscores, and hyphens",
                    "Execution IDs must be valid UUIDs",
                ],
            )

        elif error_code == "ConcurrentModificationException":
            return format_error_response(
                error=error_message,
                message=f"Pipeline is being modified by another operation during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Wait a few seconds and retry the operation",
                    "Another user or process may be modifying the pipeline",
                    "Check AWS CloudTrail logs to see what operations are in progress",
                ],
            )

        elif error_code == "PipelineExecutionNotStoppableException":
            return format_error_response(
                error=error_message,
                message=f"Pipeline execution cannot be stopped during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "The pipeline execution may already be completed or stopping",
                    "Check the current execution status before attempting to stop",
                    "Some pipeline stages cannot be interrupted once started",
                ],
            )

        elif error_code == "InvalidNextTokenException":
            return format_error_response(
                error=error_message,
                message=f"Invalid pagination token provided during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "Do not manually modify pagination tokens",
                    "Use tokens exactly as returned by previous API calls",
                    "Tokens may expire - restart the operation if needed",
                ],
            )

        elif error_code == "RequestLimitExceeded":
            return format_error_response(
                error=error_message,
                message=f"AWS request limit exceeded during {operation}",
                error_code=error_code,
                troubleshooting=[
                    "You have exceeded the maximum number of requests per time period",
                    "Wait before making additional requests",
                    "Consider batching operations to reduce API call frequency",
                    "Check AWS service quotas for your account",
                ],
            )

        else:
            return format_error_response(
                error=error_message,
                message=f"AWS API error during {operation}",
                error_code=error_code,
                troubleshooting=[
                    f"AWS returned error code: {error_code}",
                    "Check AWS service status for any ongoing issues",
                    "Verify your AWS region and account permissions",
                    "Review AWS CloudTrail logs for more details",
                ],
            )

    else:
        return format_error_response(
            error=str(e),
            message=f"Unexpected error during {operation}",
            troubleshooting=[
                "Check network connectivity to AWS services",
                "Verify AWS region configuration",
                "Review application logs for more details",
                "Contact support if the issue persists",
            ],
        )


def get_iam_permission_guidance(operation: str, error_message: str) -> list[str]:
    """Get specific IAM permission guidance based on the operation and error.

    Args:
        operation: The operation that failed
        error_message: The AWS error message

    Returns:
        List of troubleshooting steps with specific IAM permissions
    """
    base_guidance = [
        "Ensure your AWS credentials have the required IAM permissions:",
        "You can attach these permissions to your IAM user, role, or group.",
    ]

    # Operation-specific permissions
    if "pipeline release" in operation or "starting pipeline" in operation:
        permissions = [
            "  - codepipeline:GetPipeline (to validate pipeline exists)",
            "  - codepipeline:StartPipelineExecution (to start the execution)",
            f"  - Resource: arn:aws:codepipeline:{AWS_REGION}:*:pipeline/*",
        ]
    elif "pipeline status" in operation or "getting status" in operation:
        permissions = [
            "  - codepipeline:GetPipeline (to get pipeline structure)",
            "  - codepipeline:GetPipelineExecution (to get execution details)",
            "  - codepipeline:GetPipelineState (to get current stage/action)",
            "  - codepipeline:ListPipelineExecutions (to find recent executions)",
            f"  - Resource: arn:aws:codepipeline:{AWS_REGION}:*:pipeline/*",
        ]
    elif "error diagnosis" in operation or "diagnosing pipeline" in operation:
        permissions = [
            "  - codepipeline:GetPipeline (to get pipeline structure)",
            "  - codepipeline:GetPipelineExecution (to get execution details)",
            "  - codepipeline:ListPipelineExecutions (to find failed executions)",
            "  - codebuild:BatchGetBuilds (to get CodeBuild logs)",
            "  - logs:GetLogEvents (to retrieve CloudWatch logs)",
            f"  - Resource: arn:aws:codepipeline:{AWS_REGION}:*:pipeline/*",
            f"  - Resource: arn:aws:codebuild:{AWS_REGION}:*:project/*",
            f"  - Resource: arn:aws:logs:{AWS_REGION}:*:log-group:*",
        ]
    else:
        # General permissions for all pipeline operations
        permissions = [
            "  - codepipeline:GetPipeline",
            "  - codepipeline:GetPipelineExecution",
            "  - codepipeline:GetPipelineState",
            "  - codepipeline:ListPipelineExecutions",
            "  - codepipeline:StartPipelineExecution",
            "  - codebuild:BatchGetBuilds",
            "  - logs:GetLogEvents",
            f"  - Resource: arn:aws:codepipeline:{AWS_REGION}:*:pipeline/*",
        ]

    # Add specific guidance based on error message content
    additional_guidance = []
    if "codepipeline:StartPipelineExecution" in error_message:
        additional_guidance.append(
            "The error specifically mentions StartPipelineExecution permission is missing"
        )
    elif "codepipeline:GetPipeline" in error_message:
        additional_guidance.append(
            "The error specifically mentions GetPipeline permission is missing"
        )
    elif "codebuild:BatchGetBuilds" in error_message:
        additional_guidance.append(
            "The error specifically mentions CodeBuild access permission is missing"
        )
    elif "logs:GetLogEvents" in error_message:
        additional_guidance.append(
            "The error specifically mentions CloudWatch Logs access permission is missing"
        )

    # Sample IAM policy
    policy_guidance = [
        "",
        "Sample IAM policy document:",
        "{",
        '  "Version": "2012-10-17",',
        '  "Statement": [',
        "    {",
        '      "Effect": "Allow",',
        '      "Action": [',
        '        "codepipeline:GetPipeline",',
        '        "codepipeline:GetPipelineExecution",',
        '        "codepipeline:GetPipelineState",',
        '        "codepipeline:ListPipelineExecutions",',
        '        "codepipeline:StartPipelineExecution",',
        '        "codebuild:BatchGetBuilds",',
        '        "logs:GetLogEvents"',
        "      ],",
        '      "Resource": "*"',
        "    }",
        "  ]",
        "}",
    ]

    return base_guidance + permissions + additional_guidance + policy_guidance
