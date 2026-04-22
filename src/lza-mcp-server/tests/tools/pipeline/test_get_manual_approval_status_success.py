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

"""Unit tests for getManualApprovalStatus success scenarios."""

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


class TestPendingApprovalAllFields:
    """Test pending approval found with all fields populated."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CP)
    @patch(_RETRY)
    async def test_pending_approval_all_fields(self, mock_retry, mock_cp, mock_s3_diff):
        """Test: pending approval found with all fields populated."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        mock_retry.return_value = {
            "stageStates": [
                {
                    "stageName": "Review",
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "ManualApproval",
                            "latestExecution": {
                                "status": "InProgress",
                                "token": "approval-token-123",
                                "pipelineExecutionId": "exec-abc-123",
                                "summary": "CDK diff summary data",
                            },
                            "entityUrl": "https://console.aws.amazon.com/review",
                        }
                    ],
                }
            ]
        }

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["pipeline_name"] == "AWSAccelerator-Pipeline"
        assert result["stage_name"] == "Review"
        assert result["action_name"] == "ManualApproval"
        assert result["pipeline_execution_id"] == "exec-abc-123"
        assert result["token"] == "approval-token-123"
        assert result["custom_data"] == "CDK diff summary data"
        assert result["external_entity_url"] == "https://console.aws.amazon.com/review"
        assert "Manual approval is pending" in result["message"]


class TestPendingApprovalOptionalFieldsMissing:
    """Test pending approval found with optional fields missing."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CP)
    @patch(_RETRY)
    async def test_pending_approval_no_optional_fields(
        self, mock_retry, mock_cp, mock_s3_diff
    ):
        """Test: pending approval found with no custom data and no external URL."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        mock_retry.return_value = {
            "stageStates": [
                {
                    "stageName": "Review",
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "ManualApproval",
                            "latestExecution": {
                                "status": "InProgress",
                                "token": "token-456",
                                "pipelineExecutionId": "exec-def-456",
                            },
                        }
                    ],
                }
            ]
        }

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["token"] == "token-456"
        assert result["pipeline_execution_id"] == "exec-def-456"
        # Optional fields should not be present
        assert "custom_data" not in result
        assert "external_entity_url" not in result


class TestNoApprovalPipelineSucceeded:
    """Test no pending approval — pipeline succeeded."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CP)
    @patch(_RETRY)
    async def test_no_approval_pipeline_succeeded(
        self, mock_retry, mock_cp, mock_s3_diff
    ):
        """Test: no pending approval — all stages Succeeded."""
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
                },
                {
                    "stageName": "Build",
                    "latestExecution": {"status": "Succeeded"},
                    "actionStates": [
                        {
                            "actionName": "Build",
                            "latestExecution": {"status": "Succeeded"},
                        }
                    ],
                },
            ]
        }

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is False
        assert result["pipeline_status"] == "Succeeded"
        assert "No manual approval is currently pending" in result["message"]


class TestNoApprovalPipelineInProgress:
    """Test no pending approval — pipeline in progress (non-approval stage)."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CP)
    @patch(_RETRY)
    async def test_no_approval_pipeline_in_progress(
        self, mock_retry, mock_cp, mock_s3_diff
    ):
        """Test: non-approval stage InProgress, no token present."""
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
                },
                {
                    "stageName": "Build",
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "CodeBuild",
                            "latestExecution": {
                                "status": "InProgress",
                                # No token — this is not an approval action
                            },
                        }
                    ],
                },
            ]
        }

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is False
        assert result["pipeline_status"] == "InProgress"
        assert "No manual approval is currently pending" in result["message"]
