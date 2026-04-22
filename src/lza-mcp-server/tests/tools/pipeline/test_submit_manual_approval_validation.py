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

"""Unit tests for submit_manual_approval input validation."""

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


class TestSubmitManualApprovalActionValidation:
    """Test action parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_action_value(self):
        """Test invalid action value (not Approve/Reject) — error listing valid values."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="maybe",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "Invalid action" in result["error"]
        assert "Approve" in result["message"] or "Reject" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_action(self):
        """Test empty action — error."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "action" in result["error"].lower()


class TestSubmitManualApprovalRequiredParamValidation:
    """Test required parameter validation (token, stage_name, action_name)."""

    @pytest.mark.asyncio
    async def test_empty_token(self):
        """Test empty token — rejected."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result["success"] is False
        assert "token" in result["error"].lower()

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_whitespace_only_stage_name(self, mock_retry, mock_get_client):
        """Test whitespace-only stage_name — passes validation but API rejects it.

        Note: validate_string_input does not strip whitespace, so "   " passes
        the min_length check. The whitespace value reaches the API call.
        """
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="   ",
            action_name="ManualApproval",
        )

        # The whitespace-only stage_name passes validation and reaches the API
        # Verify the call was made with the whitespace value
        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args
        assert call_kwargs.kwargs["stageName"] == "   "

    @pytest.mark.asyncio
    async def test_empty_action_name(self):
        """Test empty action_name — rejected."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="",
        )

        assert result["success"] is False
        assert "action_name" in result["error"].lower()


class TestSubmitManualApprovalPipelineValidation:
    """Test pipeline name and qualifier validation."""

    @pytest.mark.asyncio
    async def test_invalid_pipeline_name_with_spaces(self):
        """Test invalid pipeline name (spaces) — rejected with validation errors."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            pipeline_name="My Pipeline",
        )

        assert result["success"] is False
        assert (
            "pipeline" in result["error"].lower()
            or "pipeline" in result["message"].lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_qualifier_special_chars(self):
        """Test invalid qualifier (special chars) — rejected with validation errors."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            qualifier="bad qualifier!",
        )

        assert result["success"] is False
        assert "qualifier" in result["error"].lower()

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_qualifier_resolves_pipeline_name(self, mock_retry, mock_get_client):
        """Test qualifier resolves pipeline name to {qualifier}-pipeline."""
        ctx = _make_ctx()
        mock_get_client.return_value = Mock()
        mock_retry.return_value = {}

        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            qualifier="my-qual",
        )

        assert result["success"] is True
        assert result["pipeline_name"] == "my-qual-pipeline"

        # Verify the retry call used the resolved pipeline name
        call_kwargs = mock_retry.call_args
        assert call_kwargs.kwargs["pipelineName"] == "my-qual-pipeline"

    @pytest.mark.asyncio
    async def test_empty_qualifier_rejected(self):
        """Test empty qualifier — rejected by validate_string_input."""
        ctx = _make_ctx()
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            qualifier="",
        )

        assert result["success"] is False
        assert "qualifier" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_name_too_long(self):
        """Test pipeline name exceeding max length — rejected."""
        ctx = _make_ctx()
        long_name = "a" * 101
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            pipeline_name=long_name,
        )

        assert result["success"] is False
        assert "pipeline" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_summary_too_long_rejected(self):
        """Test summary exceeding 2048 characters — rejected."""
        ctx = _make_ctx()
        long_summary = "x" * 2049
        result = await tool_submit_manual_approval(
            ctx,
            action="Approve",
            token="tok",
            stage_name="Review",
            action_name="ManualApproval",
            summary=long_summary,
        )

        assert result["success"] is False
        assert "summary" in result["error"].lower()
