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

"""Unit tests for get_deployment_status error paths not covered by existing tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    _get_standard_pipeline_status,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestStandardPipelineReRaiseErrors:
    """Test re-raise paths for non-specific ClientErrors."""

    @pytest.mark.asyncio
    async def test_get_pipeline_non_not_found_error(self, mock_mcp_context):
        """Test that non-PipelineNotFoundException errors from get_pipeline are re-raised and handled."""
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

        _pipeline_cache.clear()

        access_denied = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetPipeline",
        )

        async def mock_retry(func, **kwargs):
            if "name" in kwargs and "pipelineName" not in kwargs:
                raise access_denied
            return {}

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await _get_standard_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            # Should be handled by the outer except and return an error via handle_aws_error
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_pipeline_execution_non_not_found_error(self, mock_mcp_context):
        """Test that non-PipelineExecutionNotFoundException errors from get_pipeline_execution are re-raised."""
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

        _pipeline_cache.clear()

        throttle_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetPipelineExecution",
        )

        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }
        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    "status": "InProgress",
                }
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)
            if "name" in kwargs and "pipelineName" not in kwargs:
                return mock_pipeline_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
                raise throttle_error
            return {}

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await _get_standard_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            # ThrottlingException should be re-raised and caught by outer handler
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_generic_exception_handler(self, mock_mcp_context):
        """Test the outer generic exception handler in _get_standard_pipeline_status."""
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

        _pipeline_cache.clear()

        async def mock_retry(func, **kwargs):
            raise RuntimeError("Unexpected failure")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await _get_standard_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is False
            assert "error" in result
