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

"""Unit tests for aws_access module."""

import pytest
from unittest.mock import Mock
from botocore.exceptions import ClientError, NoCredentialsError

from awslabs.lza_mcp_server.aws_access import (
    get_aws_session,
    get_codepipeline_client,
    get_codebuild_client,
    get_logs_client,
    format_error_response,
    handle_aws_error,
    get_iam_permission_guidance,
    retry_with_exponential_backoff,
)


class TestAWSClients:
    """Test AWS client creation functions."""

    def test_get_aws_session(self):
        """Test AWS session creation."""
        session = get_aws_session()
        assert session is not None
        assert hasattr(session, "client")

    def test_get_codepipeline_client(self):
        """Test CodePipeline client creation."""
        client = get_codepipeline_client()
        assert client is not None
        assert hasattr(client, "get_pipeline")

    def test_get_codebuild_client(self):
        """Test CodeBuild client creation."""
        client = get_codebuild_client()
        assert client is not None
        assert hasattr(client, "batch_get_builds")

    def test_get_logs_client(self):
        """Test CloudWatch Logs client creation."""
        client = get_logs_client()
        assert client is not None
        assert hasattr(client, "get_log_events")


class TestAWSErrorHandling:
    """Test AWS error handling functionality."""

    def test_handle_no_credentials_error(self):
        """Test handling of NoCredentialsError."""
        error = NoCredentialsError()
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "credentials not configured" in result["message"]
        assert any("AWS_ACCESS_KEY_ID" in step for step in result["troubleshooting"])

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
        assert any(
            "codepipeline:StartPipelineExecution" in step
            for step in result["troubleshooting"]
        )

    def test_handle_throttling_error(self):
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

    def test_handle_generic_exception(self):
        """Test handling of generic exceptions."""
        error = Exception("Generic error")
        result = handle_aws_error(error, "test operation")

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "Generic error" in result["error"]

    def test_format_error_response_basic(self):
        """Test basic error response formatting."""
        result = format_error_response("Test error", "Test message")

        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["message"] == "Test message"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0

    def test_format_error_response_with_details(self):
        """Test error response formatting with additional details."""
        troubleshooting = ["Step 1", "Step 2"]
        result = format_error_response(
            "Test error",
            "Test message",
            error_code="TestCode",
            troubleshooting=troubleshooting,
        )

        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["message"] == "Test message"
        assert result["error_code"] == "TestCode"
        assert result["troubleshooting"] == troubleshooting


class TestIAMPermissionGuidance:
    """Test IAM permission guidance functionality."""

    def test_get_iam_permission_guidance_pipeline_release(self):
        """Test IAM permission guidance for pipeline release operations."""
        guidance = get_iam_permission_guidance(
            "starting pipeline execution", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_permission_guidance_pipeline_status(self):
        """Test IAM permission guidance for pipeline status operations."""
        guidance = get_iam_permission_guidance(
            "getting status for pipeline", "Access denied"
        )

        assert any("codepipeline:GetPipelineExecution" in step for step in guidance)
        assert any("codepipeline:GetPipelineState" in step for step in guidance)
        assert any("codepipeline:ListPipelineExecutions" in step for step in guidance)

    def test_get_iam_permission_guidance_error_diagnosis(self):
        """Test IAM permission guidance for error diagnosis operations."""
        guidance = get_iam_permission_guidance(
            "diagnosing pipeline errors", "Access denied"
        )

        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)


class TestRetryLogic:
    """Test retry logic functionality."""

    def test_retry_with_exponential_backoff_success(self):
        """Test retry mechanism with successful operation."""
        # Mock function that succeeds
        mock_func = Mock(return_value="success")

        # Test async wrapper
        async def test_async():
            result = await retry_with_exponential_backoff(
                mock_func, "arg1", kwarg1="value1"
            )
            return result

        # Run the test
        import asyncio

        result = asyncio.run(test_async())

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_retry_with_exponential_backoff_throttling(self):
        """Test retry mechanism with throttling errors."""
        # Mock function that fails with throttling then succeeds
        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        # Test async wrapper
        async def test_async():
            result = await retry_with_exponential_backoff(mock_func)
            return result

        # Run the test
        import asyncio

        result = asyncio.run(test_async())

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_with_exponential_backoff_non_retryable_error(self):
        """Test retry mechanism with non-retryable errors."""
        # Mock function that fails with non-retryable error
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="TestOperation",
        )

        # Test async wrapper
        async def test_async():
            await retry_with_exponential_backoff(mock_func)

        # Run the test and expect exception
        import asyncio

        with pytest.raises(ClientError) as exc_info:
            asyncio.run(test_async())

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        mock_func.assert_called_once()
