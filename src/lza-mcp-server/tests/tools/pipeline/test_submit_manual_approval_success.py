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

"""Unit tests for submit_manual_approval success scenarios."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

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


class TestSubmitManualApprovalApproveSuccess:
    """Test successful approve scenarios."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_approve_with_required_params(self, mock_retry, mock_get_client):
        """Test approve with all required params — success response with confirmation."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="test-token-123",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Approved"
        assert result["pipeline_name"] == "AWSAccelerator-Pipeline"
        assert result["stage_name"] == "Review"
        assert result["action_name"] == "ManualApproval"
        assert "successfully" in result["message"]

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_approve_with_summary_comment(self, mock_retry, mock_get_client):
        """Test approve with optional summary comment — comment included in API call."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="test-token-123",
            stage_name="Review",
            action_name="ManualApproval",
            summary="Looks good, approved via MCP",
        )

        assert result["success"] is True
        assert result["action"] == "Approved"

        # Verify the retry function was called with summary in result
        call_kwargs = mock_retry.call_args
        put_params = (
            {k: v for k, v in call_kwargs.kwargs.items()} if call_kwargs.kwargs else {}
        )
        # The call is: retry(func, **put_params)
        assert put_params["result"]["summary"] == "Looks good, approved via MCP"
        assert put_params["result"]["status"] == "Approved"


class TestSubmitManualApprovalRejectSuccess:
    """Test successful reject scenarios."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_reject_with_required_params(self, mock_retry, mock_get_client):
        """Test reject with all required params — success response with confirmation."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Reject",
            token="test-token-456",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Rejected"
        assert result["pipeline_name"] == "AWSAccelerator-Pipeline"
        assert result["stage_name"] == "Review"
        assert result["action_name"] == "ManualApproval"
        assert "successfully" in result["message"]

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_reject_with_summary_comment(self, mock_retry, mock_get_client):
        """Test reject with optional summary comment — comment included in API call."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Reject",
            token="test-token-456",
            stage_name="Review",
            action_name="ManualApproval",
            summary="Changes look risky, rejecting",
        )

        assert result["success"] is True
        assert result["action"] == "Rejected"

        # Verify the retry function was called with summary in result
        call_kwargs = mock_retry.call_args
        put_params = (
            {k: v for k, v in call_kwargs.kwargs.items()} if call_kwargs.kwargs else {}
        )
        assert put_params["result"]["summary"] == "Changes look risky, rejecting"
        assert put_params["result"]["status"] == "Rejected"


class TestSubmitManualApprovalCaseInsensitive:
    """Test case-insensitive action handling."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_lowercase_approve(self, mock_retry, mock_get_client):
        """Test 'approve' (lowercase) normalizes to 'Approved'."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Approved"

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_uppercase_approve(self, mock_retry, mock_get_client):
        """Test 'APPROVE' (uppercase) normalizes to 'Approved'."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="APPROVE",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Approved"

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_mixed_case_approve(self, mock_retry, mock_get_client):
        """Test 'Approve' (mixed case) normalizes to 'Approved'."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Approved"

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_mixed_case_reject(self, mock_retry, mock_get_client):
        """Test 'REJECT' (uppercase) normalizes to 'Rejected'."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="REJECT",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is True
        assert result["action"] == "Rejected"

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_retry_called_with_correct_kwargs(self, mock_retry, mock_get_client):
        """Verify retry_with_exponential_backoff is called with correct kwargs."""
        ctx = _make_ctx()
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_retry.return_value = {}

        await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="my-token",
            stage_name="Review",
            action_name="ManualApproval",
            pipeline_name="AWSAccelerator-Pipeline",
        )

        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        # First positional arg is the function
        assert call_args.args[0] == mock_client.put_approval_result
        # Keyword args contain the put_approval_result params
        assert call_args.kwargs["pipelineName"] == "AWSAccelerator-Pipeline"
        assert call_args.kwargs["stageName"] == "Review"
        assert call_args.kwargs["actionName"] == "ManualApproval"
        assert call_args.kwargs["token"] == "my-token"
        assert call_args.kwargs["result"]["status"] == "Approved"
