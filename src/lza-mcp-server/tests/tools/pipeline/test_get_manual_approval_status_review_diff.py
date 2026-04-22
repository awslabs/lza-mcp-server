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

"""Unit tests for Review stage diff retrieval (_retrieve_review_stage_diff)
and its integration with tool_get_manual_approval_status."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    _retrieve_review_stage_diff,
    tool_get_manual_approval_status,
)

_CB = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_codebuild_client"
_LOGS = (
    "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_logs_client"
)
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.retry_with_exponential_backoff"
_CP = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_codepipeline_client"
_S3_DIFF = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.is_s3_diff_enabled"


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Helpers for building pipeline stage states
# ---------------------------------------------------------------------------


def _stage_with_codebuild_and_approval(
    stage_name="Review",
    build_id="build-id-123",
    approval_token="approval-token",
    exec_id="exec-123",
):
    """Build a stage state with a CodeBuild action and an approval action."""
    return {
        "stageName": stage_name,
        "latestExecution": {"status": "InProgress"},
        "actionStates": [
            {
                "actionName": "ReviewCommit",
                "latestExecution": {
                    "status": "Succeeded",
                    "externalExecutionId": build_id,
                },
            },
            {
                "actionName": "ManualApproval",
                "latestExecution": {
                    "status": "InProgress",
                    "token": approval_token,
                    "pipelineExecutionId": exec_id,
                },
            },
        ],
    }


def _build_response(group="/log-group", stream="log-stream"):
    """Build a CodeBuild batch_get_builds response with log info."""
    return {
        "builds": [
            {
                "id": "build-id-123",
                "logs": {
                    "groupName": group,
                    "streamName": stream,
                },
            }
        ]
    }


def _log_events(messages):
    """Build a CloudWatch get_log_events response."""
    return {"events": [{"message": m} for m in messages]}


# ===========================================================================
# Task 12.3 — Unit tests for _retrieve_review_stage_diff() directly
# ===========================================================================


class TestReviewDiffCodeBuildSameStage:
    """CodeBuild action found in same stage as approval, logs retrieved."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_same_stage_success(self, mock_cb, mock_logs, mock_retry):
        stage_states = [_stage_with_codebuild_and_approval()]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        # retry calls: batch_get_builds, then get_log_events
        mock_retry.side_effect = [
            _build_response(),
            _log_events(["line1", "line2", "line3"]),
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is True
        assert "line1" in result["content"]
        assert "line2" in result["content"]
        assert "line3" in result["content"]


class TestReviewDiffCodeBuildPrecedingStage:
    """CodeBuild action found in a preceding stage, logs retrieved."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_preceding_stage_success(self, mock_cb, mock_logs, mock_retry):
        stage_states = [
            {
                "stageName": "Build",
                "latestExecution": {"status": "Succeeded"},
                "actionStates": [
                    {
                        "actionName": "BuildAction",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "preceding-build-id",
                        },
                    }
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
                            "token": "tok",
                            "pipelineExecutionId": "exec-1",
                        },
                    }
                ],
            },
        ]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        mock_retry.side_effect = [
            _build_response(),
            _log_events(["preceding log line"]),
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is True
        assert "preceding log line" in result["content"]


class TestReviewDiffNoCodeBuildAction:
    """No CodeBuild action found (no externalExecutionId in any action)."""

    @pytest.mark.asyncio
    async def test_no_codebuild_action(self):
        stage_states = [
            {
                "stageName": "Review",
                "latestExecution": {"status": "InProgress"},
                "actionStates": [
                    {
                        "actionName": "ManualApproval",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok",
                            "pipelineExecutionId": "exec-1",
                        },
                    }
                ],
            }
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is False
        assert "no CodeBuild action found" in result["warning"]


class TestReviewDiffEmptyBuilds:
    """CodeBuild batch_get_builds returns empty builds list."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_empty_builds(self, mock_cb, mock_logs, mock_retry):
        stage_states = [_stage_with_codebuild_and_approval()]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        mock_retry.side_effect = [
            {"builds": []},  # empty builds
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is False
        assert "not found" in result["warning"]


class TestReviewDiffBuildNoLogs:
    """CodeBuild build has no logs (no groupName/streamName)."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_build_no_logs(self, mock_cb, mock_logs, mock_retry):
        stage_states = [_stage_with_codebuild_and_approval()]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        mock_retry.side_effect = [
            {"builds": [{"id": "build-id-123"}]},  # no logs key
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is False
        assert "no log information" in result["warning"]


class TestReviewDiffEmptyLogEvents:
    """CloudWatch get_log_events returns empty events."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_empty_log_events(self, mock_cb, mock_logs, mock_retry):
        stage_states = [_stage_with_codebuild_and_approval()]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        mock_retry.side_effect = [
            _build_response(),
            {"events": []},  # empty events
        ]

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is False
        assert "no log events found" in result["warning"]


class TestReviewDiffApiError:
    """API error during retrieval — returns warning (graceful degradation)."""

    @pytest.mark.asyncio
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    async def test_api_error_graceful(self, mock_cb, mock_logs, mock_retry):
        stage_states = [_stage_with_codebuild_and_approval()]

        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        mock_retry.side_effect = Exception("CodeBuild API unavailable")

        result = await _retrieve_review_stage_diff(stage_states, "Review")

        assert result["success"] is False
        assert "Could not retrieve Review stage diff" in result["warning"]


# ===========================================================================
# Task 12.4 — Integration tests for tool_get_manual_approval_status()
# ===========================================================================


class TestIntegrationPendingApprovalWithReviewDiff:
    """Pending approval with review diff — both approval metadata and review_diff."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    @patch(_CP)
    async def test_pending_with_review_diff(
        self, mock_cp, mock_cb, mock_logs, mock_retry, mock_s3_diff
    ):
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        pipeline_state = {"stageStates": [_stage_with_codebuild_and_approval()]}

        # Calls: get_pipeline_state, batch_get_builds, get_log_events
        mock_retry.side_effect = [
            pipeline_state,
            _build_response(),
            _log_events(["CDK diff output line 1", "CDK diff output line 2"]),
        ]

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["token"] == "approval-token"
        assert result["stage_name"] == "Review"
        assert "review_diff" in result
        assert "CDK diff output line 1" in result["review_diff"]
        assert "CDK diff output line 2" in result["review_diff"]


class TestIntegrationPendingApprovalWithReviewDiffAndS3Diff:
    """Pending approval with review diff AND S3 diff enabled — both present."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=True)
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_aws_account_id",
        return_value="123456789012",
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_s3_client"
    )
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    @patch(_CP)
    async def test_pending_with_review_diff_and_s3_diff(
        self,
        mock_cp,
        mock_cb,
        mock_logs,
        mock_retry,
        mock_s3,
        mock_account,
        mock_s3_diff,
    ):
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()
        mock_s3.return_value = Mock()

        pipeline_state = {"stageStates": [_stage_with_codebuild_and_approval()]}

        # Mock S3 body
        mock_body = Mock()
        mock_body.read.return_value = b"S3 structured diff content"
        s3_response = {"Body": mock_body}

        # Calls: get_pipeline_state, batch_get_builds, get_log_events, s3.get_object
        mock_retry.side_effect = [
            pipeline_state,
            _build_response(),
            _log_events(["CodeBuild log line"]),
            s3_response,
        ]

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        # Both review_diff and s3_diff_content should be present
        assert "review_diff" in result
        assert "CodeBuild log line" in result["review_diff"]
        assert "s3_diff_content" in result
        assert result["s3_diff_content"] == "S3 structured diff content"


class TestIntegrationPendingApprovalWithReviewDiffFailure:
    """Pending approval with review diff failure — approval metadata + warning."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_RETRY)
    @patch(_LOGS)
    @patch(_CB)
    @patch(_CP)
    async def test_pending_with_review_diff_failure(
        self, mock_cp, mock_cb, mock_logs, mock_retry, mock_s3_diff
    ):
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_cb.return_value = Mock()
        mock_logs.return_value = Mock()

        pipeline_state = {"stageStates": [_stage_with_codebuild_and_approval()]}

        # Calls: get_pipeline_state succeeds, batch_get_builds raises error
        mock_retry.side_effect = [
            pipeline_state,
            Exception("CodeBuild service error"),
        ]

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["token"] == "approval-token"
        # review_diff should NOT be present, but warning should be
        assert "review_diff" not in result
        assert "review_diff_warning" in result
        assert "Could not retrieve Review stage diff" in result["review_diff_warning"]


class TestIntegrationNoApprovalSkipsReviewDiff:
    """No pending approval — _retrieve_review_stage_diff() is NOT called."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_CB)
    @patch(_RETRY)
    @patch(_CP)
    async def test_no_approval_skips_review_diff(
        self, mock_cp, mock_retry, mock_cb, mock_s3_diff
    ):
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        pipeline_state = {
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

        mock_retry.return_value = pipeline_state

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is False
        # CodeBuild client should NOT have been called
        mock_cb.assert_not_called()
        assert "review_diff" not in result
