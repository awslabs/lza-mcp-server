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

"""Unit tests for retry logic with exponential backoff in aws_access module."""

import pytest
from unittest.mock import Mock
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import retry_with_exponential_backoff


class TestRetrySuccess:
    """Test retry logic with successful operations."""

    @pytest.mark.asyncio
    async def test_retry_with_immediate_success(self):
        """Test retry mechanism with immediate success."""
        mock_func = Mock(return_value="success")

        result = await retry_with_exponential_backoff(
            mock_func, "arg1", kwarg1="value1"
        )

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_retry_with_no_arguments(self):
        """Test retry mechanism with no arguments."""
        mock_func = Mock(return_value="success")

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_complex_return_value(self):
        """Test retry mechanism with complex return value."""
        expected_result = {"status": "success", "data": [1, 2, 3]}
        mock_func = Mock(return_value=expected_result)

        result = await retry_with_exponential_backoff(mock_func)

        assert result == expected_result
        assert result["status"] == "success"
        assert result["data"] == [1, 2, 3]


class TestRetryThrottling:
    """Test retry logic with throttling errors."""

    @pytest.mark.asyncio
    async def test_retry_with_throttling_exception(self):
        """Test retry mechanism with ThrottlingException."""
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

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_throttling_alternate_code(self):
        """Test retry mechanism with Throttling error code."""
        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {"Code": "Throttling", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_request_limit_exceeded(self):
        """Test retry mechanism with RequestLimitExceeded error."""
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
            "success",
        ]

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_service_unavailable(self):
        """Test retry mechanism with ServiceUnavailable error."""
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

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_multiple_throttling_errors(self):
        """Test retry mechanism with multiple throttling errors."""
        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        result = await retry_with_exponential_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3


class TestRetryMaxAttempts:
    """Test retry logic when max attempts are exceeded."""

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test retry mechanism when max retries are exceeded."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
            },
            operation_name="TestOperation",
        )

        with pytest.raises(ClientError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"
        assert mock_func.call_count == 3  # MAX_RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_retry_max_attempts_with_service_unavailable(self):
        """Test retry mechanism when max retries exceeded with ServiceUnavailable."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ServiceUnavailable",
                    "Message": "Service unavailable",
                }
            },
            operation_name="TestOperation",
        )

        with pytest.raises(ClientError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert exc_info.value.response["Error"]["Code"] == "ServiceUnavailable"
        assert mock_func.call_count == 3


class TestRetryNonRetryableErrors:
    """Test retry logic with non-retryable errors."""

    @pytest.mark.asyncio
    async def test_retry_with_access_denied_error(self):
        """Test retry mechanism with non-retryable AccessDenied error."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="TestOperation",
        )

        with pytest.raises(ClientError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_pipeline_not_found_error(self):
        """Test retry mechanism with non-retryable PipelineNotFoundException."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "PipelineNotFoundException",
                    "Message": "Pipeline not found",
                }
            },
            operation_name="GetPipeline",
        )

        with pytest.raises(ClientError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert exc_info.value.response["Error"]["Code"] == "PipelineNotFoundException"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_validation_exception(self):
        """Test retry mechanism with non-retryable ValidationException."""
        mock_func = Mock()
        mock_func.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Invalid parameter",
                }
            },
            operation_name="StartPipelineExecution",
        )

        with pytest.raises(ClientError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert exc_info.value.response["Error"]["Code"] == "ValidationException"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_generic_exception(self):
        """Test retry mechanism with generic non-AWS exception."""
        mock_func = Mock()
        mock_func.side_effect = ValueError("Invalid value")

        with pytest.raises(ValueError) as exc_info:
            await retry_with_exponential_backoff(mock_func)

        assert str(exc_info.value) == "Invalid value"
        mock_func.assert_called_once()


class TestRetryExponentialBackoff:
    """Test exponential backoff behavior."""

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff_timing(self):
        """Test that retry delays increase exponentially."""
        import time

        mock_func = Mock()
        mock_func.side_effect = [
            ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                },
                operation_name="TestOperation",
            ),
            "success",
        ]

        start_time = time.time()
        result = await retry_with_exponential_backoff(mock_func)
        elapsed_time = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 3
        # First retry: 1s, second retry: 2s = 3s total minimum
        assert elapsed_time >= 3.0


class TestRetryEdgeCases:
    """Test edge cases in retry logic."""

    @pytest.mark.asyncio
    async def test_retry_with_none_return_value(self):
        """Test retry mechanism with None return value."""
        mock_func = Mock(return_value=None)

        result = await retry_with_exponential_backoff(mock_func)

        assert result is None
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_false_return_value(self):
        """Test retry mechanism with False return value."""
        mock_func = Mock(return_value=False)

        result = await retry_with_exponential_backoff(mock_func)

        assert result is False
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_empty_dict_return_value(self):
        """Test retry mechanism with empty dict return value."""
        mock_func = Mock(return_value={})

        result = await retry_with_exponential_backoff(mock_func)

        assert result == {}
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_preserves_function_arguments(self):
        """Test that retry preserves function arguments across attempts."""
        call_args_list = []

        def track_calls(*args, **kwargs):
            call_args_list.append((args, kwargs))
            if len(call_args_list) < 2:
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ThrottlingException",
                            "Message": "Rate exceeded",
                        }
                    },
                    operation_name="TestOperation",
                )
            return "success"

        result = await retry_with_exponential_backoff(
            track_calls, "arg1", "arg2", key1="value1", key2="value2"
        )

        assert result == "success"
        assert len(call_args_list) == 2
        # Verify all calls had the same arguments
        assert call_args_list[0] == (
            ("arg1", "arg2"),
            {"key1": "value1", "key2": "value2"},
        )
        assert call_args_list[1] == (
            ("arg1", "arg2"),
            {"key1": "value1", "key2": "value2"},
        )
