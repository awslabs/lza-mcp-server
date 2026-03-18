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

"""Unit tests for get_deployment_status qualifier (Branch B) scenarios."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    tool_get_deployment_status,
)

QUALIFIER = "container-dev-1"
QUALIFIER_PIPELINE = f"{QUALIFIER}-pipeline"
LOG_GROUP = f"/ecs/{QUALIFIER}-lza-deployment"
TASK_ID = "abc123def456"
STREAM_PREFIX = "ecs/lza-deployment-container/"
STREAM_NAME = f"{STREAM_PREFIX}{TASK_ID}"

# Patch targets — lazy imports resolve at their source modules
_PATCH_PIPELINE = "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status._get_standard_pipeline_status"
_PATCH_LOGS_CLIENT = "awslabs.lza_mcp_server.aws_access.get_logs_client"
_PATCH_FIND_STREAM = "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._find_most_recent_deployment_stream"
_PATCH_FIND_STREAM_BY_TASK = "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._find_deployment_stream_by_task_id"
_PATCH_ANALYZE = "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._analyze_deployment_log_stream"
_PATCH_ECS_TASK_STATUS = (
    "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status._check_ecs_task_status"
)


@pytest.fixture
def mock_mcp_context():
    """Create a mock MCP context for testing."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _pipeline_not_found_result():
    """Return a result dict simulating PipelineNotFoundException."""
    return {
        "success": False,
        "error_code": "PipelineNotFoundException",
        "error": f"Pipeline '{QUALIFIER_PIPELINE}' not found",
        "message": f"The specified pipeline '{QUALIFIER_PIPELINE}' does not exist",
    }


class TestQualifierValidation:
    """Test qualifier input validation."""

    @pytest.mark.asyncio
    async def test_invalid_qualifier_empty(self, mock_mcp_context):
        """Test with empty qualifier string."""
        result = await tool_get_deployment_status(mock_mcp_context, qualifier="")
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_qualifier_too_long(self, mock_mcp_context):
        """Test with qualifier exceeding max length."""
        result = await tool_get_deployment_status(mock_mcp_context, qualifier="a" * 101)
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_qualifier_special_chars(self, mock_mcp_context):
        """Test with qualifier containing invalid characters."""
        result = await tool_get_deployment_status(
            mock_mcp_context, qualifier="bad qualifier!"
        )
        assert result["success"] is False
        assert "Invalid qualifier" in result["error"]


class TestQualifierBothSourcesFound:
    """Test qualifier path when both CodePipeline and ECS container are found."""

    @pytest.mark.asyncio
    async def test_both_pipeline_and_container(self, mock_mcp_context):
        """Test when both CodePipeline and ECS container logs exist."""
        pipeline_result = {
            "success": True,
            "status": "SUCCEEDED",
            "pipeline_name": QUALIFIER_PIPELINE,
        }

        mock_detail = {
            "task_id": TASK_ID,
            "log_stream": STREAM_NAME,
            "deployment_status": "COMPLETE",
            "phase_reached": "Phase 3: complete",
            "specific_error": None,
            "first_event_time": 1000,
            "last_event_time": 2000,
            "total_log_events": 500,
            "logs": "some logs",
        }

        mock_stream = {
            "logStreamName": STREAM_NAME,
            "firstEventTimestamp": 1000,
            "lastEventTimestamp": 2000,
        }

        with (
            patch(
                _PATCH_PIPELINE, new_callable=AsyncMock, return_value=pipeline_result
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(_PATCH_FIND_STREAM, new_callable=AsyncMock, return_value=mock_stream),
            patch(_PATCH_ANALYZE, new_callable=AsyncMock, return_value=mock_detail),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["deployment_type"] == "external_pipeline"
            assert result["qualifier"] == QUALIFIER
            assert "CodePipeline" in result["sources_checked"]
            assert "ECS container" in result["sources_checked"]
            assert result["pipeline_status"] is not None
            assert result["container_status"] is not None
            assert result["container_status"]["task_id"] == TASK_ID
            assert result["container_status"]["deployment_status"] == "COMPLETE"
            assert result["container_status"]["has_errors"] is False


class TestQualifierPipelineOnly:
    """Test qualifier path when only CodePipeline exists."""

    @pytest.mark.asyncio
    async def test_pipeline_found_no_ecs(self, mock_mcp_context):
        """Test when CodePipeline exists but ECS log group does not."""
        pipeline_result = {
            "success": True,
            "status": "INPROGRESS",
            "pipeline_name": QUALIFIER_PIPELINE,
        }

        log_group_error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DescribeLogStreams",
        )

        with (
            patch(
                _PATCH_PIPELINE, new_callable=AsyncMock, return_value=pipeline_result
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM, new_callable=AsyncMock, side_effect=log_group_error
            ),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["sources_checked"] == ["CodePipeline"]
            assert result["pipeline_status"] is not None
            assert "container_status" not in result


class TestQualifierEcsOnly:
    """Test qualifier path when only ECS container logs exist."""

    @pytest.mark.asyncio
    async def test_ecs_found_no_pipeline(self, mock_mcp_context):
        """Test when ECS log group exists but CodePipeline does not."""
        mock_detail = {
            "task_id": TASK_ID,
            "log_stream": STREAM_NAME,
            "deployment_status": "FAILED",
            "phase_reached": "Phase 2: deploying",
            "specific_error": "CREATE_FAILED: some resource",
            "first_event_time": 1000,
            "last_event_time": 2000,
            "total_log_events": 300,
            "logs": "some logs",
        }

        mock_stream = {
            "logStreamName": STREAM_NAME,
            "firstEventTimestamp": 1000,
            "lastEventTimestamp": 2000,
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(_PATCH_FIND_STREAM, new_callable=AsyncMock, return_value=mock_stream),
            patch(_PATCH_ANALYZE, new_callable=AsyncMock, return_value=mock_detail),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["sources_checked"] == ["ECS container"]
            assert "pipeline_status" not in result
            assert result["container_status"] is not None
            assert result["container_status"]["deployment_status"] == "FAILED"
            assert result["container_status"]["has_errors"] is True
            assert "CREATE_FAILED" in result["container_status"]["specific_error"]


class TestQualifierNoSourcesFound:
    """Test qualifier path when neither CodePipeline nor ECS logs exist."""

    @pytest.mark.asyncio
    async def test_no_infrastructure_found(self, mock_mcp_context):
        """Test when neither CodePipeline nor ECS log group exist."""
        log_group_error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DescribeLogStreams",
        )

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM, new_callable=AsyncMock, side_effect=log_group_error
            ),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is False
            assert "No deployment infrastructure found" in result["error"]
            assert "troubleshooting" in result


class TestQualifierEdgeCases:
    """Test edge cases in qualifier path."""

    @pytest.mark.asyncio
    async def test_ecs_no_deployment_streams(self, mock_mcp_context):
        """Test when ECS log group exists but has no deployment streams."""
        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(_PATCH_FIND_STREAM, new_callable=AsyncMock, return_value=None),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            # No streams found means no container_status, and pipeline was not found
            assert result["success"] is False
            assert "No deployment infrastructure found" in result["error"]

    @pytest.mark.asyncio
    async def test_ecs_analyze_returns_none(self, mock_mcp_context):
        """Test when ECS stream exists but analysis returns None."""
        mock_stream = {
            "logStreamName": STREAM_NAME,
            "firstEventTimestamp": 1000,
            "lastEventTimestamp": 2000,
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(_PATCH_FIND_STREAM, new_callable=AsyncMock, return_value=mock_stream),
            patch(_PATCH_ANALYZE, new_callable=AsyncMock, return_value=None),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            # Analysis returned None, so no container_status
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_pipeline_check_raises_exception(self, mock_mcp_context):
        """Test when CodePipeline check raises an unexpected exception."""
        log_group_error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DescribeLogStreams",
        )

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                side_effect=RuntimeError("Unexpected error"),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM, new_callable=AsyncMock, side_effect=log_group_error
            ),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            # Pipeline raised exception (caught), ECS not found — no sources
            assert result["success"] is False
            assert "No deployment infrastructure found" in result["error"]

    @pytest.mark.asyncio
    async def test_ecs_non_resource_not_found_error(self, mock_mcp_context):
        """Test when ECS check raises a non-ResourceNotFoundException ClientError."""
        access_denied = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "DescribeLogStreams",
        )

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM, new_callable=AsyncMock, side_effect=access_denied
            ),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            # Non-ResourceNotFoundException is logged as warning, no container_status
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ecs_generic_exception(self, mock_mcp_context):
        """Test when ECS check raises a generic exception."""
        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM,
                new_callable=AsyncMock,
                side_effect=RuntimeError("Something broke"),
            ),
            patch(_PATCH_ECS_TASK_STATUS, new_callable=AsyncMock, return_value=None),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_standard_path_adds_qualifier_hint(self, mock_mcp_context):
        """Test that standard path adds qualifier hint when pipeline not found."""
        not_found_result = {
            "success": False,
            "error_code": "PipelineNotFoundException",
            "error": "Pipeline not found",
            "message": "Pipeline does not exist",
            "troubleshooting": ["Check pipeline name"],
        }

        with patch(
            _PATCH_PIPELINE, new_callable=AsyncMock, return_value=not_found_result
        ):
            result = await tool_get_deployment_status(mock_mcp_context)

            assert result["deployment_type"] == "standard"
            assert any(
                "qualifier" in hint.lower() for hint in result["troubleshooting"]
            )


class TestQualifierEcsTaskPending:
    """Test qualifier path when ECS task is in a pending state."""

    @pytest.mark.asyncio
    async def test_task_provisioning(self, mock_mcp_context):
        """Test when ECS task is PROVISIONING — report immediately without checking logs."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "PROVISIONING",
            "created_at": "2025-01-01T00:00:00+00:00",
            "message": "ECS task is PROVISIONING — container has not started yet",
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert "ECS container" in result["sources_checked"]
            assert result["container_status"]["deployment_status"] == "PROVISIONING"
            assert result["container_status"]["total_log_events"] == 0
            assert result["container_status"]["phase_reached"] is None
            assert "PROVISIONING" in result["container_status"]["message"]

    @pytest.mark.asyncio
    async def test_task_pending(self, mock_mcp_context):
        """Test when ECS task is PENDING — report immediately without checking logs."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "PENDING",
            "created_at": "2025-01-01T00:00:00+00:00",
            "message": "ECS task is PENDING — container has not started yet",
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["container_status"]["deployment_status"] == "PENDING"
            assert result["container_status"]["has_errors"] is False

    @pytest.mark.asyncio
    async def test_task_activating(self, mock_mcp_context):
        """Test when ECS task is ACTIVATING — report immediately without checking logs."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "ACTIVATING",
            "created_at": "2025-01-01T00:00:00+00:00",
            "message": "ECS task is ACTIVATING — container has not started yet",
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["container_status"]["deployment_status"] == "ACTIVATING"


class TestQualifierEcsTaskRunningNoLogs:
    """Test qualifier path when ECS task is RUNNING but no logs exist yet."""

    @pytest.mark.asyncio
    async def test_running_no_log_stream(self, mock_mcp_context):
        """Test when ECS task is RUNNING but no log stream exists yet."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "RUNNING",
            "last_status": "RUNNING",
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM_BY_TASK, new_callable=AsyncMock, return_value=None
            ),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert "ECS container" in result["sources_checked"]
            assert result["container_status"]["deployment_status"] == "RUNNING"
            assert "no deployment logs" in result["container_status"]["message"].lower()
            assert result["container_status"]["total_log_events"] == 0

    @pytest.mark.asyncio
    async def test_running_log_stream_exists_but_analysis_returns_none(
        self, mock_mcp_context
    ):
        """Test when ECS task is RUNNING, log stream exists but analysis returns None."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "RUNNING",
            "last_status": "RUNNING",
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        mock_stream = {
            "logStreamName": STREAM_NAME,
            "firstEventTimestamp": 1000,
            "lastEventTimestamp": 2000,
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM_BY_TASK,
                new_callable=AsyncMock,
                return_value=mock_stream,
            ),
            patch(_PATCH_ANALYZE, new_callable=AsyncMock, return_value=None),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["container_status"]["deployment_status"] == "RUNNING"
            assert "no deployment logs" in result["container_status"]["message"].lower()

    @pytest.mark.asyncio
    async def test_running_with_logs_uses_log_status(self, mock_mcp_context):
        """Test when ECS task is RUNNING and logs exist — use log-based status."""
        ecs_task_info = {
            "success": True,
            "deployment_type": "ecs_container",
            "qualifier": QUALIFIER,
            "task_id": TASK_ID,
            "deployment_status": "RUNNING",
            "last_status": "RUNNING",
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        mock_detail = {
            "task_id": TASK_ID,
            "log_stream": STREAM_NAME,
            "deployment_status": "IN_PROGRESS",
            "phase_reached": "Phase 2: deploying",
            "specific_error": None,
            "first_event_time": 1000,
            "last_event_time": 2000,
            "total_log_events": 100,
            "logs": "some logs",
        }

        mock_stream = {
            "logStreamName": STREAM_NAME,
            "firstEventTimestamp": 1000,
            "lastEventTimestamp": 2000,
        }

        with (
            patch(
                _PATCH_PIPELINE,
                new_callable=AsyncMock,
                return_value=_pipeline_not_found_result(),
            ),
            patch(_PATCH_LOGS_CLIENT) as mock_logs,
            patch(
                _PATCH_FIND_STREAM_BY_TASK,
                new_callable=AsyncMock,
                return_value=mock_stream,
            ),
            patch(_PATCH_ANALYZE, new_callable=AsyncMock, return_value=mock_detail),
            patch(
                _PATCH_ECS_TASK_STATUS,
                new_callable=AsyncMock,
                return_value=ecs_task_info,
            ),
        ):
            mock_logs.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, qualifier=QUALIFIER
            )

            assert result["success"] is True
            assert result["container_status"]["deployment_status"] == "IN_PROGRESS"
            assert result["container_status"]["total_log_events"] == 100
            assert result["container_status"]["phase_reached"] == "Phase 2: deploying"
