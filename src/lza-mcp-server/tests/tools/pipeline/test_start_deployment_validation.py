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

"""Unit tests for start_deployment validation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.start_deployment import (
    tool_start_deployment,
)


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestStartDeploymentValidation:
    """Test input validation for start_deployment."""

    @pytest.mark.asyncio
    async def test_empty_pipeline_name(self):
        """Test start deployment with empty pipeline name."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, pipeline_name="")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_pipeline_name_too_long(self):
        """Test start deployment with pipeline name exceeding max length."""
        ctx = _make_ctx()
        long_name = "a" * 101
        result = await tool_start_deployment(ctx, pipeline_name=long_name)

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_invalid_characters_in_pipeline_name(self):
        """Test start deployment with invalid characters in name."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, pipeline_name="Invalid Pipeline!")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result
        assert any("special characters" in step for step in result["troubleshooting"])

    @pytest.mark.asyncio
    async def test_spaces_in_pipeline_name(self):
        """Test start deployment with spaces in name."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, pipeline_name="My Pipeline")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_valid_pipeline_name_formats(self):
        """Test start deployment accepts valid name formats."""
        ctx = _make_ctx()
        valid_names = [
            "AWSAccelerator-Pipeline",
            "my_pipeline",
            "pipeline.123",
            "Test-Pipeline_v1.0",
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
        ) as mock_client:
            mock_cp = Mock()
            mock_cp.get_pipeline.return_value = {"pipeline": {"name": "test"}}
            mock_cp.start_pipeline_execution.return_value = {
                "pipelineExecutionId": "test-id"
            }
            mock_client.return_value = mock_cp

            for name in valid_names:
                result = await tool_start_deployment(ctx, pipeline_name=name)
                assert "Invalid pipeline name" not in result.get("error", "")

    @pytest.mark.asyncio
    async def test_invalid_qualifier_empty(self):
        """Test start deployment with empty qualifier."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, qualifier="")

        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_qualifier_special_chars(self):
        """Test start deployment with special characters in qualifier."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, qualifier="bad qualifier!")

        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_qualifier_too_long(self):
        """Test start deployment with qualifier exceeding max length."""
        ctx = _make_ctx()
        result = await tool_start_deployment(ctx, qualifier="a" * 101)

        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]
