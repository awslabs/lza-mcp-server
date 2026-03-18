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

"""Unit tests for diagnose_pipeline_errors CodeBuild and CloudWatch Logs integration."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    _diagnose_standard_pipeline as tool_diagnose_pipeline_errors,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    context = Mock()
    context.request_context = Mock()
    context.request_context.session = Mock()
    return context


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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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

    @pytest.mark.asyncio
    async def test_logs_with_general_error_pattern_no_create_failed(
        self, mock_mcp_context
    ):
        """Test when logs have general error pattern but no CREATE_FAILED (line 279, 477)."""
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

        # Logs with general error pattern but no CREATE_FAILED
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
                return mock_build_response
            else:
                return mock_log_response

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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
            # Should have general error pattern (line 279)
            assert failed_action["specific_error"] == "| error | Something went wrong"
            assert "Error:" in failed_action["error_summary"]
            # Note: Message says "CREATE_FAILED error details" even for general errors
            # because specific_error is set (line 277 checks if specific_error exists)
            assert "failed action(s)" in result["message"]

    @pytest.mark.asyncio
    async def test_logs_with_no_error_patterns(self, mock_mcp_context):
        """Test when logs have no error patterns at all (line 279, 477)."""
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

        # Logs with no error patterns
        mock_log_response = {
            "events": [
                {"message": "Starting build"},
                {"message": "Running tests"},
                {"message": "Build completed"},
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

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codepipeline_client"
            ) as mock_cp_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_codebuild_client"
            ) as mock_cb_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
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
            # Should have logs but no specific error (line 477)
            assert failed_action["specific_error"] is None
            assert failed_action["codebuild_logs"] is not None
            # Line 279: When logs exist but no specific errors, message says "CodeBuild logs retrieved"
            assert "CodeBuild logs retrieved" in result["message"]
