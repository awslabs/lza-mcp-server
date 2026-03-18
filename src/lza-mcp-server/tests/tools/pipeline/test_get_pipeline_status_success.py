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

"""Unit tests for get_pipeline_status success scenarios."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    tool_get_deployment_status,
)


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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
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
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

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
            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                # Both get_pipeline and get_pipeline_state use 'name' parameter
                # get_pipeline is called first (Step 1), get_pipeline_state is called later (Step 5)
                # Count how many times we've seen 'name' parameter
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )

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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
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
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

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
            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                # Both get_pipeline and get_pipeline_state use 'name' parameter
                # get_pipeline is called first (Step 1), get_pipeline_state is called later (Step 5)
                # Count how many times we've seen 'name' parameter
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )

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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["status"] == "SUCCEEDED"
            assert "start_time" in result
            assert "end_time" in result
            assert result["stage_progress"]["completed_stages"] == 2
