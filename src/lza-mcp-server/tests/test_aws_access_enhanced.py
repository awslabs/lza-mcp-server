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

"""Enhanced unit tests for aws_access module."""

import pytest
import asyncio
import socket
from unittest.mock import Mock, patch
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ConnectionError as BotocoreConnectionError,
)

from awslabs.lza_mcp_server.aws_access import (
    get_aws_account_id,
    handle_aws_error,
    get_iam_permission_guidance,
    retry_with_exponential_backoff,
)


class TestAWSAccountAccess:
    """Test AWS account access functionality."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_success(self, mock_get_session):
        """Test successful AWS account ID retrieval."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_get_session.return_value = mock_session

        account_id = get_aws_account_id()

        assert account_id == "123456789012"
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once_with("sts")
        mock_sts_client.get_caller_identity.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_no_credentials(self, mock_get_session):
        """Test AWS account ID retrieval with no credentials."""
        mock_get_session.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            get_aws_account_id()


class TestRetryLogicEnhanced:
    """Enhanced test retry logic functionality."""

    def test_retry_with_exponential_backoff_max_retries_exceeded(self):
        """Test retry mechanism when max retries are exceeded."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
            },
            operation_name="TestOperation",
        )

        async def test_async():
            await retry_with_exponential_backoff(mock_func)

        with pytest.raises(ClientError) as exc_info:
            asyncio.run(test_async())

        assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"
        assert mock_func.call_count == 3  # MAX_RETRY_ATTEMPTS

    def test_retry_with_service_unavailable(self):
        """Test retry logic with ServiceUnavailable error."""
        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {
                        "Code": "ServiceUnavailable",
                        "Message": "Service unavailable",
                    }
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        async def test_async():
            result = await retry_with_exponential_backoff(mock_func)
            return result

        result = asyncio.run(test_async())
        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_with_request_limit_exceeded(self):
        """Test retry logic with RequestLimitExceeded error."""
        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {
                        "Code": "RequestLimitExceeded",
                        "Message": "Request limit exceeded",
                    }
                },
                operation_name="TestOperation",
            ),
            ClientError(
                error_response={
                    "Error": {
                        "Code": "RequestLimitExceeded",
                        "Message": "Request limit exceeded",
                    }
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        async def test_async():
            result = await retry_with_exponential_backoff(mock_func)
            return result

        result = asyncio.run(test_async())
        assert result == "success"
        assert mock_func.call_count == 3


class TestNetworkFailureHandling:
    """Test network failure and connectivity error handling."""

    def test_handle_network_timeout_error(self):
        """Test handling of network timeout errors."""
        error = socket.timeout("Connection timed out")
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "Connection timed out" in result["error"]
        assert any("network connectivity" in step for step in result["troubleshooting"])

    def test_handle_connection_error(self):
        """Test handling of connection errors."""
        error = BotocoreConnectionError(error=Exception("Connection failed"))
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert any("network connectivity" in step for step in result["troubleshooting"])

    def test_handle_dns_resolution_error(self):
        """Test handling of DNS resolution errors."""
        error = socket.gaierror("Name resolution failed")
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "Name resolution failed" in result["error"]
        assert any("network connectivity" in step for step in result["troubleshooting"])


class TestComprehensiveErrorHandling:
    """Test comprehensive error handling for all AWS service error codes."""

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

    def test_handle_invalid_parameter_error(self):
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

    def test_handle_concurrent_modification_error(self):
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

    def test_handle_invalid_next_token_error(self):
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
        assert any(
            "required parameters are provided" in step
            for step in result["troubleshooting"]
        )

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
        assert any(
            "codepipeline:GetPipeline" in step for step in result["troubleshooting"]
        )


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions in error handling."""

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

    def test_handle_none_exception(self):
        """Test handling of None as exception (edge case)."""
        result = handle_aws_error(None, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "None" in result["error"]

    def test_handle_unicode_error_message(self):
        """Test handling of error messages with unicode characters."""
        unicode_message = "Error with unicode: 测试 🚀 ñoño"
        error = ClientError(
            error_response={
                "Error": {"Code": "UnicodeError", "Message": unicode_message}
            },
            operation_name="TestOperation",
        )

        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert result["error_code"] == "UnicodeError"
        assert unicode_message in result["error"]


class TestIAMPermissionGuidanceEnhanced:
    """Enhanced test IAM permission guidance functionality."""

    def test_get_iam_guidance_for_codebuild_operations(self):
        """Test IAM permission guidance for CodeBuild operations."""
        guidance = get_iam_permission_guidance(
            "retrieving build logs", "codebuild:BatchGetBuilds"
        )

        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_guidance_for_logs_operations(self):
        """Test IAM permission guidance for CloudWatch Logs operations."""
        guidance = get_iam_permission_guidance(
            "accessing build logs", "logs:GetLogEvents"
        )

        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_guidance_with_specific_error_messages(self):
        """Test IAM guidance generation with specific error messages."""
        guidance = get_iam_permission_guidance(
            "starting pipeline",
            "User is not authorized to perform: codepipeline:StartPipelineExecution",
        )

        assert any(
            "StartPipelineExecution permission is missing" in step for step in guidance
        )
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)

    def test_get_iam_guidance_for_general_operations(self):
        """Test IAM guidance for general operations without specific context."""
        guidance = get_iam_permission_guidance(
            "general pipeline operation", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:GetPipelineExecution" in step for step in guidance)
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)
