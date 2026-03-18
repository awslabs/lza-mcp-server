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

"""Unit tests for diagnose_deployment_errors input validation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    tool_diagnose_deployment_errors,
    _diagnose_standard_pipeline,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestDiagnoseDeploymentErrorsValidation:
    """Test input validation for diagnose_deployment_errors."""

    @pytest.mark.asyncio
    async def test_invalid_qualifier_empty(self, mock_mcp_context):
        """Test validation rejects empty qualifier."""
        result = await tool_diagnose_deployment_errors(mock_mcp_context, qualifier="")
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_qualifier_special_chars(self, mock_mcp_context):
        """Test validation rejects qualifier with invalid characters."""
        result = await tool_diagnose_deployment_errors(
            mock_mcp_context, qualifier="test@qualifier!"
        )
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]
        assert "format requirements" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_qualifier_too_long(self, mock_mcp_context):
        """Test validation rejects qualifier that's too long."""
        result = await tool_diagnose_deployment_errors(
            mock_mcp_context, qualifier="a" * 101
        )
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_no_qualifier_delegates_to_pipeline(self, mock_mcp_context):
        """Test that no qualifier delegates to standard pipeline diagnosis."""
        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
        ) as mock_pipeline:
            mock_pipeline.return_value = {
                "success": True,
                "pipeline_name": "AWSAccelerator-Pipeline",
                "failed_actions": [],
                "message": "No failed executions found",
            }

            result = await tool_diagnose_deployment_errors(mock_mcp_context)

            mock_pipeline.assert_called_once()
            assert result["success"] is True
            assert result["deployment_type"] == "standard"

    @pytest.mark.asyncio
    async def test_pipeline_not_found_adds_qualifier_hint(self, mock_mcp_context):
        """Test that PipelineNotFoundException adds qualifier hint."""
        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
        ) as mock_pipeline:
            mock_pipeline.return_value = {
                "success": False,
                "error": "Pipeline not found",
                "error_code": "PipelineNotFoundException",
                "message": "Pipeline does not exist",
                "troubleshooting": ["Check pipeline name"],
            }

            result = await tool_diagnose_deployment_errors(mock_mcp_context)

            assert result["success"] is False
            assert result["deployment_type"] == "standard"
            # Should have added qualifier hint
            troubleshooting = result["troubleshooting"]
            assert any("qualifier" in step.lower() for step in troubleshooting)
            assert any("checkAwsConnectivity" in step for step in troubleshooting)


class TestStandardPipelineValidation:
    """Test input validation for the standard pipeline diagnosis path."""

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_empty(self, mock_mcp_context):
        """Test validation rejects empty pipeline name."""
        result = await _diagnose_standard_pipeline(mock_mcp_context, pipeline_name="")
        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_too_long(self, mock_mcp_context):
        """Test validation rejects pipeline name that's too long."""
        result = await _diagnose_standard_pipeline(
            mock_mcp_context, pipeline_name="a" * 101
        )
        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_special_chars(self, mock_mcp_context):
        """Test validation rejects pipeline name with invalid characters."""
        result = await _diagnose_standard_pipeline(
            mock_mcp_context, pipeline_name="test@pipeline!"
        )
        assert result["success"] is False
        assert "Invalid pipeline name" in result["error"]
        assert "naming requirements" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_execution_id_format(self, mock_mcp_context):
        """Test validation rejects invalid execution ID format."""
        result = await _diagnose_standard_pipeline(
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
        result = await _diagnose_standard_pipeline(
            mock_mcp_context,
            pipeline_name="test-pipeline",
            execution_id="",
        )
        assert result["success"] is False
        assert "Invalid execution ID" in result["error"]
