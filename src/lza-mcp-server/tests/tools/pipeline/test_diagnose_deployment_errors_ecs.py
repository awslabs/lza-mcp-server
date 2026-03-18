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

"""Unit tests for diagnose_deployment_errors ECS container diagnosis via CloudWatch Logs."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    tool_diagnose_deployment_errors,
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


QUALIFIER = "container-dev-1"
LOG_GROUP = f"/ecs/{QUALIFIER}-lza-deployment"
QUALIFIER_PIPELINE = f"{QUALIFIER}-pipeline"
TASK_ID = "abc123def456"
STREAM_NAME = f"ecs/lza-deployment-container/{TASK_ID}"


def _pipeline_not_found_error():
    """Create a PipelineNotFoundException ClientError."""
    return ClientError(
        {
            "Error": {
                "Code": "PipelineNotFoundException",
                "Message": "Pipeline not found",
            }
        },
        "GetPipeline",
    )


def _mock_no_pipeline():
    """Patch _diagnose_standard_pipeline to return PipelineNotFoundException."""
    return patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline",
        new_callable=AsyncMock,
        return_value={
            "success": False,
            "error_code": "PipelineNotFoundException",
            "error": f"Pipeline '{QUALIFIER_PIPELINE}' not found",
            "message": f"The specified pipeline '{QUALIFIER_PIPELINE}' does not exist",
        },
    )


class TestDiagnoseDeploymentErrorsCwl:
    """Test CloudWatch Logs-based container deployment diagnosis."""

    @pytest.mark.asyncio
    async def test_log_group_not_found(self, mock_mcp_context):
        """Test handling when the log group doesn't exist and no pipeline exists."""
        mock_error = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Log group not found",
                }
            },
            "DescribeLogStreams",
        )

        async def mock_retry(func, **kwargs):
            raise mock_error

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            # Neither pipeline nor log group found
            assert result["success"] is False
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_no_deployment_streams(self, mock_mcp_context):
        """Test when log group exists but prefix returns no matching streams."""
        mock_streams_response = {"logStreams": []}

        async def mock_retry(func, **kwargs):
            return mock_streams_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["deployment_type"] == "external_pipeline"
            # Container diagnosis present with empty deployments
            container = result["container_diagnosis"]
            assert container is not None
            assert container["failed_deployments"] == []

    @pytest.mark.asyncio
    async def test_empty_log_group(self, mock_mcp_context):
        """Test when log group exists but has no streams at all."""
        mock_streams_response = {"logStreams": []}

        async def mock_retry(func, **kwargs):
            return mock_streams_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            container = result["container_diagnosis"]
            assert container is not None
            assert container["failed_deployments"] == []

    @pytest.mark.asyncio
    async def test_deployment_with_create_failed(self, mock_mcp_context):
        """Test diagnosing a deployment with CREATE_FAILED error in logs."""
        mock_streams_response = {
            "logStreams": [
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                    "firstEventTimestamp": 1699999000000,
                },
            ]
        }
        mock_log_response = {
            "events": [
                {"message": "Phase 1: S3 Config Initialization"},
                {"message": "Phase 2: External Pipeline Configuration"},
                {"message": "Phase 3: Pipeline Execution"},
                {
                    "message": "MyStack-123 | 0/5 | 10:26:03 AM | CREATE_FAILED | AWS::Lambda::Function | MyFunction"
                },
                {"message": "Deployment failed with exit code 1"},
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_streams_response
            else:
                return mock_log_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["deployment_type"] == "external_pipeline"

            container = result["container_diagnosis"]
            assert container is not None
            assert len(container["failed_deployments"]) == 1

            deployment = container["failed_deployments"][0]
            assert deployment["task_id"] == TASK_ID
            assert "Phase 3" in deployment["phase_reached"]
            assert "CREATE_FAILED" in deployment["specific_error"]
            assert deployment["logs"] is not None
            assert deployment["last_event_time"] == 1700000000000

    @pytest.mark.asyncio
    async def test_deployment_with_general_error(self, mock_mcp_context):
        """Test diagnosing a deployment with general error pattern."""
        mock_streams_response = {
            "logStreams": [
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                    "firstEventTimestamp": 1699999000000,
                },
            ]
        }
        mock_log_response = {
            "events": [
                {"message": "Phase 1: S3 Config Initialization"},
                {"message": "| error | Configuration validation failed"},
                {"message": "Deployment failed"},
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_streams_response
            else:
                return mock_log_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            container = result["container_diagnosis"]
            assert len(container["failed_deployments"]) == 1
            deployment = container["failed_deployments"][0]
            assert "error" in deployment["specific_error"].lower()
            assert "Phase 1" in deployment["phase_reached"]

    @pytest.mark.asyncio
    async def test_deployment_stream_empty_events(self, mock_mcp_context):
        """Test handling when a deployment stream has no log events."""
        mock_streams_response = {
            "logStreams": [
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                },
            ]
        }
        mock_log_response = {"events": []}

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_streams_response
            else:
                return mock_log_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            container = result["container_diagnosis"]
            # Empty stream should not produce a deployment entry
            assert len(container["failed_deployments"]) == 0

    @pytest.mark.asyncio
    async def test_skips_non_deployment_streams_to_find_match(self, mock_mcp_context):
        """Test that pagination skips non-deployment streams to find the deployment one."""
        mock_streams_response = {
            "logStreams": [
                {
                    "logStreamName": "some-sidecar-stream",
                    "lastEventTimestamp": 1800000000000,
                },
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                    "firstEventTimestamp": 1699999000000,
                },
            ]
        }
        mock_log_response = {
            "events": [
                {"message": "Phase 1: S3 Config Initialization"},
                {"message": "Deployment completed"},
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_streams_response
            else:
                return mock_log_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            container = result["container_diagnosis"]
            assert len(container["failed_deployments"]) == 1
            assert container["failed_deployments"][0]["task_id"] == TASK_ID

    @pytest.mark.asyncio
    async def test_paginates_to_find_deployment_stream(self, mock_mcp_context):
        """Test that pagination continues across pages to find the deployment stream."""
        page1 = {
            "logStreams": [
                {
                    "logStreamName": "other-stream-1",
                    "lastEventTimestamp": 1800000000000,
                },
                {
                    "logStreamName": "other-stream-2",
                    "lastEventTimestamp": 1790000000000,
                },
            ],
            "nextToken": "page2token",
        }
        page2 = {
            "logStreams": [
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                    "firstEventTimestamp": 1699999000000,
                },
            ]
        }
        mock_log_response = {
            "events": [
                {"message": "Phase 1: S3 Config Initialization"},
                {"message": "| error | Something broke"},
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return page1
            elif call_count[0] == 2:
                return page2
            else:
                return mock_log_response

        with (
            _mock_no_pipeline(),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            container = result["container_diagnosis"]
            assert len(container["failed_deployments"]) == 1
            assert container["failed_deployments"][0]["task_id"] == TASK_ID
            assert (
                "error" in container["failed_deployments"][0]["specific_error"].lower()
            )

    @pytest.mark.asyncio
    async def test_both_pipeline_and_container_found(self, mock_mcp_context):
        """Test when both CodePipeline and ECS container exist for a qualifier."""
        mock_pipeline_result = {
            "success": True,
            "pipeline_name": QUALIFIER_PIPELINE,
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "failed_actions": [
                {
                    "stage_name": "Deploy",
                    "action_name": "DeployAction",
                    "error_code": "JobFailed",
                    "error_message": "Stack failed",
                }
            ],
            "message": "Found 1 failed action(s)",
        }

        mock_streams_response = {
            "logStreams": [
                {
                    "logStreamName": STREAM_NAME,
                    "lastEventTimestamp": 1700000000000,
                    "firstEventTimestamp": 1699999000000,
                },
            ]
        }
        mock_log_response = {
            "events": [
                {"message": "Phase 1: S3 Config Initialization"},
                {"message": "Phase 3: Pipeline Execution"},
                {"message": "| error | Deploy failed"},
            ]
        }

        call_count = [0]

        async def mock_retry(func, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_streams_response
            else:
                return mock_log_response

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline",
                new_callable=AsyncMock,
                return_value=mock_pipeline_result,
            ),
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.get_logs_client"
            ) as mock_logs,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_diagnose_deployment_errors(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["deployment_type"] == "external_pipeline"
            assert "CodePipeline" in result["sources_checked"]
            assert "ECS container" in result["sources_checked"]

            # Pipeline diagnosis present
            assert result["pipeline_diagnosis"] is not None
            assert len(result["pipeline_diagnosis"]["failed_actions"]) == 1

            # Container diagnosis present
            assert result["container_diagnosis"] is not None
            assert len(result["container_diagnosis"]["failed_deployments"]) == 1
