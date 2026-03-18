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

"""Unit tests for diagnose_pipeline_errors error handling."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    _diagnose_standard_pipeline as tool_diagnose_pipeline_errors,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    return Mock()


class TestDiagnosePipelineErrorsErrors:
    """Test error handling in diagnose_pipeline_errors."""

    @pytest.mark.asyncio
    async def test_pipeline_not_found(self, mock_mcp_context):
        """Test handling when pipeline doesn't exist."""
        mock_error = ClientError(
            {
                "Error": {
                    "Code": "PipelineNotFoundException",
                    "Message": "Pipeline not found",
                }
            },
            "GetPipeline",
        )

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_error,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="nonexistent-pipeline"
            )

            assert result["success"] is False
            assert "does not exist" in result["message"]
            assert result["error_code"] == "PipelineNotFoundException"
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_execution_not_found(self, mock_mcp_context):
        """Test handling when specific execution doesn't exist."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {"pipeline": {"name": "test-pipeline"}}
        mock_error = ClientError(
            {
                "Error": {
                    "Code": "PipelineExecutionNotFoundException",
                    "Message": "Execution not found",
                }
            },
            "GetPipelineExecution",
        )

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is get_pipeline (validation)
                return mock_pipeline_response
            else:
                # Second call is get_pipeline_execution - raise error
                raise mock_error

        # Need to also mock the synchronous call to get_pipeline_execution
        mock_codepipeline = Mock()
        mock_codepipeline.get_pipeline_execution.side_effect = mock_error

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client",
                return_value=mock_codepipeline,
            ),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context,
                pipeline_name="test-pipeline",
                execution_id=execution_id,
            )

            assert result["success"] is False
            assert "does not exist" in result["message"]
            assert result["error_code"] == "PipelineExecutionNotFoundException"

    @pytest.mark.asyncio
    async def test_generic_aws_error(self, mock_mcp_context):
        """Test handling of generic AWS errors."""
        mock_error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetPipeline",
        )

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_error,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is False
            assert "error" in result
