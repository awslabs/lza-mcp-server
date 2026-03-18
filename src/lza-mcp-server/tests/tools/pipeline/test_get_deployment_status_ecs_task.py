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

"""Unit tests for _check_ecs_task_status helper."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    _check_ecs_task_status,
)

QUALIFIER = "container-dev-1"
CLUSTER_ARN = f"arn:aws:ecs:eu-north-1:123456789012:cluster/{QUALIFIER}-ecs-cluster"
TASK_ARN = f"arn:aws:ecs:eu-north-1:123456789012:task/{QUALIFIER}-ecs-cluster/abc123"
TASK_ID = "abc123"

_PATCH_ECS_CLIENT = (
    "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_ecs_client"
)
_PATCH_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff"


@pytest.fixture
def mock_mcp_context():
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _make_ecs_client(cluster_arns=None, task_arns=None, tasks=None):
    """Build a mock ECS client with paginator support."""
    client = MagicMock()

    paginator = MagicMock()
    paginator.paginate.return_value = [{"clusterArns": cluster_arns or []}]
    client.get_paginator.return_value = paginator

    client.list_tasks.return_value = {"taskArns": task_arns or []}
    client.describe_tasks.return_value = {"tasks": tasks or []}

    return client


class TestCheckEcsTaskStatusNoCluster:
    """Test when no ECS cluster matches the qualifier."""

    @pytest.mark.asyncio
    async def test_no_cluster_found(self, mock_mcp_context):
        """Returns None when no cluster matches the qualifier."""
        client = _make_ecs_client(cluster_arns=[])

        with patch(_PATCH_ECS_CLIENT, return_value=client):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is None

    @pytest.mark.asyncio
    async def test_cluster_not_found_error(self, mock_mcp_context):
        """Returns None on ClusterNotFoundException."""
        client = MagicMock()
        client.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "ClusterNotFoundException", "Message": "Not found"}},
            "ListClusters",
        )

        with patch(_PATCH_ECS_CLIENT, return_value=client):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_mcp_context):
        """Returns None on unexpected exceptions."""
        client = MagicMock()
        client.get_paginator.side_effect = RuntimeError("boom")

        with patch(_PATCH_ECS_CLIENT, return_value=client):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is None


class TestCheckEcsTaskStatusNoTasks:
    """Test when cluster exists but no tasks are running."""

    @pytest.mark.asyncio
    async def test_no_running_tasks(self, mock_mcp_context):
        """Returns None when list_tasks returns empty."""
        client = _make_ecs_client(cluster_arns=[CLUSTER_ARN], task_arns=[])

        async def mock_retry(func, **kwargs):
            return func(**kwargs)

        with (
            patch(_PATCH_ECS_CLIENT, return_value=client),
            patch(_PATCH_RETRY, side_effect=mock_retry),
        ):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is None


class TestCheckEcsTaskStatusPending:
    """Test when ECS task is in a pending-like state."""

    @pytest.mark.asyncio
    async def test_task_provisioning(self, mock_mcp_context):
        """Returns pending status when task lastStatus is PROVISIONING."""
        created = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tasks = [
            {
                "taskArn": TASK_ARN,
                "lastStatus": "PROVISIONING",
                "createdAt": created,
            }
        ]
        client = _make_ecs_client(
            cluster_arns=[CLUSTER_ARN],
            task_arns=[TASK_ARN],
            tasks=tasks,
        )

        async def mock_retry(func, **kwargs):
            return func(**kwargs)

        with (
            patch(_PATCH_ECS_CLIENT, return_value=client),
            patch(_PATCH_RETRY, side_effect=mock_retry),
        ):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is not None
        assert result["deployment_status"] == "PROVISIONING"
        assert result["task_id"] == TASK_ID
        assert result["has_errors"] is False
        assert "PROVISIONING" in result["message"]

    @pytest.mark.asyncio
    async def test_task_pending(self, mock_mcp_context):
        """Returns pending status when task lastStatus is PENDING."""
        tasks = [
            {
                "taskArn": TASK_ARN,
                "lastStatus": "PENDING",
                "createdAt": datetime(2025, 1, 1, tzinfo=timezone.utc),
            }
        ]
        client = _make_ecs_client(
            cluster_arns=[CLUSTER_ARN],
            task_arns=[TASK_ARN],
            tasks=tasks,
        )

        async def mock_retry(func, **kwargs):
            return func(**kwargs)

        with (
            patch(_PATCH_ECS_CLIENT, return_value=client),
            patch(_PATCH_RETRY, side_effect=mock_retry),
        ):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result["deployment_status"] == "PENDING"


class TestCheckEcsTaskStatusRunning:
    """Test when ECS task is RUNNING."""

    @pytest.mark.asyncio
    async def test_task_running(self, mock_mcp_context):
        """Returns RUNNING status for caller to check logs."""
        created = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tasks = [
            {
                "taskArn": TASK_ARN,
                "lastStatus": "RUNNING",
                "createdAt": created,
            }
        ]
        client = _make_ecs_client(
            cluster_arns=[CLUSTER_ARN],
            task_arns=[TASK_ARN],
            tasks=tasks,
        )

        async def mock_retry(func, **kwargs):
            return func(**kwargs)

        with (
            patch(_PATCH_ECS_CLIENT, return_value=client),
            patch(_PATCH_RETRY, side_effect=mock_retry),
        ):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result is not None
        assert result["deployment_status"] == "RUNNING"
        assert result["task_id"] == TASK_ID

    @pytest.mark.asyncio
    async def test_multiple_tasks_uses_most_recent(self, mock_mcp_context):
        """When multiple tasks exist, uses the most recently created one."""
        older = datetime(2025, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2025, 1, 2, tzinfo=timezone.utc)
        older_arn = (
            f"arn:aws:ecs:eu-north-1:123456789012:task/{QUALIFIER}-ecs-cluster/old111"
        )
        newer_arn = (
            f"arn:aws:ecs:eu-north-1:123456789012:task/{QUALIFIER}-ecs-cluster/new222"
        )

        tasks = [
            {"taskArn": older_arn, "lastStatus": "RUNNING", "createdAt": older},
            {"taskArn": newer_arn, "lastStatus": "PROVISIONING", "createdAt": newer},
        ]
        client = _make_ecs_client(
            cluster_arns=[CLUSTER_ARN],
            task_arns=[older_arn, newer_arn],
            tasks=tasks,
        )

        async def mock_retry(func, **kwargs):
            return func(**kwargs)

        with (
            patch(_PATCH_ECS_CLIENT, return_value=client),
            patch(_PATCH_RETRY, side_effect=mock_retry),
        ):
            result = await _check_ecs_task_status(mock_mcp_context, QUALIFIER)

        assert result["task_id"] == "new222"
        assert result["deployment_status"] == "PROVISIONING"
