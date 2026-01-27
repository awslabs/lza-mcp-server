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

"""Unit tests for S3UploadUtils bucket operations."""

import pytest
from unittest.mock import patch, AsyncMock

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils


class TestBucketOperations:
    """Test bucket name determination and validation."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_upload_determines_default_bucket_name(self, mock_check_connectivity):
        """Test upload determines default bucket name when not provided."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()

        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = aws_context

        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )

        utils.s3_manager.determine_bucket_name = AsyncMock(
            return_value="aws-accelerator-config-123456789012-us-east-1"
        )
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)
        utils.s3_manager.prompt_for_custom_bucket_name = AsyncMock(return_value={})

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        utils.s3_manager.determine_bucket_name.assert_called_once_with(
            account_id="123456789012", region="us-east-1"
        )

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_upload_validates_custom_bucket_name(self, mock_check_connectivity):
        """Test upload validates provided custom bucket name."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        custom_bucket = "my-custom-bucket"

        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = aws_context

        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )

        utils.s3_manager.validate_custom_bucket_name = AsyncMock(
            return_value={"valid": True}
        )
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)
        utils.s3_manager.prompt_for_custom_bucket_name = AsyncMock(return_value={})

        # Act
        result = await utils.upload_configuration(mock_ctx, bucket_name=custom_bucket)

        # Assert
        utils.s3_manager.validate_custom_bucket_name.assert_called_once_with(
            custom_bucket
        )

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_upload_fails_on_invalid_bucket_name(self, mock_check_connectivity):
        """Test upload fails when custom bucket name is invalid."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        invalid_bucket = "Invalid_Bucket_Name"

        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = aws_context

        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )

        utils.s3_manager.validate_custom_bucket_name = AsyncMock(
            return_value={
                "valid": False,
                "error": "Invalid bucket name format",
                "error_type": "VALIDATION_ERROR",
                "troubleshooting": ["Use lowercase letters only"],
            }
        )

        # Act
        result = await utils.upload_configuration(mock_ctx, bucket_name=invalid_bucket)

        # Assert
        assert result["success"] is False
        assert "bucket name validation failed" in result["message"]
        assert result["error"] == "Invalid bucket name format"
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_upload_verifies_bucket_exists(self, mock_check_connectivity):
        """Test upload verifies bucket existence."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        bucket_name = "existing-bucket"

        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = aws_context

        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )

        utils.s3_manager.validate_custom_bucket_name = AsyncMock(
            return_value={"valid": True}
        )
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)

        # Act
        # Will fail at ZIP creation but that's OK for this test
        try:
            await utils.upload_configuration(mock_ctx, bucket_name=bucket_name)
        except:
            pass

        # Assert
        utils.s3_manager.verify_bucket_exists.assert_called_once_with(bucket_name)

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_upload_prompts_when_bucket_not_found(self, mock_check_connectivity):
        """Test upload prompts user when bucket doesn't exist."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        bucket_name = "nonexistent-bucket"

        aws_context = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = aws_context

        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )

        utils.s3_manager.determine_bucket_name = AsyncMock(return_value=bucket_name)
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)

        prompt_response = {
            "prompt": "Provide custom bucket name",
            "default": bucket_name,
        }
        utils.s3_manager.prompt_for_custom_bucket_name = AsyncMock(
            return_value=prompt_response
        )

        # Act
        result = await utils.upload_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert f"Bucket '{bucket_name}' does not exist" in result["error"]
        assert result["user_prompt"] == prompt_response
        assert "next_steps" in result
        utils.s3_manager.prompt_for_custom_bucket_name.assert_called_once()
