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

"""Unit tests for upload_config_s3 validation."""

import pytest
from unittest.mock import patch, Mock, AsyncMock

from awslabs.lza_mcp_server.tools.config.upload_config_s3 import (
    tool_upload_configuration_to_s3,
)


class TestUploadConfigValidation:
    """Test input validation for upload_configuration_to_s3."""

    @pytest.mark.asyncio
    async def test_invalid_config_path_absolute(self, mock_mcp_context):
        """Test validation rejects absolute paths."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path="/absolute/path/to/config",
            bucket_name=None,
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_CONFIG_PATH"
        assert (
            "absolute" in result["error"].lower()
            or "invalid" in result["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_config_path_parent_traversal(self, mock_mcp_context):
        """Test validation rejects parent directory traversal."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path="../../../etc/passwd",
            bucket_name=None,
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_CONFIG_PATH"

    @pytest.mark.asyncio
    async def test_invalid_bucket_name_too_short(self, mock_mcp_context):
        """Test validation rejects bucket names that are too short."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path=None,
            bucket_name="ab",  # Too short (< 3 chars)
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_BUCKET_NAME"
        assert "at least 3 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_bucket_name_too_long(self, mock_mcp_context):
        """Test validation rejects bucket names that are too long."""
        long_name = "a" * 64  # Too long (> 63 chars)
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path=None,
            bucket_name=long_name,
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_BUCKET_NAME"

    @pytest.mark.asyncio
    async def test_invalid_bucket_name_uppercase(self, mock_mcp_context):
        """Test validation rejects bucket names with uppercase letters."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path=None,
            bucket_name="MyBucket",  # Contains uppercase
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_BUCKET_NAME"
        assert "lowercase" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_bucket_name_special_chars(self, mock_mcp_context):
        """Test validation rejects bucket names with invalid characters."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path=None,
            bucket_name="my_bucket!",  # Contains invalid chars
            offer_pipeline_release=False,
        )

        # Should return validation error
        assert "error" in result
        assert result["error_code"] == "INVALID_BUCKET_NAME"

    @pytest.mark.asyncio
    async def test_host_path_detection_users(self, mock_mcp_context):
        """Test detection of host paths starting with /Users/."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path="/Users/username/config",
            bucket_name=None,
            offer_pipeline_release=False,
        )

        # Should fail validation first (absolute path)
        # Note: Host path detection happens AFTER validation
        assert "error" in result
        assert result["error_code"] == "INVALID_CONFIG_PATH"
        assert (
            "absolute" in result["error"].lower()
            or "invalid" in result["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_host_path_detection_tilde(self, mock_mcp_context):
        """Test detection of host paths starting with ~/."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path="~/my-config",
            bucket_name=None,
            offer_pipeline_release=False,
        )

        # Should detect host path and return specific error
        assert "error" in result
        assert result["error_code"] == "HOST_PATH_PROVIDED"
        assert "host filesystem path" in result["error"]
        assert "getConfigurationFromS3" in result["error"]

    @pytest.mark.asyncio
    async def test_valid_relative_path(self, mock_mcp_context):
        """Test that valid relative paths pass validation."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_upload_utils:
            mock_instance = Mock()
            mock_upload_utils.return_value = mock_instance
            mock_instance.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Config not found",  # Expected since path doesn't exist
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path="./my-config",  # Valid relative path
                bucket_name="valid-bucket-name",
                offer_pipeline_release=False,
            )

        # Should pass validation (may fail later for other reasons)
        # The key is that it doesn't fail with INVALID_CONFIG_PATH or HOST_PATH_PROVIDED
        if "error_code" in result:
            assert result["error_code"] not in [
                "INVALID_CONFIG_PATH",
                "HOST_PATH_PROVIDED",
            ]

    @pytest.mark.asyncio
    async def test_valid_bucket_name(self, mock_mcp_context):
        """Test that valid bucket names pass validation."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_upload_utils:
            mock_instance = Mock()
            mock_upload_utils.return_value = mock_instance
            mock_instance.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Config not found",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=None,
                bucket_name="valid-bucket-name-123",  # Valid bucket name
                offer_pipeline_release=False,
            )

        # Should pass validation
        if "error_code" in result:
            assert result["error_code"] != "INVALID_BUCKET_NAME"
