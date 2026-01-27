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

"""Unit tests for get_pipeline_status module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status import (
    tool_get_pipeline_status,
    get_stage_description,
    get_action_description,
    get_cached_pipeline_metadata,
    cache_pipeline_metadata,
)


class TestStageDescriptions:
    """Test stage and action description functions."""

    def test_get_stage_description_known_stages(self):
        """Test getting descriptions for known LZA pipeline stages."""
        known_stages = {
            "Source": "Retrieves LZA source code",
            "Prepare": "Creates and validates AWS accounts",
            "Accounts": "Validates all accounts",
            "Bootstrap": "Runs AWS CDK bootstrap",
            "Logging": "Deploys centralized KMS keys",
            "Organization": "Deploys AWS Organization-wide resources",
            "SecurityAudit": "Deploys security service dependencies",
            "Deploy": "Deploys infrastructure",
        }

        for stage_name, expected_substring in known_stages.items():
            description = get_stage_description(stage_name)
            assert expected_substring in description
            assert len(description) > 0

    def test_get_stage_description_unknown_stage(self):
        """Test getting description for unknown stage."""
        description = get_stage_description("UnknownStage")
        assert description == "Stage: UnknownStage"

    def test_get_action_description_known_actions(self):
        """Test getting descriptions for known LZA pipeline actions."""
        known_actions = {
            "Network_Prepare": "Creates Transit Gateway",
            "Network_VPCs": "Deploys VPCs",
        }

        for action_name, expected_substring in known_actions.items():
            description = get_action_description(action_name)
            assert expected_substring in description
            assert len(description) > 0

    def test_get_action_description_unknown_action(self):
        """Test getting description for unknown action."""
        description = get_action_description("UnknownAction")
        assert description == "Action: UnknownAction"


class TestCacheFunctions:
    """Test pipeline metadata caching functions."""

    def test_cache_and_retrieve_pipeline_metadata(self):
        """Test caching and retrieving pipeline metadata."""
        pipeline_name = "test-pipeline"
        metadata = {
            "stages": [{"name": "Source"}, {"name": "Build"}],
            "total_stages": 2,
        }

        cache_pipeline_metadata(pipeline_name, metadata)
        cached = get_cached_pipeline_metadata(pipeline_name)

        assert cached is not None
        assert cached == metadata
        assert cached["total_stages"] == 2
        assert len(cached["stages"]) == 2

    def test_get_cached_pipeline_metadata_not_found(self):
        """Test retrieving non-existent cached metadata."""
        result = get_cached_pipeline_metadata("non-existent-pipeline-xyz")
        assert result is None


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
        result = await tool_get_pipeline_status(mock_mcp_context, pipeline_name=long_name)

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


class TestPipelineStatusErrors:
    """Test error handling in pipeline status retrieval."""

    @pytest.mark.asyncio
    async def test_pipeline_not_found(self, mock_mcp_context):
        """Test handling of pipeline not found error."""
        error_response = {"Error": {"Code": "PipelineNotFoundException"}}
        client_error = ClientError(error_response, "get_pipeline")

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=client_error,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="non-existent-pipeline"
            )

            assert result["success"] is False
            assert "PipelineNotFoundException" in result.get("error_code", "")
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_generic_aws_error(self, mock_mcp_context):
        """Test handling of generic AWS errors."""
        error_response = {"Error": {"Code": "AccessDeniedException"}}
        client_error = ClientError(error_response, "get_pipeline")

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=client_error,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is False
            assert "error" in result
