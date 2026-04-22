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

"""Unit tests for diagnose_deployment_errors internal functions."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    _find_deployment_stream_by_task_id,
    _analyze_deployment_log_stream,
    _find_failures_in_stage,
)

_RETRY = "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors.retry_with_exponential_backoff"


def _ce(code, msg="err"):
    """Create a ClientError with the given error code."""
    return ClientError({"Error": {"Code": code, "Message": msg}}, "op")


class TestFindDeploymentStreamByTaskId:
    """Test _find_deployment_stream_by_task_id helper."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_stream_found(self, mock_retry):
        """Test finding a stream matching the task ID."""
        logs_client = Mock()
        stream = {"logStreamName": "ecs/lza-deployment-container/abc123"}
        mock_retry.return_value = {"logStreams": [stream]}

        result = await _find_deployment_stream_by_task_id(
            logs_client, "/ecs/my-log-group", "abc123"
        )

        assert result == stream

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_stream_not_found(self, mock_retry):
        """Test when no stream matches the task ID."""
        logs_client = Mock()
        mock_retry.return_value = {"logStreams": []}

        result = await _find_deployment_stream_by_task_id(
            logs_client, "/ecs/my-log-group", "abc123"
        )

        assert result is None

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_client_error_returns_none(self, mock_retry):
        """Test that ClientError is caught and returns None."""
        logs_client = Mock()
        mock_retry.side_effect = _ce("AccessDeniedException")

        result = await _find_deployment_stream_by_task_id(
            logs_client, "/ecs/my-log-group", "abc123"
        )

        assert result is None

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_stream_name_mismatch(self, mock_retry):
        """Test when streams exist but none match the exact task ID."""
        logs_client = Mock()
        mock_retry.return_value = {
            "logStreams": [
                {"logStreamName": "lza-container-runner/accelerator/other-task"}
            ]
        }

        result = await _find_deployment_stream_by_task_id(
            logs_client, "/ecs/my-log-group", "abc123"
        )

        assert result is None


class TestAnalyzeDeploymentLogStream:
    """Test _analyze_deployment_log_stream helper."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_resource_not_found_returns_none(self, mock_retry):
        """Test ResourceNotFoundException returns None."""
        ctx = Mock()
        ctx.info = AsyncMock()
        logs_client = Mock()
        mock_retry.side_effect = _ce("ResourceNotFoundException")

        result = await _analyze_deployment_log_stream(
            ctx,
            logs_client,
            "/ecs/log-group",
            "lza-container-runner/accelerator/task1",
            "task1",
            {"firstEventTimestamp": 1000, "lastEventTimestamp": 2000},
        )

        assert result is None

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_empty_events_returns_none(self, mock_retry):
        """Test empty events returns None."""
        ctx = Mock()
        ctx.info = AsyncMock()
        logs_client = Mock()
        mock_retry.return_value = {"events": [], "nextForwardToken": None}

        result = await _analyze_deployment_log_stream(
            ctx,
            logs_client,
            "/ecs/log-group",
            "lza-container-runner/accelerator/task1",
            "task1",
            {"firstEventTimestamp": 1000, "lastEventTimestamp": 2000},
        )

        assert result is None

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_successful_analysis_with_error(self, mock_retry):
        """Test successful analysis extracting error from logs."""
        ctx = Mock()
        ctx.info = AsyncMock()
        logs_client = Mock()
        mock_retry.return_value = {
            "events": [
                {"message": "Starting deployment"},
                {"message": "Error: Stack creation failed"},
                {"message": "DEPLOYMENT FAILED"},
            ],
            "nextForwardToken": None,
        }

        result = await _analyze_deployment_log_stream(
            ctx,
            logs_client,
            "/ecs/log-group",
            "lza-container-runner/accelerator/task1",
            "task1",
            {"firstEventTimestamp": 1000, "lastEventTimestamp": 2000},
        )

        assert result is not None
        assert result["task_id"] == "task1"
        assert result["deployment_status"] == "FAILED"
        assert result["specific_error"] is not None
        assert result["total_log_events"] == 3

    @pytest.mark.asyncio
    @patch(_RETRY)
    async def test_non_resource_error_raises(self, mock_retry):
        """Test non-ResourceNotFoundException ClientError is re-raised."""
        ctx = Mock()
        ctx.info = AsyncMock()
        logs_client = Mock()
        mock_retry.side_effect = _ce("AccessDeniedException")

        with pytest.raises(ClientError):
            await _analyze_deployment_log_stream(
                ctx,
                logs_client,
                "/ecs/log-group",
                "lza-container-runner/accelerator/task1",
                "task1",
                {"firstEventTimestamp": 1000, "lastEventTimestamp": 2000},
            )


class TestFindFailuresInStage:
    """Test _find_failures_in_stage helper."""

    @pytest.mark.asyncio
    async def test_stage_without_action_states(self):
        """Test stage with no actionStates key — returns early."""
        failed_actions = []
        stage_state = {"stageName": "Build"}

        await _find_failures_in_stage("exec-123", failed_actions, stage_state)

        assert len(failed_actions) == 0

    @pytest.mark.asyncio
    async def test_action_without_latest_execution(self):
        """Test action with no latestExecution — skipped."""
        failed_actions = []
        stage_state = {
            "stageName": "Build",
            "actionStates": [
                {"actionName": "BuildAction", "actionTypeId": {"provider": "CodeBuild"}}
            ],
        }

        await _find_failures_in_stage("exec-123", failed_actions, stage_state)

        assert len(failed_actions) == 0

    @pytest.mark.asyncio
    async def test_action_not_failed_skipped(self):
        """Test action with non-FAILED status — skipped."""
        failed_actions = []
        stage_state = {
            "stageName": "Build",
            "latestExecution": {"pipelineExecutionId": "exec-123"},
            "actionStates": [
                {
                    "actionName": "BuildAction",
                    "actionTypeId": {"provider": "CodeBuild"},
                    "latestExecution": {"status": "Succeeded"},
                }
            ],
        }

        await _find_failures_in_stage("exec-123", failed_actions, stage_state)

        assert len(failed_actions) == 0
