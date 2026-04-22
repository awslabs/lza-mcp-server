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

"""Unit tests for getManualApprovalStatus error handling."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from botocore.exceptions import ClientError, NoCredentialsError

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    tool_get_manual_approval_status,
)

_CP = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_codepipeline_client"
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.retry_with_exponential_backoff"


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _ce(code, msg="err"):
    """Create a ClientError with the given code and message."""
    return ClientError({"Error": {"Code": code, "Message": msg}}, "op")


class TestPipelineNotFoundError:
    """Test PipelineNotFoundException returns error with troubleshooting guidance."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_pipeline_not_found(self, mock_retry, mock_cp):
        """Test: PipelineNotFoundException returns error with troubleshooting."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_retry.side_effect = _ce("PipelineNotFoundException", "Pipeline not found")

        result = await tool_get_manual_approval_status(
            ctx, pipeline_name="NonExistent-Pipeline"
        )

        assert result["success"] is False
        assert result["error_code"] == "PipelineNotFoundException"
        assert "troubleshooting" in result
        assert any("pipeline" in s.lower() for s in result["troubleshooting"])


class TestAccessDeniedError:
    """Test AccessDenied returns error identifying missing permission."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_access_denied(self, mock_retry, mock_cp):
        """Test: AccessDenied identifies missing codepipeline:GetPipelineState permission."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_retry.side_effect = _ce("AccessDenied", "Access denied")

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is False
        assert result["error_code"] == "AccessDenied"
        assert "troubleshooting" in result


class TestThrottlingError:
    """Test throttling error returns error with retry guidance."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_throttling_error(self, mock_retry, mock_cp):
        """Test: ThrottlingException returns error with retry guidance."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_retry.side_effect = _ce("ThrottlingException", "Rate exceeded")

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is False
        assert result["error_code"] == "ThrottlingException"
        assert "troubleshooting" in result
        assert any(
            "retry" in s.lower() or "wait" in s.lower()
            for s in result["troubleshooting"]
        )


class TestNoCredentialsError:
    """Test NoCredentialsError returns error with credential guidance."""

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_no_credentials(self, mock_retry, mock_cp):
        """Test: NoCredentialsError returns error with credential guidance."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_retry.side_effect = NoCredentialsError()

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is False
        assert "troubleshooting" in result
        assert any("credential" in s.lower() for s in result["troubleshooting"])
