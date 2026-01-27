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

"""Unit tests for diagnose_pipeline_errors input validation."""

import pytest
from unittest.mock import Mock

from awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors import (
    tool_diagnose_pipeline_errors,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    return Mock()


class TestDiagnosePipelineErrorsValidation:
    """Test input validation for diagnose_pipeline_errors."""

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_empty(self, mock_mcp_context):
        """Test validation rejects empty pipeline name."""
        result = await tool_diagnose_pipeline_errors(
            mock_mcp_context, pipeline_name=""
        )

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_too_long(self, mock_mcp_context):
        """Test validation rejects pipeline name that's too long."""
        result = await tool_diagnose_pipeline_errors(
            mock_mcp_context, pipeline_name="a" * 101
        )

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_special_chars(self, mock_mcp_context):
        """Test validation rejects pipeline name with invalid characters."""
        result = await tool_diagnose_pipeline_errors(
            mock_mcp_context, pipeline_name="test@pipeline!"
        )

        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "naming requirements" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_execution_id_format(self, mock_mcp_context):
        """Test validation rejects invalid execution ID format."""
        result = await tool_diagnose_pipeline_errors(
            mock_mcp_context,
            pipeline_name="test-pipeline",
            execution_id="invalid-format",
        )

        assert result["success"] is False
        assert "Invalid execution ID" in result["error"]
        assert "format requirements" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_execution_id_empty(self, mock_mcp_context):
        """Test validation rejects empty execution ID."""
        result = await tool_diagnose_pipeline_errors(
            mock_mcp_context, pipeline_name="test-pipeline", execution_id=""
        )

        assert result["success"] is False
        assert "Invalid execution ID" in result["error"]
