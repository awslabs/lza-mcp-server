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
from typing import Dict, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

from .constants import DEFAULT_REGION, MAX_RETRY_ATTEMPTS, INITIAL_RETRY_DELAY
from .error_categories import ErrorCategory
from .utils.error_handling import (
    format_error_response,
)

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


def get_s3_client() -> boto3.client:
    """Create an S3 client using the configured AWS session with retry configuration.

    Returns:
        boto3.client: S3 client configured with the current session and retry logic

    Raises:
        NoCredentialsError: If AWS credentials are not properly configured
        ClientError: If there are issues creating the client
    """
    session = get_aws_session()
    config = Config(
        retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "adaptive"},
        max_pool_connections=50,
    )
    return session.client("s3", config=config)


def download_from_s3(bucket: str, key: str, local_path: str) -> bool:
    """
    Download a file from S3 to a local path.

    Args:
        bucket: The S3 bucket name
        key: The S3 object key
        local_path: The local file path to save to

    Returns:
        bool: True if successful, False otherwise
    """
    session = get_aws_session()
    s3_client = session.client("s3")

    try:
        s3_client.download_file(bucket, key, local_path)
        logger.info(f"Successfully downloaded {bucket}/{key} to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {bucket}/{key}: {str(e)}")
        return False


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


def categorize_aws_error(error: Exception) -> Dict[str, Any]:
    """
    Categorize AWS errors and provide specific troubleshooting guidance.

    Args:
        error: AWS exception to categorize

    Returns:
        Dictionary with error category and troubleshooting steps
    """
    if isinstance(error, NoCredentialsError):
        return {
            "category": ErrorCategory.CONNECTIVITY,
            "error_code": "NO_CREDENTIALS",
            "troubleshooting": [
                "Configure AWS credentials using one of these methods:",
                "  - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                "  - Configure AWS profile with 'aws configure'",
                "  - Use IAM roles if running on EC2",
                "  - For Docker: pass credentials as environment variables",
            ],
        }

    elif isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "Unknown")

        if error_code == "AccessDenied":
            return {
                "category": ErrorCategory.CONNECTIVITY,
                "error_code": error_code,
                "troubleshooting": [
                    "AWS credentials lack necessary permissions",
                    "Ensure the user/role has the following permissions:",
                    "  - sts:GetCallerIdentity (for connectivity verification)",
                    "  - s3:ListBucket (for bucket verification)",
                    "  - s3:PutObject (for configuration upload)",
                    "  - s3:GetBucketLocation (for bucket region verification)",
                    "Check IAM policies and resource-based policies",
                ],
            }

        elif error_code == "NoSuchBucket":
            return {
                "category": ErrorCategory.S3,
                "error_code": error_code,
                "troubleshooting": [
                    "The specified S3 bucket does not exist",
                    "Verify the bucket name is correct",
                    "Check that the bucket exists in your AWS account",
                    "Ensure the bucket is in the same region as your AWS session",
                    "Create the bucket if it doesn't exist",
                ],
            }

        elif error_code == "InvalidBucketName":
            return {
                "category": ErrorCategory.S3,
                "error_code": error_code,
                "troubleshooting": [
                    "The bucket name does not meet AWS S3 naming requirements",
                    "Bucket names must be 3-63 characters long",
                    "Must contain only lowercase letters, numbers, periods, and hyphens",
                    "Cannot start or end with periods or hyphens",
                    "Cannot contain consecutive periods",
                ],
            }

        elif error_code in ["Throttling", "RequestLimitExceeded", "SlowDown"]:
            return {
                "category": ErrorCategory.S3,
                "error_code": error_code,
                "troubleshooting": [
                    "AWS API rate limit exceeded",
                    "Wait a few moments and retry the operation",
                    "Consider implementing exponential backoff",
                    "Check if other processes are making concurrent requests",
                ],
            }

        elif error_code == "InvalidUserID.NotFound":
            return {
                "category": ErrorCategory.CONNECTIVITY,
                "error_code": error_code,
                "troubleshooting": [
                    "AWS credentials may be invalid or expired",
                    "Try refreshing your AWS credentials",
                    "Verify the access key ID is correct",
                    "Check if the IAM user still exists",
                ],
            }

        else:
            return {
                "category": ErrorCategory.S3,
                "error_code": error_code,
                "troubleshooting": [
                    f"AWS API error: {error_code}",
                    "Check AWS service status for any ongoing issues",
                    "Verify your AWS credentials and permissions",
                    "Check network connectivity to AWS services",
                ],
            }

    elif isinstance(error, BotoCoreError):
        return {
            "category": ErrorCategory.CONNECTIVITY,
            "error_code": "BOTOCORE_ERROR",
            "troubleshooting": [
                "AWS configuration error detected",
                "Check AWS region configuration (AWS_REGION or AWS_DEFAULT_REGION)",
                "Verify AWS configuration files are properly formatted",
                "Check network connectivity and DNS resolution",
                "Ensure boto3 and botocore are up to date",
            ],
        }

    else:
        return {
            "category": ErrorCategory.INTEGRATION,
            "error_code": "UNEXPECTED_ERROR",
            "troubleshooting": [
                "An unexpected error occurred",
                "Check system resources and disk space",
                "Verify network connectivity",
                "Check application logs for more details",
                "Contact support if the issue persists",
            ],
        }


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
