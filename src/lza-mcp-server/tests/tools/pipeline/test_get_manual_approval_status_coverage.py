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

"""Additional coverage tests for get_manual_approval_status."""

import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    infer_s3_diff_bucket_name,
    _retrieve_s3_diff,
    _determine_pipeline_status,
)

_RETRY = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.retry_with_exponential_backoff"
_S3_CLIENT = (
    "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_s3_client"
)


class TestInferS3DiffBucketNameEdgeCases:
    """Test edge cases for S3 diff bucket name inference."""

    def test_pipeline_name_without_pipeline_suffix(self):
        """Test pipeline name that does not end with '-Pipeline' — uses full name as prefix."""
        bucket = infer_s3_diff_bucket_name(
            pipeline_name="CustomPipeline",
            qualifier=None,
            account_id="111222333444",
            region="us-west-2",
        )
        assert bucket == "CustomPipeline-diff-111222333444-us-west-2"


_ACCOUNT = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status.get_aws_account_id"


class TestRetrieveS3DiffGenericException:
    """Test _retrieve_s3_diff with generic (non-ClientError) exception."""

    @pytest.mark.asyncio
    @patch(_ACCOUNT, return_value="123456789012")
    @patch(_RETRY)
    @patch(_S3_CLIENT)
    async def test_generic_exception_returns_warning(
        self, mock_s3_client, mock_retry, mock_account
    ):
        """Test generic exception returns warning dict."""
        mock_retry.side_effect = RuntimeError("unexpected error")

        result = await _retrieve_s3_diff(
            pipeline_name="AWSAccelerator-Pipeline",
            qualifier=None,
            pipeline_execution_id="exec-123",
        )

        assert result["success"] is False
        assert "Could not retrieve deployment diff from S3" in result["warning"]


class TestDeterminePipelineStatusEdgeCases:
    """Test _determine_pipeline_status edge cases."""

    def test_failed_stage_status(self):
        """Test pipeline with a failed stage returns Failed."""
        stage_states = [
            {"latestExecution": {"status": "Failed"}},
        ]
        result = _determine_pipeline_status(stage_states)
        assert result == "Failed"

    def test_unknown_status_not_succeeded(self):
        """Test stage with unknown status — not counted as succeeded."""
        stage_states = [
            {"latestExecution": {"status": "Cancelled"}},
        ]
        result = _determine_pipeline_status(stage_states)
        # Not InProgress, not Failed, not all Succeeded → returns "Unknown"
        assert result == "Unknown"


class TestRetrieveS3DiffInputValidation:
    """Test _retrieve_s3_diff input validation for path traversal prevention."""

    @pytest.mark.asyncio
    async def test_invalid_execution_id_format(self):
        """Test execution ID with path traversal chars — rejected."""
        result = await _retrieve_s3_diff(
            pipeline_name="AWSAccelerator-Pipeline",
            qualifier=None,
            pipeline_execution_id="../../../etc/passwd",
        )

        assert result["success"] is False
        assert "Invalid pipeline execution ID" in result["warning"]

    @pytest.mark.asyncio
    async def test_empty_execution_id(self):
        """Test empty execution ID — rejected."""
        result = await _retrieve_s3_diff(
            pipeline_name="AWSAccelerator-Pipeline",
            qualifier=None,
            pipeline_execution_id="",
        )

        assert result["success"] is False
        assert "Invalid pipeline execution ID" in result["warning"]

    @pytest.mark.asyncio
    @patch(_ACCOUNT, return_value="123456789012")
    @patch(_RETRY)
    @patch(_S3_CLIENT)
    async def test_missing_body_in_response(
        self, mock_s3_client, mock_retry, mock_account
    ):
        """Test S3 response missing Body field — returns warning."""
        mock_retry.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        result = await _retrieve_s3_diff(
            pipeline_name="AWSAccelerator-Pipeline",
            qualifier=None,
            pipeline_execution_id="exec-abc-123",
        )

        assert result["success"] is False
        assert "missing content" in result["warning"]
