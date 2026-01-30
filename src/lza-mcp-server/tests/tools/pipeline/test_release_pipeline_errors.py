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

"""Unit tests for release_pipeline error handling."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.release_pipeline import (
    tool_release_pipeline,
)


class TestReleasePipelineErrors:
    """Test error handling for pipeline release."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_not_found(self, mock_retry, mock_get_client):
        """Test pipeline release when pipeline doesn't exist."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate PipelineNotFoundException
        error_response = {
            "Error": {
                "Code": "PipelineNotFoundException",
                "Message": "Pipeline not found",
            }
        }
        mock_retry.side_effect = ClientError(error_response, "GetPipeline")

        result = await tool_release_pipeline(ctx, "NonExistent-Pipeline")

        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["error_code"] == "PipelineNotFoundException"
        assert "troubleshooting" in result
        assert any(
            "Verify the pipeline name" in step for step in result["troubleshooting"]
        )

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_access_denied(self, mock_retry, mock_get_client):
        """Test pipeline release with access denied error."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate AccessDeniedException
        error_response = {
            "Error": {"Code": "AccessDeniedException", "Message": "Access denied"}
        }
        mock_retry.side_effect = ClientError(error_response, "GetPipeline")

        result = await tool_release_pipeline(ctx, "Test-Pipeline")

        assert result["success"] is False
        assert "error" in result
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_generic_client_error(
        self, mock_retry, mock_get_client
    ):
        """Test pipeline release with generic client error."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate generic ClientError
        error_response = {
            "Error": {"Code": "InternalError", "Message": "Internal service error"}
        }
        mock_retry.side_effect = ClientError(error_response, "GetPipeline")

        result = await tool_release_pipeline(ctx, "Test-Pipeline")

        assert result["success"] is False
        assert "error" in result
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_unexpected_exception(
        self, mock_retry, mock_get_client
    ):
        """Test pipeline release with unexpected exception."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate unexpected exception
        mock_retry.side_effect = Exception("Unexpected error")

        result = await tool_release_pipeline(ctx, "Test-Pipeline")

        assert result["success"] is False
        assert "error" in result
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_start_execution_fails(
        self, mock_retry, mock_get_client
    ):
        """Test pipeline release when start_pipeline_execution fails."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # First call succeeds (get_pipeline), second fails (start_pipeline_execution)
        error_response = {
            "Error": {
                "Code": "InvalidStructureException",
                "Message": "Invalid pipeline",
            }
        }
        mock_retry.side_effect = [
            {"pipeline": {"name": "test"}},
            ClientError(error_response, "StartPipelineExecution"),
        ]

        result = await tool_release_pipeline(ctx, "Test-Pipeline")

        assert result["success"] is False
        assert "error" in result
        assert "troubleshooting" in result
