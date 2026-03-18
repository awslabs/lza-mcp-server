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

"""Unit tests for get_pipeline_status edge cases and fallback logic."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    tool_get_deployment_status,
)


class TestPipelineStatusEdgeCases:
    """Test edge cases and fallback logic in pipeline status retrieval."""

    @pytest.mark.asyncio
    async def test_inprogress_execution_no_active_stages(self, mock_mcp_context):
        """Test INPROGRESS execution when no stages show InProgress status (fallback logic)."""
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

        # No stages show InProgress - all are waiting or not started
        mock_state_response = {
            "stageStates": [
                {"stageName": "Source"},
                {"stageName": "Build"},
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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

            # Should use fallback logic: assume starting at first stage
            assert result["success"] is True
            assert result["status"] == "INPROGRESS"
            assert result["current_stage"] == "Source"
            assert result["stage_progress"]["current_stage_number"] == 1
            # The message shows stage info when current_stage is set
            assert "stage 1 of 2" in result["message"]

    @pytest.mark.asyncio
    async def test_failed_pipeline_execution(self, mock_mcp_context):
        """Test FAILED pipeline execution status."""
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
                    "status": "Failed",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                "status": "Failed",
                "executionMode": "NORMAL",
                "creationTime": datetime(2024, 1, 15, 10, 30, 0),
                "lastUpdateTime": datetime(2024, 1, 15, 10, 45, 0),
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
                        "status": "Failed",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                },
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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
            assert result["status"] == "FAILED"
            assert "Pipeline execution failed" in result["message"]
            assert result["current_stage"] == "Build"  # Should show final stage

    @pytest.mark.asyncio
    async def test_stopped_pipeline_execution(self, mock_mcp_context):
        """Test STOPPED pipeline execution status."""
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
                    "status": "Stopped",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                "status": "Stopped",
                "executionMode": "NORMAL",
                "creationTime": datetime(2024, 1, 15, 10, 30, 0),
                "lastUpdateTime": datetime(2024, 1, 15, 10, 35, 0),
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
                {"stageName": "Build"},
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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
            assert result["status"] == "STOPPED"
            assert "Pipeline execution was stopped" in result["message"]

    @pytest.mark.asyncio
    async def test_specific_execution_id_with_completed_status(self, mock_mcp_context):
        """Test providing specific execution ID for a completed execution."""
        # Clear cache before test
        from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
            _pipeline_cache,
        )

        _pipeline_cache.clear()

        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }

        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": execution_id,
                    "status": "Succeeded",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": execution_id,
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
                        "pipelineExecutionId": execution_id,
                    },
                },
                {
                    "stageName": "Build",
                    "latestExecution": {
                        "status": "Succeeded",
                        "pipelineExecutionId": execution_id,
                    },
                },
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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
                mock_mcp_context,
                pipeline_name="test-pipeline",
                execution_id=execution_id,
            )

            assert result["success"] is True
            assert result["status"] == "SUCCEEDED"
            # When specific execution ID is provided, message should show stage info
            assert "stage 2 of 2" in result["message"]
            assert result["current_stage"] == "Build"

    @pytest.mark.asyncio
    async def test_unknown_status_handling(self, mock_mcp_context):
        """Test handling of unknown/unexpected pipeline status."""
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
                    "status": "UnknownStatus",  # Unexpected status
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                "status": "UnknownStatus",
                "executionMode": "NORMAL",
                "creationTime": datetime(2024, 1, 15, 10, 30, 0),
            }
        }

        # No stages have execution info
        mock_state_response = {
            "stageStates": [
                {"stageName": "Source"},
                {"stageName": "Build"},
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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

            # Should handle unknown status gracefully
            assert result["success"] is True
            assert result["status"] == "UNKNOWNSTATUS"
            # For unknown status with no current_stage, message shows execution status (uppercased)
            assert result["message"] == "Pipeline execution status: UNKNOWNSTATUS"
            # current_stage and current_action are not in response when None
            assert "current_stage" not in result
            assert "current_action" not in result
            assert result["stage_progress"]["current_stage_number"] == 0

    @pytest.mark.asyncio
    async def test_multiple_inprogress_stages(self, mock_mcp_context):
        """Test handling when multiple stages are in progress simultaneously."""
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
                    {"name": "Test"},
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

        # Multiple stages showing InProgress status
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
                            "latestExecution": {
                                "status": "InProgress",
                                "lastStatusChange": datetime(2024, 1, 15, 10, 35, 0),
                            },
                        }
                    ],
                },
                {
                    "stageName": "Test",
                    "latestExecution": {
                        "status": "InProgress",
                        "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    },
                    "actionStates": [
                        {
                            "actionName": "TestAction",
                            "latestExecution": {
                                "status": "InProgress",
                                "lastStatusChange": datetime(2024, 1, 15, 10, 40, 0),
                            },
                        }
                    ],
                },
                {"stageName": "Deploy"},
            ]
        }

        call_sequence = []

        async def mock_retry(func, **kwargs):
            call_sequence.append(kwargs)

            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                name_calls = sum(
                    1
                    for call in call_sequence
                    if "name" in call and "pipelineName" not in call
                )
                if name_calls == 1:
                    return mock_pipeline_response
                else:
                    return mock_state_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
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

            # Should pick the first in-progress stage (Build, not Test)
            assert result["success"] is True
            assert result["status"] == "INPROGRESS"
            assert result["current_stage"] == "Build"
            assert result["current_action"] == "BuildAction"
            # Message should show current stage info
            assert "stage 2 of 4" in result["message"]
            assert "1 stages completed" in result["message"]
