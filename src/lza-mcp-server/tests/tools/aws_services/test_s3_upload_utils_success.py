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

"""Unit tests for S3UploadUtils successful upload scenarios."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils


class TestUploadSuccess:
    """Test successful upload scenarios."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_configuration_success(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test successful configuration upload."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        
        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1"
        }
        mock_check_connectivity.return_value = aws_context
        
        utils._discover_and_select_configuration = AsyncMock(return_value={
            "success": True,
            "selected_config": "/config"
        })
        
        bucket_name = "test-bucket"
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value=bucket_name)
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        
        # Mock temp file
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        # Mock ZIP creation
        mock_create_zip.return_value = {
            "success": True,
            "file_size": 1024
        }
        
        # Mock S3 upload
        utils.s3_manager.upload_zip_file = AsyncMock(return_value={
            "success": True,
            "file_size": 1024,
            "etag": "abc123"
        })
        
        # Mock cleanup
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is True
        assert "successfully uploaded" in result["message"]
        assert result["bucket_name"] == bucket_name
        assert result["s3_location"] == f"s3://{bucket_name}/zipped/aws-accelerator-config.zip"
        assert result["upload_size"] == 1024
        assert result["pipeline_release_offered"] is True

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_without_pipeline_release_offer(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload without offering pipeline release."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        
        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1"
        }
        mock_check_connectivity.return_value = aws_context
        
        utils._discover_and_select_configuration = AsyncMock(return_value={
            "success": True,
            "selected_config": "/config"
        })
        
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value="test-bucket")
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        mock_create_zip.return_value = {"success": True, "file_size": 1024}
        utils.s3_manager.upload_zip_file = AsyncMock(return_value={
            "success": True,
            "file_size": 1024
        })
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(
            mock_ctx, offer_pipeline_release=False
        )

        # Assert
        assert result["success"] is True
        assert "pipeline_release_offered" not in result

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_with_custom_bucket(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload with custom bucket name."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        custom_bucket = "my-custom-bucket"
        
        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1"
        }
        mock_check_connectivity.return_value = aws_context
        
        utils._discover_and_select_configuration = AsyncMock(return_value={
            "success": True,
            "selected_config": "/config"
        })
        
        utils.s3_manager.validate_custom_bucket_name = AsyncMock(return_value={
            "valid": True
        })
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        mock_create_zip.return_value = {"success": True, "file_size": 1024}
        utils.s3_manager.upload_zip_file = AsyncMock(return_value={
            "success": True,
            "file_size": 1024
        })
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(mock_ctx, bucket_name=custom_bucket)

        # Assert
        assert result["success"] is True
        assert result["bucket_name"] == custom_bucket
        assert result["s3_location"] == f"s3://{custom_bucket}/zipped/aws-accelerator-config.zip"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_with_specific_config_path(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload with specific configuration path."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        config_path = "/specific/config/path"
        
        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1"
        }
        mock_check_connectivity.return_value = aws_context
        
        utils._discover_and_select_configuration = AsyncMock(return_value={
            "success": True,
            "selected_config": config_path
        })
        
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value="test-bucket")
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        mock_create_zip.return_value = {"success": True, "file_size": 1024}
        utils.s3_manager.upload_zip_file = AsyncMock(return_value={
            "success": True,
            "file_size": 1024
        })
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(mock_ctx, config_path=config_path)

        # Assert
        assert result["success"] is True
        utils._discover_and_select_configuration.assert_called_once_with(
            mock_ctx, config_path
        )
