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

"""Unit tests for S3UploadUtils error handling."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError


class TestUploadErrors:
    """Test error handling during upload."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    async def test_upload_fails_on_aws_connectivity_error(self, mock_check_connectivity):
        """Test upload fails when AWS connectivity cannot be established."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        
        # Mock connectivity check to raise exception
        mock_check_connectivity.side_effect = Exception("Unable to connect")

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert "Configuration upload failed" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    async def test_upload_fails_on_config_discovery_error(self, mock_check_connectivity):
        """Test upload fails when configuration discovery fails."""
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
            "success": False,
            "error": "No configurations found"
        })

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert result["error"] == "No configurations found"
        assert result["aws_context"] == aws_context

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_fails_on_zip_creation_error(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload fails when ZIP creation fails."""
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
        
        mock_create_zip.return_value = {
            "success": False,
            "error": "Failed to create ZIP"
        }
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert "Failed to create configuration ZIP" in result["message"]
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_fails_on_s3_upload_error(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload fails when S3 upload fails."""
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
            "success": False,
            "error": "Access denied",
            "error_code": "AccessDenied",
            "troubleshooting": ["Check IAM permissions"]
        })
        mock_cleanup_zip.return_value = {"success": True}

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert "S3 upload failed" in result["message"]
        assert result["error"] == "Access denied"
        assert result["error_code"] == "AccessDenied"
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    async def test_upload_handles_s3_upload_error_exception(self, mock_check_connectivity):
        """Test upload handles S3UploadError exceptions."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        
        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1"
        }
        mock_check_connectivity.return_value = aws_context
        
        error = S3UploadError(
            message="Upload error",
            error_code="UPLOAD_FAILED",
            category="INTEGRATION"
        )
        utils._discover_and_select_configuration = AsyncMock(side_effect=error)

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "UPLOAD_FAILED"
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    async def test_upload_handles_unexpected_exception(self, mock_check_connectivity):
        """Test upload handles unexpected exceptions."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        
        mock_check_connectivity.side_effect = Exception("Unexpected error")

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert "Configuration upload failed" in result["error"]
        assert result["error_code"] == "UNEXPECTED_UPLOAD_ERROR"
        assert "troubleshooting" in result
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity")
    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile")
    async def test_upload_logs_cleanup_failure(
        self, mock_tempfile, mock_check_connectivity, mock_create_zip, mock_cleanup_zip
    ):
        """Test upload logs cleanup failure but continues."""
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
        
        # Cleanup fails
        mock_cleanup_zip.return_value = {
            "success": False,
            "error": "Permission denied"
        }

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is True  # Upload still succeeds
        mock_ctx.error.assert_called_once()  # Cleanup error is logged
        assert "Failed to cleanup" in str(mock_ctx.error.call_args)
