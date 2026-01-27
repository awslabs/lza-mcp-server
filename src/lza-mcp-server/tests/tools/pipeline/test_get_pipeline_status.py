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


class TestPipelineStatusSuccess:
    """Test successful pipeline status retrieval scenarios."""

    @pytest.mark.asyncio
    async def test_get_pipeline_status_no_executions(self, mock_mcp_context):
        """Test getting status when pipeline has no executions."""
        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }
        mock_executions_response = {"pipelineExecutionSummaries": []}

        # Track which API calls have been made
        call_tracker = {"calls": []}

        async def mock_retry(func, **kwargs):
            # Track the call
            call_tracker["calls"].append((func, kwargs))
            
            # Determine which API call based on kwargs
            if "name" in kwargs and "pipelineName" not in kwargs:
                # get_pipeline call
                return mock_pipeline_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                # list_pipeline_executions call
                return mock_executions_response
            return {}

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["status"] == "NO_EXECUTIONS"
            assert "No executions found" in result["message"]
            assert result["stage_progress"]["total_stages"] == 2

    @pytest.mark.asyncio
    async def test_get_pipeline_status_in_progress(self, mock_mcp_context):
        """Test getting status for pipeline in progress."""
        # Clear cache before test
        from awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status import _pipeline_cache
        _pipeline_cache.clear()
        
        mock_pipeline_response = {
            "pipeline": {
                "stages": [
                    {"name": "Source"},
                    {"name": "Build"},
                    {"name": "Deploy"},
                ]
            }
        }

        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    "status": "InProgress",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                "status": "InProgress",
                "executionMode": "NORMAL",
                "creationTime": datetime(2024, 1, 15, 10, 30, 0),
            }
        }

        mock_state_response = {
            "stageStates": [
                {
                    "stageName": "Source",
                    "latestExecution": {
                        "status": "Succeeded",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                },
                {
                    "stageName": "Build",
                    "latestExecution": {
                        "status": "InProgress",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                    "actionStates": [
                        {
                            "actionName": "BuildAction",
                            "latestExecution": {"status": "InProgress"},
                        }
                    ],
                },
                {"stageName": "Deploy"},
            ]
        }

        call_sequence = []
        
        async def mock_retry(func, **kwargs):
            # Track call sequence to distinguish between get_pipeline and get_pipeline_state
            call_sequence.append(kwargs)
            
            # Determine which API call based on kwargs
            if "name" in kwargs and "pipelineName" not in kwargs and "pipelineExecutionId" not in kwargs:
                # Both get_pipeline and get_pipeline_state use 'name' parameter
                # get_pipeline is called first (Step 1), get_pipeline_state is called later (Step 5)
                # Count how many times we've seen 'name' parameter
                name_calls = sum(1 for call in call_sequence if "name" in call and "pipelineName" not in call)
                
                if name_calls == 1:
                    # First call with 'name' is get_pipeline
                    return mock_pipeline_response
                else:
                    # Second call with 'name' is get_pipeline_state
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                # list_pipeline_executions call
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
                # get_pipeline_execution call
                return mock_execution_response
            return {}

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["status"] == "INPROGRESS"
            assert result["current_stage"] == "Build"
            assert result["current_action"] == "BuildAction"
            assert result["stage_progress"]["current_stage_number"] == 2
            assert result["stage_progress"]["total_stages"] == 3
            assert result["stage_progress"]["completed_stages"] == 1

    @pytest.mark.asyncio
    async def test_get_pipeline_status_succeeded(self, mock_mcp_context):
        """Test getting status for successfully completed pipeline."""
        # Clear cache before test
        from awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status import _pipeline_cache
        _pipeline_cache.clear()
        
        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }

        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    "status": "Succeeded",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                "status": "Succeeded",
                "executionMode": "NORMAL",
                "creationTime": datetime(2024, 1, 15, 10, 30, 0),
                "lastUpdateTime": datetime(2024, 1, 15, 11, 0, 0),
            }
        }

        mock_state_response = {
            "stageStates": [
                {
                    "stageName": "Source",
                    "latestExecution": {
                        "status": "Succeeded",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                },
                {
                    "stageName": "Build",
                    "latestExecution": {
                        "status": "Succeeded",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                },
            ]
        }

        call_sequence = []
        
        async def mock_retry(func, **kwargs):
            # Track call sequence to distinguish between get_pipeline and get_pipeline_state
            call_sequence.append(kwargs)
            
            # Determine which API call based on kwargs
            if "name" in kwargs and "pipelineName" not in kwargs and "pipelineExecutionId" not in kwargs:
                # Both get_pipeline and get_pipeline_state use 'name' parameter
                # get_pipeline is called first (Step 1), get_pipeline_state is called later (Step 5)
                # Count how many times we've seen 'name' parameter
                name_calls = sum(1 for call in call_sequence if "name" in call and "pipelineName" not in call)
                
                if name_calls == 1:
                    # First call with 'name' is get_pipeline
                    return mock_pipeline_response
                else:
                    # Second call with 'name' is get_pipeline_state
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                # list_pipeline_executions call
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
                # get_pipeline_execution call
                return mock_execution_response
            return {}

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["status"] == "SUCCEEDED"
            assert "start_time" in result
            assert "end_time" in result
            assert result["stage_progress"]["completed_stages"] == 2


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
    async def test_execution_not_found(self, mock_mcp_context):
        """Test handling of execution not found error."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }

        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "different-id-1234-1234-1234-123456789012",
                    "status": "Succeeded",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        error_response = {"Error": {"Code": "PipelineExecutionNotFoundException"}}
        client_error = ClientError(error_response, "get_pipeline_execution")

        async def mock_retry(func, **kwargs):
            # Determine which API call based on kwargs
            if "name" in kwargs and "pipelineName" not in kwargs and "pipelineExecutionId" not in kwargs:
                # get_pipeline call
                return mock_pipeline_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                # list_pipeline_executions call
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
                # get_pipeline_execution call - raise error
                raise client_error
            return {}

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_get_pipeline_status(
                mock_mcp_context, pipeline_name="test-pipeline", execution_id=execution_id
            )

            assert result["success"] is False
            assert "PipelineExecutionNotFoundException" in result.get("error_code", "")
            assert execution_id in result["error"]

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
