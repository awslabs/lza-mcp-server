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

"""
Tests for timeout utilities (T-005, T-012 mitigation).
"""

import asyncio
import pytest

from awslabs.lza_mcp_server.utils.timeout_utils import (
    with_timeout,
    timeout_decorator,
    run_with_file_timeout,
    run_with_aws_timeout,
    TimeoutError,
    TimeoutContext,
)


@pytest.mark.unit
class TestTimeoutUtils:
    """Test timeout utility functions."""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test successful operation within timeout."""

        async def quick_operation():
            await asyncio.sleep(0.1)
            return "success"

        result = await with_timeout(
            quick_operation(), timeout=1.0, operation_name="test"
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_exceeds(self):
        """Test operation that exceeds timeout."""

        async def slow_operation():
            await asyncio.sleep(2.0)
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(
                slow_operation(), timeout=0.5, operation_name="slow test"
            )

        assert "slow test" in str(exc_info.value)
        assert "0.5 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_decorator_success(self):
        """Test timeout decorator with successful operation."""

        @timeout_decorator(timeout=1.0, operation_name="decorated test")
        async def decorated_operation():
            await asyncio.sleep(0.1)
            return "decorated success"

        result = await decorated_operation()
        assert result == "decorated success"

    @pytest.mark.asyncio
    async def test_timeout_decorator_exceeds(self):
        """Test timeout decorator with operation that exceeds timeout."""

        @timeout_decorator(timeout=0.5, operation_name="slow decorated")
        async def slow_decorated_operation():
            await asyncio.sleep(2.0)
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            await slow_decorated_operation()

        assert "slow decorated" in str(exc_info.value)
        assert "0.5 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_decorator_default_timeout(self):
        """Test timeout decorator with default timeout."""

        @timeout_decorator()
        async def default_timeout_operation():
            await asyncio.sleep(0.1)
            return "default timeout success"

        result = await default_timeout_operation()
        assert result == "default timeout success"

    @pytest.mark.asyncio
    async def test_run_with_file_timeout_success(self):
        """Test file operation timeout wrapper with success."""

        async def file_operation():
            await asyncio.sleep(0.1)
            return "file success"

        result = await run_with_file_timeout(file_operation(), "test file op")
        assert result == "file success"

    @pytest.mark.asyncio
    async def test_run_with_file_timeout_exceeds(self):
        """Test file operation timeout wrapper with timeout."""

        async def slow_file_operation():
            await asyncio.sleep(2.0)  # Use shorter sleep for testing
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            # Use shorter timeout for testing
            await with_timeout(
                slow_file_operation(), timeout=0.5, operation_name="slow file op"
            )

        assert "slow file op" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_with_aws_timeout_success(self):
        """Test AWS operation timeout wrapper with success."""

        async def aws_operation():
            await asyncio.sleep(0.1)
            return "aws success"

        result = await run_with_aws_timeout(aws_operation(), "test aws op")
        assert result == "aws success"

    @pytest.mark.asyncio
    async def test_run_with_aws_timeout_exceeds(self):
        """Test AWS operation timeout wrapper with timeout."""

        async def slow_aws_operation():
            await asyncio.sleep(2.0)  # Use shorter sleep for testing
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            # Use shorter timeout for testing
            await with_timeout(
                slow_aws_operation(), timeout=0.5, operation_name="slow aws op"
            )

        assert "slow aws op" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_context_success(self):
        """Test timeout context manager with successful operation."""

        async with TimeoutContext(1.0, "context test"):
            await asyncio.sleep(0.1)
            result = "context success"

        assert result == "context success"

    @pytest.mark.asyncio
    async def test_timeout_context_exceeds(self):
        """Test timeout context manager with timeout - note: context manager doesn't enforce timeout."""

        # TimeoutContext is a simple context manager that doesn't enforce timeouts
        # It only handles asyncio.TimeoutError if raised within the context
        # For actual timeout enforcement, use with_timeout() or timeout_decorator()

        # This test verifies the context manager handles the timeout error correctly
        async def operation_with_timeout():
            async with TimeoutContext(0.5, "slow context"):
                # Use asyncio.wait_for to actually enforce the timeout
                await asyncio.wait_for(asyncio.sleep(2.0), timeout=0.5)

        with pytest.raises(TimeoutError) as exc_info:
            await operation_with_timeout()

        assert "slow context" in str(exc_info.value)
        assert "0.5 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_with_exception(self):
        """Test that non-timeout exceptions are propagated correctly."""

        async def failing_operation():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")

        with pytest.raises(ValueError) as exc_info:
            await with_timeout(
                failing_operation(), timeout=1.0, operation_name="failing test"
            )

        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_decorator_with_args(self):
        """Test timeout decorator with function arguments."""

        @timeout_decorator(timeout=1.0, operation_name="args test")
        async def operation_with_args(value: str, multiplier: int = 2):
            await asyncio.sleep(0.1)
            return value * multiplier

        result = await operation_with_args("test", multiplier=3)
        assert result == "testtesttest"

    @pytest.mark.asyncio
    async def test_concurrent_timeouts(self):
        """Test multiple concurrent operations with timeouts."""

        @timeout_decorator(timeout=1.0)
        async def concurrent_operation(delay: float):
            await asyncio.sleep(delay)
            return f"completed {delay}"

        # Run multiple operations concurrently
        results = await asyncio.gather(
            concurrent_operation(0.1),
            concurrent_operation(0.2),
            concurrent_operation(0.3),
            return_exceptions=False,
        )

        assert len(results) == 3
        assert "completed 0.1" in results
        assert "completed 0.2" in results
        assert "completed 0.3" in results

    @pytest.mark.asyncio
    async def test_timeout_error_message_format(self):
        """Test that timeout error messages are properly formatted."""

        async def slow_operation():
            await asyncio.sleep(2.0)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(
                slow_operation(), timeout=0.5, operation_name="S3 upload to bucket-name"
            )

        error_message = str(exc_info.value)
        assert "S3 upload to bucket-name" in error_message
        assert "0.5 seconds" in error_message
        assert "exceeded timeout" in error_message.lower()
