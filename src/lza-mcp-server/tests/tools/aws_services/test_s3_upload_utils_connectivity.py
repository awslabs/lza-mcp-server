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

"""Unit tests for S3UploadUtils AWS connectivity verification."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils


class TestEnsureAwsConnectivity:
    """Test AWS connectivity verification and caching."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_ensure_connectivity_success(self, mock_check_connectivity):
        """Test successful AWS connectivity verification."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = Mock()

        connectivity_result = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
            "message": "Connected successfully",
        }
        mock_check_connectivity.return_value = connectivity_result

        # Act
        result = await utils.ensure_aws_connectivity(mock_ctx)

        # Assert
        assert result == connectivity_result
        assert utils._aws_connectivity_verified is True
        assert utils._aws_context == connectivity_result
        mock_check_connectivity.assert_called_once_with(mock_ctx)

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_ensure_connectivity_caches_result(self, mock_check_connectivity):
        """Test AWS connectivity result is cached."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = Mock()

        connectivity_result = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-east-1",
        }
        mock_check_connectivity.return_value = connectivity_result

        # Act - First call
        result1 = await utils.ensure_aws_connectivity(mock_ctx)
        # Act - Second call
        result2 = await utils.ensure_aws_connectivity(mock_ctx)

        # Assert
        assert result1 == connectivity_result
        assert result2 == connectivity_result
        # Should only call the connectivity check once due to caching
        mock_check_connectivity.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_ensure_connectivity_failure(self, mock_check_connectivity):
        """Test AWS connectivity verification failure."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = Mock()

        connectivity_result = {
            "connected": False,
            "message": "Unable to connect to AWS",
        }
        mock_check_connectivity.return_value = connectivity_result

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await utils.ensure_aws_connectivity(mock_ctx)

        assert "AWS connectivity failed" in str(exc_info.value)
        assert "Unable to connect to AWS" in str(exc_info.value)
        assert utils._aws_connectivity_verified is False
        assert utils._aws_context is None

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_ensure_connectivity_exception(self, mock_check_connectivity):
        """Test AWS connectivity check raises exception."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = Mock()
        mock_check_connectivity.side_effect = Exception("Network error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await utils.ensure_aws_connectivity(mock_ctx)

        assert "Network error" in str(exc_info.value)
        assert utils._aws_connectivity_verified is False

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_ensure_connectivity_returns_cached_on_subsequent_calls(
        self, mock_check_connectivity
    ):
        """Test cached connectivity result is returned without re-checking."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = Mock()

        connectivity_result = {
            "connected": True,
            "account_id": "123456789012",
            "region": "us-west-2",
        }
        mock_check_connectivity.return_value = connectivity_result

        # Act
        await utils.ensure_aws_connectivity(mock_ctx)

        # Modify the mock to return different result
        mock_check_connectivity.return_value = {
            "connected": True,
            "account_id": "999999999999",
            "region": "eu-west-1",
        }

        # Second call should return cached result
        result = await utils.ensure_aws_connectivity(mock_ctx)

        # Assert - Should return original cached result
        assert result["account_id"] == "123456789012"
        assert result["region"] == "us-west-2"
        mock_check_connectivity.assert_called_once()
