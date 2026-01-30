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

"""Unit tests for AWS error handling in aws_access module."""

from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

from awslabs.lza_mcp_server.aws_access import handle_aws_error, categorize_aws_error
from awslabs.lza_mcp_server.error_categories import ErrorCategory


class TestNoCredentialsErrorHandling:
    """Test handling of NoCredentialsError."""

    def test_handle_no_credentials_error(self):
        """Test handling of NoCredentialsError."""
        error = NoCredentialsError()
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "credentials not configured" in result["message"]
        assert any("AWS_ACCESS_KEY_ID" in step for step in result["troubleshooting"])
        assert any("AWS_PROFILE" in step for step in result["troubleshooting"])
        assert any("IAM roles" in step for step in result["troubleshooting"])

    def test_categorize_no_credentials_error(self):
        """Test categorization of NoCredentialsError."""
        error = NoCredentialsError()
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.CONNECTIVITY
        assert result["error_code"] == "NO_CREDENTIALS"
        assert any("AWS_ACCESS_KEY_ID" in step for step in result["troubleshooting"])


class TestPipelineErrorHandling:
    """Test handling of pipeline-specific errors."""

    def test_handle_pipeline_not_found_error(self):
        """Test handling of PipelineNotFoundException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "PipelineNotFoundException",
                    "Message": "Pipeline not found",
                }
            },
            operation_name="GetPipeline",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "PipelineNotFoundException"
        assert "Pipeline not found" in result["error"]
        assert any(
            "pipeline name is correct" in step for step in result["troubleshooting"]
        )
        assert any("AWS region" in step for step in result["troubleshooting"])

    def test_handle_pipeline_execution_not_found_error(self):
        """Test handling of PipelineExecutionNotFoundException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "PipelineExecutionNotFoundException",
                    "Message": "Execution not found",
                }
            },
            operation_name="GetPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "PipelineExecutionNotFoundException"
        assert "not found" in result["error"]
        assert any(
            "execution ID is correct" in step for step in result["troubleshooting"]
        )
        assert any(
            "list-pipeline-executions" in step for step in result["troubleshooting"]
        )

    def test_handle_pipeline_execution_not_stoppable_error(self):
        """Test handling of PipelineExecutionNotStoppableException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "PipelineExecutionNotStoppableException",
                    "Message": "Pipeline execution cannot be stopped",
                }
            },
            operation_name="StopPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "PipelineExecutionNotStoppableException"
        assert "cannot be stopped" in result["message"]
        assert any("already be completed" in step for step in result["troubleshooting"])


class TestAccessDeniedErrorHandling:
    """Test handling of access denied errors."""

    def test_handle_access_denied_error(self):
        """Test handling of AccessDenied error."""
        error = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "AccessDenied"
        assert "Insufficient permissions" in result["message"]
        assert any("IAM permissions" in step for step in result["troubleshooting"])

    def test_handle_unauthorized_operation_error(self):
        """Test handling of UnauthorizedOperation error."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "UnauthorizedOperation",
                    "Message": "You are not authorized to perform this operation",
                }
            },
            operation_name="GetPipeline",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "UnauthorizedOperation"
        assert "Insufficient permissions" in result["message"]

    def test_categorize_access_denied_error(self):
        """Test categorization of AccessDenied error."""
        error = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="GetPipeline",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.CONNECTIVITY
        assert result["error_code"] == "AccessDenied"
        assert any(
            "sts:GetCallerIdentity" in step for step in result["troubleshooting"]
        )
        assert any("s3:ListBucket" in step for step in result["troubleshooting"])


class TestThrottlingErrorHandling:
    """Test handling of throttling and rate limit errors."""

    def test_handle_throttling_exception(self):
        """Test handling of ThrottlingException."""
        error = ClientError(
            error_response={
                "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "ThrottlingException"
        assert "rate limit exceeded" in result["message"]
        assert any("Wait a few seconds" in step for step in result["troubleshooting"])
        assert any("exponential backoff" in step for step in result["troubleshooting"])

    def test_handle_throttling_error_alternate_code(self):
        """Test handling of Throttling error (alternate code)."""
        error = ClientError(
            error_response={
                "Error": {"Code": "Throttling", "Message": "Rate exceeded"}
            },
            operation_name="GetPipeline",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "Throttling"
        assert "rate limit exceeded" in result["message"]

    def test_handle_request_limit_exceeded_error(self):
        """Test handling of RequestLimitExceeded."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "RequestLimitExceeded",
                    "Message": "Request limit exceeded",
                }
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "RequestLimitExceeded"
        assert "request limit exceeded" in result["message"]
        assert any(
            "maximum number of requests" in step for step in result["troubleshooting"]
        )

    def test_categorize_throttling_error(self):
        """Test categorization of throttling errors."""
        error = ClientError(
            error_response={
                "Error": {"Code": "Throttling", "Message": "Rate exceeded"}
            },
            operation_name="GetPipeline",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "Throttling"
        assert any("rate limit exceeded" in step for step in result["troubleshooting"])


class TestValidationErrorHandling:
    """Test handling of validation and parameter errors."""

    def test_handle_invalid_parameter_exception(self):
        """Test handling of InvalidParameterException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidParameterException",
                    "Message": "Invalid parameter value",
                }
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "InvalidParameterException"
        assert "Invalid parameters" in result["message"]
        assert any(
            "required parameters are provided" in step
            for step in result["troubleshooting"]
        )
        assert any(
            "Pipeline names must be" in step for step in result["troubleshooting"]
        )

    def test_handle_validation_exception(self):
        """Test handling of ValidationException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid parameter format",
                }
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "ValidationException"
        assert "Invalid parameters" in result["message"]

    def test_handle_invalid_next_token_exception(self):
        """Test handling of InvalidNextTokenException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidNextTokenException",
                    "Message": "Invalid pagination token",
                }
            },
            operation_name="ListPipelineExecutions",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "InvalidNextTokenException"
        assert "Invalid pagination token" in result["message"]
        assert any(
            "Do not manually modify" in step for step in result["troubleshooting"]
        )


class TestConcurrencyErrorHandling:
    """Test handling of concurrency-related errors."""

    def test_handle_concurrent_modification_exception(self):
        """Test handling of ConcurrentModificationException."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "ConcurrentModificationException",
                    "Message": "Pipeline is being modified",
                }
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "ConcurrentModificationException"
        assert "being modified by another operation" in result["message"]
        assert any("Wait a few seconds" in step for step in result["troubleshooting"])
        assert any("CloudTrail logs" in step for step in result["troubleshooting"])


class TestS3ErrorHandling:
    """Test handling of S3-specific errors."""

    def test_categorize_no_such_bucket_error(self):
        """Test categorization of NoSuchBucket error."""
        error = ClientError(
            error_response={
                "Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}
            },
            operation_name="GetObject",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "NoSuchBucket"
        assert any(
            "bucket does not exist" in step for step in result["troubleshooting"]
        )
        assert any(
            "bucket name is correct" in step for step in result["troubleshooting"]
        )

    def test_categorize_invalid_bucket_name_error(self):
        """Test categorization of InvalidBucketName error."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidBucketName",
                    "Message": "Invalid bucket name",
                }
            },
            operation_name="CreateBucket",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "InvalidBucketName"
        assert any("3-63 characters" in step for step in result["troubleshooting"])
        assert any("lowercase letters" in step for step in result["troubleshooting"])

    def test_categorize_slow_down_error(self):
        """Test categorization of SlowDown error."""
        error = ClientError(
            error_response={
                "Error": {"Code": "SlowDown", "Message": "Please reduce request rate"}
            },
            operation_name="PutObject",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "SlowDown"
        assert any("rate limit exceeded" in step for step in result["troubleshooting"])


class TestBotoCoreErrorHandling:
    """Test handling of BotoCoreError."""

    def test_categorize_botocore_error(self):
        """Test categorization of BotoCoreError."""
        error = BotoCoreError()

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.CONNECTIVITY
        assert result["error_code"] == "BOTOCORE_ERROR"
        assert any(
            "AWS region configuration" in step for step in result["troubleshooting"]
        )
        assert any("boto3 and botocore" in step for step in result["troubleshooting"])


class TestGenericErrorHandling:
    """Test handling of generic and unexpected errors."""

    def test_handle_generic_client_error(self):
        """Test handling of generic ClientError."""
        error = ClientError(
            error_response={
                "Error": {"Code": "UnknownError", "Message": "Unknown error occurred"}
            },
            operation_name="StartPipelineExecution",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "UnknownError"
        assert "AWS API error" in result["message"]
        assert any("AWS service status" in step for step in result["troubleshooting"])

    def test_handle_generic_exception(self):
        """Test handling of generic exceptions."""
        error = Exception("Generic error")
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "Generic error" in result["error"]
        assert any("network connectivity" in step for step in result["troubleshooting"])

    def test_categorize_unexpected_error(self):
        """Test categorization of unexpected errors."""
        error = ValueError("Unexpected error")

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.INTEGRATION
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert any("unexpected error" in step for step in result["troubleshooting"])

    def test_handle_empty_error_response(self):
        """Test handling of ClientError with empty error response."""
        error = ClientError(
            error_response={"Error": {}}, operation_name="TestOperation"
        )
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "Unknown"
        assert "AWS API error" in result["message"]

    def test_handle_malformed_error_response(self):
        """Test handling of ClientError with malformed error response."""
        error = ClientError(error_response={}, operation_name="TestOperation")
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "AWS API error" in result["message"]


class TestEdgeCases:
    """Test edge cases in error handling."""

    def test_categorize_invalid_user_id_error(self):
        """Test categorization of InvalidUserID.NotFound error."""
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidUserID.NotFound",
                    "Message": "User ID not found",
                }
            },
            operation_name="GetCallerIdentity",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.CONNECTIVITY
        assert result["error_code"] == "InvalidUserID.NotFound"
        assert any(
            "credentials may be invalid" in step for step in result["troubleshooting"]
        )

    def test_categorize_generic_s3_error(self):
        """Test categorization of generic S3 error."""
        error = ClientError(
            error_response={
                "Error": {"Code": "S3Error", "Message": "S3 error occurred"}
            },
            operation_name="GetObject",
        )

        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "S3Error"
        assert any("AWS API error" in step for step in result["troubleshooting"])
