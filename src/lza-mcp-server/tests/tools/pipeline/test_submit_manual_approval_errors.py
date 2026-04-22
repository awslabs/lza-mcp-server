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

"""Unit tests for submit_manual_approval error handling."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from botocore.exceptions import ClientError, NoCredentialsError

from awslabs.lza_mcp_server.tools.pipeline.submit_manual_approval import (
    tool_submit_manual_approval,
)

_CP = "awslabs.lza_mcp_server.tools.pipeline.submit_manual_approval.get_codepipeline_client"
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.submit_manual_approval.retry_with_exponential_backoff"


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _ce(code, msg="err"):
    """Create a ClientError with the given error code."""
    return ClientError({"Error": {"Code": code, "Message": msg}}, "PutApprovalResult")


class TestSubmitManualApprovalInvalidToken:
    """Test InvalidApprovalTokenException handling."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_invalid_approval_token(self, mock_retry, mock_get_client):
        """Test InvalidApprovalTokenException — error advising re-check via getDeploymentStatus."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.side_effect = _ce(
            "InvalidApprovalTokenException",
            "The approval token has expired",
        )

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="expired-token",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert result["error_code"] == "InvalidApprovalTokenException"
        assert "token" in result["message"].lower()
        assert any(
            "getDeploymentStatus" in step or "fresh" in step.lower()
            for step in result["troubleshooting"]
        )


class TestSubmitManualApprovalAWSErrors:
    """Test AWS error handling — errors logged but not echoed to LLM."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_pipeline_not_found(self, mock_retry, mock_get_client):
        """Test PipelineNotFoundException — generic error with troubleshooting guidance."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.side_effect = _ce("PipelineNotFoundException", "Pipeline not found")

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "troubleshooting" in result
        assert "PipelineNotFoundException" not in result.get("error", "")

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_access_denied(self, mock_retry, mock_get_client):
        """Test AccessDenied — generic error without echoing error code."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.side_effect = _ce(
            "AccessDenied",
            "User is not authorized to perform codepipeline:PutApprovalResult",
        )

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "troubleshooting" in result
        assert "AccessDenied" not in result.get("error", "")

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_throttling_error(self, mock_retry, mock_get_client):
        """Test throttling error — generic error without echoing error code."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.side_effect = _ce("ThrottlingException", "Rate exceeded")

        result = await tool_submit_manual_approval(
            ctx,
            action="Reject",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "troubleshooting" in result
        assert "ThrottlingException" not in result.get("error", "")

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_no_credentials_error(self, mock_retry, mock_get_client):
        """Test NoCredentialsError — generic error without echoing details."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.side_effect = NoCredentialsError()

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "troubleshooting" in result
