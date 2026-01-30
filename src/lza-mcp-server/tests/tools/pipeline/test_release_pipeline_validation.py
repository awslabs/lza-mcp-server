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

"""Unit tests for release_pipeline validation."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.pipeline.release_pipeline import (
    tool_release_pipeline,
)


class TestReleasePipelineValidation:
    """Test input validation for release_pipeline."""

    @pytest.mark.asyncio
    async def test_release_pipeline_empty_name(self):
        """Test release pipeline with empty pipeline name."""
        ctx = Mock()
        result = await tool_release_pipeline(ctx, pipeline_name="")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_release_pipeline_name_too_long(self):
        """Test release pipeline with pipeline name exceeding max length."""
        ctx = Mock()
        long_name = "a" * 101  # Exceeds 100 character limit
        result = await tool_release_pipeline(ctx, pipeline_name=long_name)

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_release_pipeline_invalid_characters(self):
        """Test release pipeline with invalid characters in name."""
        ctx = Mock()
        result = await tool_release_pipeline(ctx, pipeline_name="Invalid Pipeline!")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result
        assert any("special characters" in step for step in result["troubleshooting"])

    @pytest.mark.asyncio
    async def test_release_pipeline_with_spaces(self):
        """Test release pipeline with spaces in name."""
        ctx = Mock()
        result = await tool_release_pipeline(ctx, pipeline_name="My Pipeline")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_release_pipeline_valid_name_format(self):
        """Test release pipeline accepts valid name formats."""
        ctx = Mock()
        valid_names = [
            "AWSAccelerator-Pipeline",
            "my_pipeline",
            "pipeline.123",
            "Test-Pipeline_v1.0",
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.release_pipeline.get_codepipeline_client"
        ) as mock_client:
            mock_cp = Mock()
            mock_cp.get_pipeline.return_value = {"pipeline": {"name": "test"}}
            mock_cp.start_pipeline_execution.return_value = {
                "pipelineExecutionId": "test-id"
            }
            mock_client.return_value = mock_cp

            for name in valid_names:
                result = await tool_release_pipeline(ctx, pipeline_name=name)
                # Should not fail validation (may fail on AWS call, but that's different)
                assert "Invalid pipeline name" not in result.get("error", "")
