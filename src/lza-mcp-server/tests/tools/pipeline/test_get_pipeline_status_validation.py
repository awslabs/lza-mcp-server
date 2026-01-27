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

"""Unit tests for get_pipeline_status input validation."""

import pytest

from awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status import (
    tool_get_pipeline_status,
)


class TestPipelineStatusValidation:
    """Test input validation for get_pipeline_status."""

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_empty(self, mock_mcp_context):
        """Test with empty pipeline name."""
        result = await tool_get_pipeline_status(mock_mcp_context, pipeline_name="")

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_too_long(self, mock_mcp_context):
        """Test with pipeline name exceeding max length."""
        long_name = "a" * 101
        result = await tool_get_pipeline_status(
            mock_mcp_context, pipeline_name=long_name
        )

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_special_chars(self, mock_mcp_context):
        """Test with pipeline name containing invalid characters."""
        result = await tool_get_pipeline_status(
            mock_mcp_context, pipeline_name="pipeline with spaces"
        )

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_execution_id_format(self, mock_mcp_context):
        """Test with invalid execution ID format."""
        result = await tool_get_pipeline_status(
            mock_mcp_context,
            pipeline_name="test-pipeline",
            execution_id="invalid-format",
        )

        assert result["success"] is False
        assert "Invalid execution ID" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_execution_id_empty(self, mock_mcp_context):
        """Test with empty execution ID."""
        result = await tool_get_pipeline_status(
            mock_mcp_context, pipeline_name="test-pipeline", execution_id=""
        )

        assert result["success"] is False
        assert "Invalid execution ID" in result["error"]
