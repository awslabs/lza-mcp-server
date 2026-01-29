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

"""Unit tests for S3Manager bucket verification."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError
from awslabs.lza_mcp_server.utils.timeout_utils import TimeoutError


class TestVerifyBucketExists:
    """Test bucket existence verification."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    async def test_verify_bucket_exists_success(self, mock_get_session):
        """Test successful bucket verification."""
        mock_s3_client = Mock()
        mock_s3_client.head_bucket.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        result = await manager.verify_bucket_exists("test-bucket")

        assert result is True
        mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    async def test_verify_bucket_not_found(self, mock_get_session):
        """Test bucket verification when bucket doesn't exist (404)."""
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response, "HeadBucket"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        result = await manager.verify_bucket_exists("nonexistent-bucket")

        assert result is False

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    async def test_verify_bucket_access_denied(self, mock_get_session):
        """Test bucket verification when access is denied (403)."""
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response, "HeadBucket"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()

        with pytest.raises(S3UploadError) as exc_info:
            await manager.verify_bucket_exists("forbidden-bucket")

        assert exc_info.value.error_code == "AccessDenied"
        assert "Access denied" in exc_info.value.message
        assert "forbidden-bucket" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.categorize_aws_error")
    async def test_verify_bucket_other_client_error(
        self, mock_categorize, mock_get_session
    ):
        """Test bucket verification with other ClientError."""
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "500", "Message": "Internal Error"}}
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response, "HeadBucket"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        mock_categorize.return_value = {
            "category": "s3",
            "error_code": "InternalError",
            "troubleshooting": ["Check AWS service status"],
        }

        manager = S3Manager()

        with pytest.raises(S3UploadError) as exc_info:
            await manager.verify_bucket_exists("error-bucket")

        assert exc_info.value.error_code == "InternalError"
        assert "error-bucket" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.with_timeout")
    async def test_verify_bucket_timeout(self, mock_with_timeout, mock_get_session):
        """Test bucket verification timeout."""
        mock_with_timeout.side_effect = TimeoutError("Operation timed out")
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        manager = S3Manager()

        with pytest.raises(S3UploadError) as exc_info:
            await manager.verify_bucket_exists("timeout-bucket")

        assert exc_info.value.error_code == "BUCKET_VERIFICATION_TIMEOUT"
        assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    async def test_verify_bucket_unexpected_error(self, mock_get_session):
        """Test bucket verification with unexpected error."""
        mock_s3_client = Mock()
        mock_s3_client.head_bucket.side_effect = RuntimeError("Unexpected error")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()

        with pytest.raises(S3UploadError) as exc_info:
            await manager.verify_bucket_exists("error-bucket")

        assert exc_info.value.error_code == "UNEXPECTED_BUCKET_ERROR"
        assert "Unexpected error" in exc_info.value.message
