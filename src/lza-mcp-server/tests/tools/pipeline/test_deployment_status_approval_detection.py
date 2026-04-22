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

"""Tests for approval detection logic merged into get_deployment_status.py.

Covers: infer_s3_diff_bucket_name, _detect_pending_approval,
_retrieve_s3_diff, _retrieve_review_stage_diff, and the Step 6
integration in _get_standard_pipeline_status.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    infer_s3_diff_bucket_name,
    _detect_pending_approval,
    _retrieve_s3_diff,
    _retrieve_review_stage_diff,
)

_MOD = "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status"


# ---------------------------------------------------------------------------
# infer_s3_diff_bucket_name
# ---------------------------------------------------------------------------
class TestInferS3DiffBucketName:
    """Test S3 diff bucket name inference."""

    def test_standard_deployment(self):
        result = infer_s3_diff_bucket_name(
            "AWSAccelerator-Pipeline", None, "123456789012", "us-east-1"
        )
        assert result == "AWSAccelerator-diff-123456789012-us-east-1"

    def test_qualifier_deployment(self):
        result = infer_s3_diff_bucket_name(
            "myq-pipeline", "myq", "111111111111", "eu-west-1"
        )
        assert result == "myq-diff-111111111111-eu-west-1"

    def test_non_standard_pipeline_name(self):
        result = infer_s3_diff_bucket_name(
            "CustomName", None, "222222222222", "ap-southeast-1"
        )
        assert result == "CustomName-diff-222222222222-ap-southeast-1"


# ---------------------------------------------------------------------------
# _detect_pending_approval
# ---------------------------------------------------------------------------
class TestDetectPendingApproval:
    """Test _detect_pending_approval helper."""

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    async def test_approval_found(self, _s3_flag, mock_review):
        mock_review.return_value = {"success": False, "warning": "no codebuild"}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok-1",
                            "pipelineExecutionId": "exec-1",
                            "summary": "diff summary",
                        },
                        "entityUrl": "https://example.com",
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result is not None
        assert result["approval_pending"] is True
        assert result["approval_token"] == "tok-1"
        assert result["approval_stage_name"] == "Review"
        assert result["approval_action_name"] == "Approve"
        assert result["approval_pipeline_execution_id"] == "exec-1"
        assert result["approval_custom_data"] == "diff summary"
        assert result["approval_external_entity_url"] == "https://example.com"

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    async def test_no_approval(self, _s3_flag, mock_review):
        stages = [
            {
                "stageName": "Build",
                "actionStates": [
                    {
                        "actionName": "CodeBuild",
                        "latestExecution": {"status": "Succeeded"},
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    async def test_in_progress_without_token_skipped(self, _s3_flag, mock_review):
        """InProgress action without a token is not an approval action."""
        stages = [
            {
                "stageName": "Build",
                "actionStates": [
                    {
                        "actionName": "CodeBuild",
                        "latestExecution": {"status": "InProgress"},
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    async def test_optional_fields_absent(self, _s3_flag, mock_review):
        mock_review.return_value = {"success": False, "warning": "n/a"}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok-2",
                            "pipelineExecutionId": "exec-2",
                        },
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result is not None
        assert "approval_custom_data" not in result
        assert "approval_external_entity_url" not in result

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_s3_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=True)
    async def test_s3_diff_included_when_enabled(self, _flag, mock_review, mock_s3):
        mock_review.return_value = {"success": True, "content": "review logs"}
        mock_s3.return_value = {"success": True, "content": "s3 diff content"}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok-3",
                            "pipelineExecutionId": "exec-3",
                        },
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe", qualifier="q1")
        assert result["review_diff"] == "review logs"
        assert result["s3_diff_content"] == "s3 diff content"

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_s3_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=True)
    async def test_s3_diff_warning(self, _flag, mock_review, mock_s3):
        mock_review.return_value = {"success": False, "warning": "no cb"}
        mock_s3.return_value = {"success": False, "warning": "NoSuchKey"}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok-4",
                            "pipelineExecutionId": "exec-4",
                        },
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result["review_diff_warning"] == "no cb"
        assert result["s3_diff_warning"] == "NoSuchKey"

    @pytest.mark.asyncio
    @patch(f"{_MOD}._retrieve_review_stage_diff", new_callable=AsyncMock)
    @patch(f"{_MOD}.is_s3_diff_enabled", return_value=False)
    async def test_review_diff_success(self, _flag, mock_review):
        mock_review.return_value = {"success": True, "content": "cdk diff output"}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok-5",
                            "pipelineExecutionId": "exec-5",
                        },
                    }
                ],
            }
        ]
        result = await _detect_pending_approval(stages, "pipe")
        assert result["review_diff"] == "cdk diff output"


# ---------------------------------------------------------------------------
# _retrieve_s3_diff
# ---------------------------------------------------------------------------
class TestRetrieveS3Diff:
    """Test _retrieve_s3_diff helper."""

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_s3_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_aws_account_id", return_value="123456789012")
    async def test_success(self, _acct, mock_retry, mock_s3):
        body = MagicMock()
        body.read.return_value = b"diff content here"
        mock_retry.return_value = {"Body": body}
        result = await _retrieve_s3_diff("AWSAccelerator-Pipeline", None, "exec-1")
        assert result["success"] is True
        assert result["content"] == "diff content here"

    @pytest.mark.asyncio
    async def test_invalid_execution_id(self):
        result = await _retrieve_s3_diff("pipe", None, "")
        assert result["success"] is False
        assert "Invalid" in result["warning"]

    @pytest.mark.asyncio
    async def test_bad_chars_execution_id(self):
        result = await _retrieve_s3_diff("pipe", None, "exec/../bad")
        assert result["success"] is False
        assert "Invalid" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_s3_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_aws_account_id", return_value="123456789012")
    async def test_no_body(self, _acct, mock_retry, mock_s3):
        mock_retry.return_value = {}
        result = await _retrieve_s3_diff("pipe", None, "exec-2")
        assert result["success"] is False
        assert "missing content" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_s3_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_aws_account_id", return_value="123456789012")
    async def test_client_error(self, _acct, mock_retry, mock_s3):
        mock_retry.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
        )
        result = await _retrieve_s3_diff("pipe", None, "exec-3")
        assert result["success"] is False
        assert "Could not retrieve deployment diff from S3" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_s3_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    @patch(f"{_MOD}.get_aws_account_id", return_value="123456789012")
    async def test_generic_exception(self, _acct, mock_retry, mock_s3):
        mock_retry.side_effect = RuntimeError("boom")
        result = await _retrieve_s3_diff("pipe", None, "exec-4")
        assert result["success"] is False
        assert "Could not retrieve deployment diff from S3" in result["warning"]


# ---------------------------------------------------------------------------
# _retrieve_review_stage_diff
# ---------------------------------------------------------------------------
class TestRetrieveReviewStageDiff:
    """Test _retrieve_review_stage_diff helper."""

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_logs_client")
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_success_same_stage(self, mock_retry, mock_cb, mock_logs):
        mock_retry.side_effect = [
            # batch_get_builds
            {
                "builds": [
                    {
                        "logs": {
                            "groupName": "/aws/codebuild/review",
                            "streamName": "stream-1",
                        }
                    }
                ]
            },
            # get_log_events
            {
                "events": [
                    {"message": "line 1"},
                    {"message": "line 2"},
                ]
            },
        ]
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "CDKDiff",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-123",
                        },
                    },
                    {
                        "actionName": "ManualApproval",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "tok",
                        },
                    },
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is True
        assert "line 1" in result["content"]
        assert "line 2" in result["content"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_logs_client")
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_success_preceding_stage(self, mock_retry, mock_cb, mock_logs):
        mock_retry.side_effect = [
            {"builds": [{"logs": {"groupName": "g", "streamName": "s"}}]},
            {"events": [{"message": "diff output"}]},
        ]
        stages = [
            {
                "stageName": "Build",
                "actionStates": [
                    {
                        "actionName": "CB",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-prev",
                        },
                    }
                ],
            },
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {"status": "InProgress", "token": "t"},
                    }
                ],
            },
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_codebuild_action(self):
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "Approve",
                        "latestExecution": {"status": "InProgress", "token": "t"},
                    }
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is False
        assert "no CodeBuild action" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_build_not_found(self, mock_retry, mock_cb):
        mock_retry.return_value = {"builds": []}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "CB",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-x",
                        },
                    }
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is False
        assert "not found" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_build_no_logs(self, mock_retry, mock_cb):
        mock_retry.return_value = {"builds": [{"id": "b1"}]}
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "CB",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-y",
                        },
                    }
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is False
        assert "no log information" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_logs_client")
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_no_log_events(self, mock_retry, mock_cb, mock_logs):
        mock_retry.side_effect = [
            {"builds": [{"logs": {"groupName": "g", "streamName": "s"}}]},
            {"events": []},
        ]
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "CB",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-z",
                        },
                    }
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is False
        assert "no log events" in result["warning"]

    @pytest.mark.asyncio
    @patch(f"{_MOD}.get_codebuild_client")
    @patch(f"{_MOD}.retry_with_exponential_backoff", new_callable=AsyncMock)
    async def test_exception_graceful(self, mock_retry, mock_cb):
        mock_retry.side_effect = RuntimeError("network error")
        stages = [
            {
                "stageName": "Review",
                "actionStates": [
                    {
                        "actionName": "CB",
                        "latestExecution": {
                            "status": "Succeeded",
                            "externalExecutionId": "build-err",
                        },
                    }
                ],
            }
        ]
        result = await _retrieve_review_stage_diff(stages, "Review")
        assert result["success"] is False
        assert "Could not retrieve Review stage diff" in result["warning"]
