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

"""Unit tests for S3Manager file upload functionality."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.utils.timeout_utils import TimeoutError


class TestUploadZipFile:
    """Test ZIP file upload to S3."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test data")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    async def test_upload_success(self, mock_getsize, mock_exists, mock_file, mock_get_session):
        """Test successful file upload."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        mock_s3_client = Mock()
        mock_s3_client.upload_file.return_value = None
        mock_s3_client.head_object.return_value = {
            "ContentLength": 1024,
            "ETag": '"abc123"'
        }
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session
        
        manager = S3Manager()
        result = await manager.upload_zip_file(
            zip_path="/tmp/test.zip",
            bucket_name="test-bucket",
            key="test-key.zip"
        )
        
        assert result["success"] is True
        assert result["bucket_name"] == "test-bucket"
        assert result["object_key"] == "test-key.zip"
        assert result["file_size"] == 1024
        assert "upload_time" in result
        assert "verification_status" in result

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self):
        """Test upload fails when file doesn't exist."""
        manager = S3Manager()
        result = await manager.upload_zip_file(
            zip_path="/nonexistent/file.zip",
            bucket_name="test-bucket"
        )
        
        assert result["success"] is False
        assert result["error_code"] == "ZIP_FILE_NOT_FOUND"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test data")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    async def test_upload_client_error(self, mock_getsize, mock_exists, mock_file, mock_get_session):
        """Test upload handles ClientError."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_client.upload_file.side_effect = ClientError(error_response, "PutObject")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session
        
        manager = S3Manager()
        result = await manager.upload_zip_file(
            zip_path="/tmp/test.zip",
            bucket_name="test-bucket"
        )
        
        assert result["success"] is False
        assert "S3 upload failed" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.with_timeout")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test data")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    async def test_upload_timeout(self, mock_getsize, mock_exists, mock_file, mock_with_timeout, mock_get_session):
        """Test upload handles timeout."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_with_timeout.side_effect = TimeoutError("Upload timed out")
        
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        
        manager = S3Manager()
        result = await manager.upload_zip_file(
            zip_path="/tmp/test.zip",
            bucket_name="test-bucket"
        )
        
        assert result["success"] is False
        assert result["error_code"] == "S3_UPLOAD_TIMEOUT"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test data")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    async def test_upload_unexpected_error(self, mock_getsize, mock_exists, mock_file, mock_get_session):
        """Test upload handles unexpected errors."""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        mock_s3_client = Mock()
        mock_s3_client.upload_file.side_effect = RuntimeError("Unexpected error")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session
        
        manager = S3Manager()
        result = await manager.upload_zip_file(
            zip_path="/tmp/test.zip",
            bucket_name="test-bucket"
        )
        
        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_UPLOAD_ERROR"
        assert "Unexpected error" in result["error"]
