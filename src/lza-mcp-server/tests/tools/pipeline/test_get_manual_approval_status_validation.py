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

"""Unit tests for getManualApprovalStatus input validation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    tool_get_manual_approval_status,
)

_CP = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_codepipeline_client"
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.retry_with_exponential_backoff"
_S3_DIFF = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.is_s3_diff_enabled"


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestInvalidPipelineName:
    """Test invalid pipeline name validation."""

    @pytest.mark.asyncio
    async def test_empty_pipeline_name(self):
        """Test: empty string pipeline name returns validation error."""
        ctx = _make_ctx()
        result = await tool_get_manual_approval_status(ctx, pipeline_name="")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_pipeline_name_too_long(self):
        """Test: pipeline name >100 chars returns validation error."""
        ctx = _make_ctx()
        long_name = "a" * 101
        result = await tool_get_manual_approval_status(ctx, pipeline_name=long_name)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_pipeline_name_with_spaces(self):
        """Test: pipeline name with spaces returns validation error."""
        ctx = _make_ctx()
        result = await tool_get_manual_approval_status(ctx, pipeline_name="my pipeline")

        assert result["success"] is False


class TestInvalidQualifier:
    """Test invalid qualifier validation."""

    @pytest.mark.asyncio
    async def test_empty_qualifier(self):
        """Test: empty string qualifier returns validation error."""
        ctx = _make_ctx()
        result = await tool_get_manual_approval_status(ctx, qualifier="")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_qualifier_too_long(self):
        """Test: qualifier >100 chars returns validation error."""
        ctx = _make_ctx()
        long_qualifier = "a" * 101
        result = await tool_get_manual_approval_status(ctx, qualifier=long_qualifier)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_qualifier_with_spaces(self):
        """Test: qualifier with spaces returns validation error."""
        ctx = _make_ctx()
        result = await tool_get_manual_approval_status(ctx, qualifier="my qualifier")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_qualifier_with_special_chars(self):
        """Test: qualifier with special chars returns validation error."""
        ctx = _make_ctx()
        result = await tool_get_manual_approval_status(ctx, qualifier="qual!@#$")

        assert result["success"] is False


class TestQualifierResolution:
    """Test qualifier resolves pipeline name to {qualifier}-pipeline."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CP)
    @patch(_RETRY)
    async def test_qualifier_resolves_pipeline_name(
        self, mock_retry, mock_cp, mock_s3_diff
    ):
        """Test: qualifier resolves pipeline name to {qualifier}-pipeline."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        mock_retry.return_value = {
            "stageStates": [
                {
                    "stageName": "Source",
                    "latestExecution": {"status": "Succeeded"},
                    "actionStates": [
                        {
                            "actionName": "Source",
                            "latestExecution": {"status": "Succeeded"},
                        }
                    ],
                }
            ]
        }

        result = await tool_get_manual_approval_status(ctx, qualifier="my-qual")

        assert result["success"] is True
        assert result["pipeline_name"] == "my-qual-pipeline"
        # Verify the retry was called with the resolved name
        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args
        assert call_kwargs[1]["name"] == "my-qual-pipeline"
