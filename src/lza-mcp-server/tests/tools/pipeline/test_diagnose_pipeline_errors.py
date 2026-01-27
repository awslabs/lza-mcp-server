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

"""Unit tests for diagnose_pipeline_errors module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors import (
    tool_diagnose_pipeline_errors,
    extract_error_line,
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


class TestExtractErrorLine:
    """Test the extract_error_line helper function."""

    def test_extract_error_line_found(self):
        """Test extracting error line when present."""
        logs = """
        Some log line
        Another line
        | error | Something went wrong
        More logs
        """
        result = extract_error_line(logs)
        assert result == "| error | Something went wrong"

    def test_extract_error_line_not_found(self):
        """Test when no error line is present."""
        logs = """
        Some log line
        Another line
        No errors here
        """
        result = extract_error_line(logs)
        assert result == ""

    def test_extract_error_line_empty_logs(self):
        """Test with empty logs."""
        result = extract_error_line("")
        assert result == ""

    def test_extract_error_line_none_logs(self):
        """Test with None logs."""
        result = extract_error_line(None)
        assert result == ""



class TestDiagnosePipelineErrorsErrors:
    """Test error handling in diagnose_pipeline_errors."""

    @pytest.mark.asyncio
    async def test_pipeline_not_found(self, mock_mcp_context):
        """Test handling when pipeline doesn't exist."""
        mock_error = ClientError(
            {"Error": {"Code": "PipelineNotFoundException", "Message": "Pipeline not found"}},
            "GetPipeline",
        )

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_error,
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="nonexistent-pipeline"
            )

            assert result["success"] is False
            assert "does not exist" in result["message"]
            assert result["error_code"] == "PipelineNotFoundException"
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_execution_not_found(self, mock_mcp_context):
        """Test handling when specific execution doesn't exist."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {"pipeline": {"name": "test-pipeline"}}
        mock_error = ClientError(
            {
                "Error": {
                    "Code": "PipelineExecutionNotFoundException",
                    "Message": "Execution not found",
                }
            },
            "GetPipelineExecution",
        )

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is get_pipeline (validation)
                return mock_pipeline_response
            else:
                # Second call is get_pipeline_execution - raise error
                raise mock_error

        # Need to also mock the synchronous call to get_pipeline_execution
        mock_codepipeline = Mock()
        mock_codepipeline.get_pipeline_execution.side_effect = mock_error

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

            assert result["success"] is False
            assert "does not exist" in result["message"]
            assert result["error_code"] == "PipelineExecutionNotFoundException"

    @pytest.mark.asyncio
    async def test_generic_aws_error(self, mock_mcp_context):
        """Test handling of generic AWS errors."""
        mock_error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetPipeline",
        )

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_error,
        ):
            mock_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is False
            assert "error" in result


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



class TestDiagnosePipelineErrorsCodeBuildIntegration:
    """Test CodeBuild and CloudWatch Logs integration."""

    @pytest.mark.asyncio
    async def test_failed_action_with_codebuild_logs(self, mock_mcp_context):
        """Test retrieving CodeBuild logs for failed action."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                                "externalExecutionId": build_id,
                            },
                        }
                    ],
                }
            ]
        }

        # Mock CodeBuild response
        mock_build_response = {
            "builds": [
                {
                    "id": build_id,
                    "logs": {
                        "groupName": "/aws/codebuild/test-project",
                        "streamName": "stream-123",
                    },
                }
            ]
        }

        # Mock CloudWatch Logs response
        mock_log_response = {
            "events": [
                {"message": "Starting build"},
                {"message": "| error | Something went wrong"},
                {"message": "Build failed"},
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
            elif call_count[0] == 4:
                return mock_state_response
            elif call_count[0] == 5:
                # CodeBuild batch_get_builds
                return mock_build_response
            else:
                # CloudWatch get_log_events
                return mock_log_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_logs_client"
        ) as mock_logs_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()
            mock_logs_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            assert failed_action["external_execution_id"] == build_id
            assert failed_action["codebuild_logs"] is not None
            assert failed_action["specific_error"] == "| error | Something went wrong"

    @pytest.mark.asyncio
    async def test_failed_action_with_create_failed_error(self, mock_mcp_context):
        """Test extracting CREATE_FAILED error from CodeBuild logs."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                    "stageName": "Deploy",
                    "latestExecution": {"pipelineExecutionId": execution_id},
                    "actionStates": [
                        {
                            "actionName": "DeployStack",
                            "actionTypeId": {"provider": "CodeBuild"},
                            "latestExecution": {
                                "status": "Failed",
                                "errorDetails": {
                                    "code": "JobFailed",
                                    "message": "CloudFormation stack failed",
                                },
                                "externalExecutionId": build_id,
                            },
                        }
                    ],
                }
            ]
        }

        mock_build_response = {
            "builds": [
                {
                    "id": build_id,
                    "logs": {
                        "groupName": "/aws/codebuild/test-project",
                        "streamName": "stream-123",
                    },
                }
            ]
        }

        # Mock CloudWatch Logs with CREATE_FAILED error
        mock_log_response = {
            "events": [
                {"message": "Starting deployment"},
                {
                    "message": "MyStack-123 | 0/5 | 10:26:03 AM | CREATE_FAILED | AWS::Lambda::Function | MyFunction"
                },
                {"message": "Stack deployment failed"},
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
            elif call_count[0] == 4:
                return mock_state_response
            elif call_count[0] == 5:
                return mock_build_response
            else:
                return mock_log_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_logs_client"
        ) as mock_logs_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()
            mock_logs_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            assert "CREATE_FAILED" in failed_action["specific_error"]
            assert "CREATE_FAILED" in failed_action["error_summary"]
            assert "CREATE_FAILED error details" in result["message"]

    @pytest.mark.asyncio
    async def test_failed_action_no_codebuild_logs(self, mock_mcp_context):
        """Test when CodeBuild build has no logs available."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                                "externalExecutionId": build_id,
                            },
                        }
                    ],
                }
            ]
        }

        # Mock CodeBuild response with no logs
        mock_build_response = {
            "builds": [
                {
                    "id": build_id,
                    # No logs field
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
            elif call_count[0] == 4:
                return mock_state_response
            else:
                return mock_build_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            # Should still have basic error info even without logs
            assert failed_action["error_code"] == "JobFailed"
            assert failed_action["codebuild_logs"] is None


    @pytest.mark.asyncio
    async def test_codebuild_retrieval_failure(self, mock_mcp_context):
        """Test handling when CodeBuild details retrieval fails."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                                "externalExecutionId": build_id,
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
            elif call_count[0] == 4:
                return mock_state_response
            else:
                # CodeBuild call fails
                raise Exception("CodeBuild API error")

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            # Should still succeed with basic error info even if CodeBuild retrieval fails
            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            assert failed_action["error_code"] == "JobFailed"
            # No logs due to retrieval failure
            assert failed_action["codebuild_logs"] is None

    @pytest.mark.asyncio
    async def test_cloudwatch_logs_retrieval_failure(self, mock_mcp_context):
        """Test handling when CloudWatch logs retrieval fails."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                                "externalExecutionId": build_id,
                            },
                        }
                    ],
                }
            ]
        }

        mock_build_response = {
            "builds": [
                {
                    "id": build_id,
                    "logs": {
                        "groupName": "/aws/codebuild/test-project",
                        "streamName": "stream-123",
                    },
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
            elif call_count[0] == 4:
                return mock_state_response
            elif call_count[0] == 5:
                return mock_build_response
            else:
                # CloudWatch logs call fails
                raise Exception("CloudWatch Logs API error")

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_logs_client"
        ) as mock_logs_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()
            mock_logs_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            # Should still succeed even if CloudWatch logs retrieval fails
            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            assert failed_action["error_code"] == "JobFailed"

    @pytest.mark.asyncio
    async def test_empty_cloudwatch_logs(self, mock_mcp_context):
        """Test handling when CloudWatch logs are empty."""
        execution_id = "12345678-1234-1234-1234-123456789012"
        build_id = "project:build-id"

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
                                "externalExecutionId": build_id,
                            },
                        }
                    ],
                }
            ]
        }

        mock_build_response = {
            "builds": [
                {
                    "id": build_id,
                    "logs": {
                        "groupName": "/aws/codebuild/test-project",
                        "streamName": "stream-123",
                    },
                }
            ]
        }

        # Empty log events
        mock_log_response = {"events": []}

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_pipeline_response
            elif call_count[0] == 2:
                return mock_executions_response
            elif call_count[0] == 3:
                return mock_execution_response
            elif call_count[0] == 4:
                return mock_state_response
            elif call_count[0] == 5:
                return mock_build_response
            else:
                return mock_log_response

        with patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codepipeline_client"
        ) as mock_cp_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_codebuild_client"
        ) as mock_cb_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.get_logs_client"
        ) as mock_logs_client, patch(
            "awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors.retry_with_exponential_backoff",
            side_effect=mock_retry,
        ):
            mock_cp_client.return_value = Mock()
            mock_cb_client.return_value = Mock()
            mock_logs_client.return_value = Mock()

            result = await tool_diagnose_pipeline_errors(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is True
            assert len(result["failed_actions"]) == 1
            
            failed_action = result["failed_actions"][0]
            # Should have basic error info even with empty logs
            assert failed_action["error_code"] == "JobFailed"
