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

"""Unit tests for release_pipeline success scenarios."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.pipeline.release_pipeline import (
    tool_release_pipeline,
)


class TestReleasePipelineSuccess:
    """Test successful pipeline release scenarios."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_success(self, mock_retry, mock_get_client):
        """Test successful pipeline release."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Mock get_pipeline to verify pipeline exists
        mock_retry.side_effect = [
            {"pipeline": {"name": "AWSAccelerator-Pipeline"}},  # get_pipeline
            {"pipelineExecutionId": "exec-12345"},  # start_pipeline_execution
        ]

        result = await tool_release_pipeline(ctx, "AWSAccelerator-Pipeline")

        assert result["success"] is True
        assert result["execution_id"] == "exec-12345"
        assert result["pipeline_name"] == "AWSAccelerator-Pipeline"
        assert "started successfully" in result["message"]
        assert "error" not in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_with_custom_name(self, mock_retry, mock_get_client):
        """Test pipeline release with custom pipeline name."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        custom_name = "My-Custom-Pipeline"
        mock_retry.side_effect = [
            {"pipeline": {"name": custom_name}},
            {"pipelineExecutionId": "exec-67890"},
        ]

        result = await tool_release_pipeline(ctx, custom_name)

        assert result["success"] is True
        assert result["execution_id"] == "exec-67890"
        assert result["pipeline_name"] == custom_name
        assert custom_name in result["message"]

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.retry_with_exponential_backoff"
    )
    async def test_release_pipeline_returns_execution_id(
        self, mock_retry, mock_get_client
    ):
        """Test that pipeline release returns execution ID."""
        ctx = Mock()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        execution_id = "12345678-1234-1234-1234-123456789012"
        mock_retry.side_effect = [
            {"pipeline": {"name": "test"}},
            {"pipelineExecutionId": execution_id},
        ]

        result = await tool_release_pipeline(ctx, "test-pipeline")

        assert result["success"] is True
        assert result["execution_id"] == execution_id
        assert isinstance(result["execution_id"], str)
