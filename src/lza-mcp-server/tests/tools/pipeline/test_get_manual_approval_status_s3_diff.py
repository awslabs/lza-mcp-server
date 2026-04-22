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

"""Unit tests for getManualApprovalStatus S3 diff retrieval."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    tool_get_manual_approval_status,
    infer_s3_diff_bucket_name,
)

_CP = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_codepipeline_client"
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.retry_with_exponential_backoff"
_S3_DIFF = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.is_s3_diff_enabled"
_ACCOUNT = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_aws_account_id"
_S3_CLIENT = (
    "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_s3_client"
)


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _pipeline_state_with_approval(exec_id="exec-123"):
    """Return a pipeline state response with a pending approval action."""
    return {
        "stageStates": [
            {
                "stageName": "Review",
                "latestExecution": {"status": "InProgress"},
                "actionStates": [
                    {
                        "actionName": "ManualApproval",
                        "latestExecution": {
                            "status": "InProgress",
                            "token": "token-abc",
                            "pipelineExecutionId": exec_id,
                            "summary": "CDK diff",
                        },
                        "entityUrl": "https://example.com",
                    }
                ],
            }
        ]
    }


class TestS3DiffEnabledSuccess:
    """Test S3 diff enabled and successfully retrieved."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=True)
    @patch(_ACCOUNT, return_value="123456789012")
    @patch(_S3_CLIENT)
    @patch(_CP)
    @patch(_RETRY)
    async def test_s3_diff_included_in_response(
        self, mock_retry, mock_cp, mock_s3_client, mock_account, mock_s3_diff
    ):
        """Test: S3 diff content included in response when enabled and retrieved."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        # First call: get_pipeline_state; subsequent calls: s3 get_object
        s3_body = MagicMock()
        s3_body.read.return_value = b"--- diff content ---"

        call_count = [0]

        async def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _pipeline_state_with_approval()
            return {"Body": s3_body}

        mock_retry.side_effect = retry_side_effect

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["s3_diff_content"] == "--- diff content ---"


class TestS3DiffEnabledNoSuchKey:
    """Test S3 diff enabled but retrieval fails with NoSuchKey."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=True)
    @patch(_ACCOUNT, return_value="123456789012")
    @patch(_S3_CLIENT)
    @patch(_CP)
    @patch(_RETRY)
    async def test_s3_diff_nosuchkey_returns_warning(
        self, mock_retry, mock_cp, mock_s3_client, mock_account, mock_s3_diff
    ):
        """Test: NoSuchKey returns approval metadata with warning."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        call_count = [0]

        async def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _pipeline_state_with_approval()
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
                "GetObject",
            )

        mock_retry.side_effect = retry_side_effect

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["token"] == "token-abc"
        assert "s3_diff_content" not in result
        assert "s3_diff_warning" in result
        assert "Could not retrieve deployment diff from S3" in result["s3_diff_warning"]


class TestS3DiffEnabledAccessDenied:
    """Test S3 diff enabled but retrieval fails with AccessDenied."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=True)
    @patch(_ACCOUNT, return_value="123456789012")
    @patch(_S3_CLIENT)
    @patch(_CP)
    @patch(_RETRY)
    async def test_s3_diff_access_denied_returns_warning(
        self, mock_retry, mock_cp, mock_s3_client, mock_account, mock_s3_diff
    ):
        """Test: AccessDenied returns approval metadata with warning."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()

        call_count = [0]

        async def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _pipeline_state_with_approval()
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "GetObject",
            )

        mock_retry.side_effect = retry_side_effect

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert result["token"] == "token-abc"
        assert "s3_diff_content" not in result
        assert "s3_diff_warning" in result
        assert "Could not retrieve deployment diff from S3" in result["s3_diff_warning"]


class TestS3DiffDisabled:
    """Test S3 diff disabled — S3 not called."""

    @pytest.mark.asyncio
    @patch(_S3_DIFF, return_value=False)
    @patch(_S3_CLIENT)
    @patch(_CP)
    @patch(_RETRY)
    async def test_s3_not_called_when_disabled(
        self, mock_retry, mock_cp, mock_s3_client, mock_s3_diff
    ):
        """Test: S3 diff disabled — S3 client not called, no diff in response."""
        ctx = _make_ctx()
        mock_cp.return_value = Mock()
        mock_retry.return_value = _pipeline_state_with_approval()

        result = await tool_get_manual_approval_status(ctx)

        assert result["success"] is True
        assert result["approval_pending"] is True
        assert "s3_diff_content" not in result
        assert "s3_diff_warning" not in result
        # S3 client should not have been used
        mock_s3_client.assert_not_called()


class TestS3DiffBucketNameInference:
    """Test S3 diff bucket name inference."""

    def test_standard_deployment_bucket_name(self):
        """Test: standard deployment infers AWSAccelerator-diff-{account}-{region}."""
        bucket = infer_s3_diff_bucket_name(
            pipeline_name="AWSAccelerator-Pipeline",
            qualifier=None,
            account_id="123456789012",
            region="us-east-1",
        )
        assert bucket == "AWSAccelerator-diff-123456789012-us-east-1"

    def test_external_deployment_bucket_name(self):
        """Test: external deployment infers {qualifier}-diff-{account}-{region}."""
        bucket = infer_s3_diff_bucket_name(
            pipeline_name="my-qual-pipeline",
            qualifier="my-qual",
            account_id="987654321098",
            region="eu-west-1",
        )
        assert bucket == "my-qual-diff-987654321098-eu-west-1"
