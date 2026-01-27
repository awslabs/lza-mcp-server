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

"""Unit tests for diagnose_pipeline_errors success scenarios."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors import (
    tool_diagnose_pipeline_errors,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    return Mock()


class TestDiagnosePipelineErrorsSuccess:
    """Test successful scenarios for diagnose_pipeline_errors."""

    @pytest.mark.asyncio
    async def test_no_failed_executions_found(self, mock_mcp_context):
        """Test when pipeline has no failed executions."""
        mock_pipeline_response = {"pipeline": {"name": "test-pipeline"}}
        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
                    "status": "Succeeded",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_pipeline_response
            else:
                return mock_executions_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["pipeline_name"] == "test-pipeline"
            assert result["failed_actions"] == []
            assert "No failed executions found" in result["message"]

    @pytest.mark.asyncio
    async def test_execution_not_failed_status(self, mock_mcp_context):
        """Test when specified execution is not in failed status."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {"pipeline": {"name": "test-pipeline"}}
        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": execution_id,
                "status": "Succeeded",
            }
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_pipeline_response
            else:
                return mock_execution_response

        # Mock the synchronous get_pipeline_execution call
        mock_codepipeline = Mock()
        mock_codepipeline.get_pipeline_execution.return_value = mock_execution_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client",
            return_value=mock_codepipeline,
        ), patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context,
                pipeline_name="test-pipeline",
                execution_id=execution_id,
            )

            assert result["success"] is True
            assert result["execution_id"] == execution_id
            assert result["status"] == "Succeeded"
            assert result["failed_actions"] == []
            assert "no failures to diagnose" in result["message"]

    @pytest.mark.asyncio
    async def test_failed_execution_with_basic_error(self, mock_mcp_context):
        """Test diagnosing a failed execution with basic error details."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {"pipeline": {"name": "test-pipeline"}}
        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": execution_id,
                    "status": "Failed",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }
        mock_execution_response = {
            "pipelineExecution": {
                "pipelineExecutionId": execution_id,
                "status": "Failed",
            }
        }
        mock_state_response = {
            "stageStates": [
                {
                    "stageName": "Build",
                    "latestExecution": {"pipelineExecutionId": execution_id},
                    "actionStates": [
                        {
                            "actionName": "BuildAction",
                            "actionTypeId": {"provider": "CodeBuild"},
                            "latestExecution": {
                                "status": "Failed",
                                "errorDetails": {
                                    "code": "JobFailed",
                                    "message": "Build failed",
                                },
                            },
                        }
                    ],
                }
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_pipeline_response
            elif call_count[0] == 2:
                return mock_executions_response
            elif call_count[0] == 3:
                return mock_execution_response
            else:
                return mock_state_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert result["execution_id"] == execution_id
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            assert failed_action["stage_name"] == "Build"
            assert failed_action["action_name"] == "BuildAction"
            assert failed_action["action_type"] == "CodeBuild"
            assert failed_action["error_code"] == "JobFailed"
            assert failed_action["error_message"] == "Build failed"
            assert "basic error details" in result["message"]
