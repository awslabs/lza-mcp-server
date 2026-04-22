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

"""Tests for the Step 6 approval detection integration in _get_standard_pipeline_status.

Exercises _get_standard_pipeline_status directly, verifying that approval
metadata always appears in the response when a pending approval exists.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    _get_standard_pipeline_status,
    _pipeline_cache,
)

_MOD = "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status"

_PIPELINE_NAME = "AWSAccelerator-Pipeline"
_EXEC_ID = "exec-001"


def _make_ctx():
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _stage_states_with_approval():
    return [
        {
            "stageName": "Source",
            "latestExecution": {"status": "Succeeded"},
            "actionStates": [
                {"actionName": "Source", "latestExecution": {"status": "Succeeded"}}
            ],
        },
        {
            "stageName": "Review",
            "latestExecution": {"status": "InProgress"},
            "actionStates": [
                {
                    "actionName": "ManualApproval",
                    "latestExecution": {
                        "status": "InProgress",
                        "token": "approval-tok-abc",
                        "pipelineExecutionId": _EXEC_ID,
                        "summary": "CDK diff summary",
                    },
                    "entityUrl": "https://console.example.com",
                }
            ],
        },
    ]


def _stage_states_no_approval():
    return [
        {
            "stageName": "Source",
            "latestExecution": {"status": "Succeeded"},
            "actionStates": [
                {"actionName": "Source", "latestExecution": {"status": "Succeeded"}}
            ],
        },
        {
            "stageName": "Build",
            "latestExecution": {"status": "Succeeded"},
            "actionStates": [
                {"actionName": "Build", "latestExecution": {"status": "Succeeded"}}
            ],
        },
    ]


def _make_mock_retry(stage_states, exec_status="InProgress"):
    """Build a mock_retry that dispatches based on the API call kwargs."""

    async def mock_retry(func, **kwargs):
        if "name" in kwargs and "pipelineName" not in kwargs:
            return {
                "pipeline": {
                    "stages": [{"name": s["stageName"]} for s in stage_states]
                },
                "stageStates": stage_states,
            }
        if (
            "pipelineName" in kwargs
            and "maxResults" in kwargs
            and "pipelineExecutionId" not in kwargs
        ):
            return {
                "pipelineExecutionSummaries": [
                    {"pipelineExecutionId": _EXEC_ID, "status": exec_status}
                ]
            }
        if "pipelineExecutionId" in kwargs:
            return {
                "pipelineExecution": {
                    "pipelineExecutionId": _EXEC_ID,
                    "status": exec_status,
                    "executionMode": "NORMAL",
                    "creationTime": datetime(2025, 1, 1, tzinfo=timezone.utc),
                }
            }
        return {"stageStates": stage_states}

    return mock_retry


class TestDeploymentStatusApprovalIntegration:
    """Test that _get_standard_pipeline_status always returns approval metadata."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _pipeline_cache.clear()

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    @patch(f"{_MOD}.get_codepipeline_client")
    async def test_approval_detected_in_response(self, mock_cp, _s3_flag, mock_review):
        mock_review.return_value = {"success": False, "warning": "no cb"}
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        with patch(
            f"{_MOD}.retry_with_exponential_backoff",
            side_effect=_make_mock_retry(_stage_states_with_approval()),
        ):
            result = await _get_standard_pipeline_status(ctx, _PIPELINE_NAME)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["approval_token"] == "approval-tok-abc"
        assert result["approval_stage_name"] == "Review"
        assert result["approval_action_name"] == "ManualApproval"
        assert "submitManualApproval" in result["message"]
        assert "llm_instructions" in result
        assert "present" in result["llm_instructions"].lower()
        assert "approve or reject" in result["llm_instructions"].lower()

    @pytest.mark.asyncio
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    @patch(f"{_MOD}.get_codepipeline_client")
    async def test_no_approval_when_none_pending(self, mock_cp, _s3_flag):
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        with patch(
            f"{_MOD}.retry_with_exponential_backoff",
            side_effect=_make_mock_retry(_stage_states_no_approval(), "Succeeded"),
        ):
            result = await _get_standard_pipeline_status(ctx, _PIPELINE_NAME)

        assert result["success"] is True
        assert "approval_pending" not in result
        assert "approval_token" not in result

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    @patch(f"{_MOD}.get_codepipeline_client")
    async def test_approval_with_review_diff(self, mock_cp, _s3_flag, mock_review):
        mock_review.return_value = {"success": True, "content": "cdk diff output"}
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        with patch(
            f"{_MOD}.retry_with_exponential_backoff",
            side_effect=_make_mock_retry(_stage_states_with_approval()),
        ):
            result = await _get_standard_pipeline_status(ctx, _PIPELINE_NAME)

        assert result["approval_pending"] is True
        assert result["review_diff"] == "cdk diff output"

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    @patch(f"{_MOD}.get_codepipeline_client")
    async def test_approval_with_qualifier(self, mock_cp, _s3_flag, mock_review):
        """Qualifier is passed through to _detect_pending_approval."""
        mock_review.return_value = {"success": False, "warning": "n/a"}
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        with patch(
            f"{_MOD}.retry_with_exponential_backoff",
            side_effect=_make_mock_retry(_stage_states_with_approval()),
        ):
            result = await _get_standard_pipeline_status(
                ctx, "myq-pipeline", qualifier="myq"
            )

        assert result["approval_pending"] is True
        assert result["approval_token"] == "approval-tok-abc"
