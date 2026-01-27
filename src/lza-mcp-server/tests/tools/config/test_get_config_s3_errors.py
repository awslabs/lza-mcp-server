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

"""Unit tests for S3ConfigRetrieval error handling."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestGetConfigurationErrors:
    """Test error handling in configuration retrieval."""

    @pytest.mark.asyncio
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_invalid_bucket_name(self, mock_cleanup):
        """Test configuration retrieval with invalid bucket name."""
        mock_cleanup.return_value = None
        
        retrieval = S3ConfigRetrieval()
        retrieval._validate_bucket_name = Mock(return_value={
            "valid": False,
            "error": "Bucket name is invalid"
        })
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="Invalid-Bucket")
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BUCKET_NAME"
        assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_custom_bucket_not_found(self, mock_cleanup):
        """Test configuration retrieval when custom bucket doesn't exist."""
        mock_cleanup.return_value = None
        
        retrieval = S3ConfigRetrieval()
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="nonexistent-bucket")
        
        assert result["success"] is False
        assert result["error_code"] == "BUCKET_NOT_FOUND"
        assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_default_bucket_not_found(self, mock_cleanup):
        """Test configuration retrieval when default bucket doesn't exist."""
        mock_cleanup.return_value = None
        
        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager.determine_bucket_name = AsyncMock(
            return_value="aws-accelerator-config-123456789012-us-east-1"
        )
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx)
        
        assert result["success"] is False
        assert result["error_code"] == "DEFAULT_BUCKET_NOT_FOUND"
        assert "Default bucket" in result["error"]

    @pytest.mark.asyncio
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_object_not_found(self, mock_cleanup, mock_mkstemp):
        """Test configuration retrieval when S3 object doesn't exist."""
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        mock_s3_client.download_file.side_effect = ClientError(error_response, "GetObject")
        
        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="test-bucket")
        
        assert result["success"] is False
        assert result["error_code"] == "OBJECT_NOT_FOUND"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_s3_download_error(self, mock_cleanup, mock_mkstemp):
        """Test configuration retrieval with S3 download error."""
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_client.download_file.side_effect = ClientError(error_response, "GetObject")
        
        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="test-bucket")
        
        assert result["success"] is False
        assert "Failed to download" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.is_zipfile")
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_invalid_zip(self, mock_cleanup, mock_mkstemp, mock_is_zipfile):
        """Test configuration retrieval with invalid ZIP file."""
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        mock_is_zipfile.return_value = False
        
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        
        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="test-bucket")
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_ZIP_FILE"
        assert "not a valid ZIP" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.ZipFile")
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.is_zipfile")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_extraction_fails(
        self, mock_cleanup, mock_mkstemp, mock_exists, mock_makedirs,
        mock_is_zipfile, mock_zipfile_class
    ):
        """Test configuration retrieval when ZIP extraction fails."""
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        mock_exists.return_value = False
        mock_is_zipfile.return_value = True
        
        mock_zip = Mock()
        mock_zip.extractall.side_effect = Exception("Extraction failed")
        mock_zipfile_class.return_value.__enter__.return_value = mock_zip
        
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        
        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx, bucket_name="test-bucket")
        
        assert result["success"] is False
        assert result["error_code"] == "EXTRACTION_FAILED"
        assert "Failed to extract" in result["error"]

    @pytest.mark.asyncio
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_unexpected_error(self, mock_cleanup):
        """Test configuration retrieval with unexpected error."""
        mock_cleanup.side_effect = RuntimeError("Unexpected error")
        
        retrieval = S3ConfigRetrieval()
        
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        
        result = await retrieval.get_configuration(mock_ctx)
        
        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_RETRIEVAL_ERROR"
        assert "Unexpected error" in result["error"]
