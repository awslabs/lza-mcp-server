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

"""Unit tests for S3 operations in aws_access module."""

from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import download_from_s3


class TestS3DownloadSuccess:
    """Test successful S3 download operations."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_success(self, mock_get_session):
        """Test successful S3 file download."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert result is True
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once_with("s3")
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "test-key", "/tmp/test-file"
        )

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_with_nested_key(self, mock_get_session):
        """Test S3 download with nested object key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            "test-bucket", "path/to/nested/file.txt", "/tmp/file.txt"
        )

        assert result is True
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "path/to/nested/file.txt", "/tmp/file.txt"
        )

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_with_special_characters(self, mock_get_session):
        """Test S3 download with special characters in key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            "test-bucket", "file with spaces & special.txt", "/tmp/file.txt"
        )

        assert result is True
        mock_s3_client.download_file.assert_called_once()


class TestS3DownloadErrors:
    """Test S3 download error handling."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_no_such_bucket(self, mock_get_session):
        """Test S3 download with non-existent bucket."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            error_response={
                "Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}
            },
            operation_name="GetObject",
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("nonexistent-bucket", "test-key", "/tmp/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_no_such_key(self, mock_get_session):
        """Test S3 download with non-existent key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            error_response={
                "Error": {"Code": "NoSuchKey", "Message": "Key does not exist"}
            },
            operation_name="GetObject",
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "nonexistent-key", "/tmp/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_access_denied(self, mock_get_session):
        """Test S3 download with access denied error."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            },
            operation_name="GetObject",
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_generic_exception(self, mock_get_session):
        """Test S3 download with generic exception."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Generic error")
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()


class TestS3DownloadFileSystem:
    """Test S3 download with file system errors."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_permission_error(self, mock_get_session):
        """Test S3 download with file system permission error."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = PermissionError("Permission denied")
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/root/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_file_not_found_error(self, mock_get_session):
        """Test S3 download with file not found error."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = FileNotFoundError(
            "Directory does not exist"
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            "test-bucket", "test-key", "/nonexistent/path/test-file"
        )

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_disk_full_error(self, mock_get_session):
        """Test S3 download with disk full error."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = OSError("No space left on device")
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert result is False
        mock_s3_client.download_file.assert_called_once()


class TestS3DownloadEdgeCases:
    """Test edge cases in S3 download operations."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_empty_bucket_name(self, mock_get_session):
        """Test S3 download with empty bucket name."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "InvalidBucketName",
                    "Message": "Invalid bucket name",
                }
            },
            operation_name="GetObject",
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("", "test-key", "/tmp/test-file")

        assert result is False

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_empty_key(self, mock_get_session):
        """Test S3 download with empty key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = ClientError(
            error_response={
                "Error": {"Code": "NoSuchKey", "Message": "Key does not exist"}
            },
            operation_name="GetObject",
        )
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "", "/tmp/test-file")

        assert result is False

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_very_long_key(self, mock_get_session):
        """Test S3 download with very long key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        long_key = "a" * 1024  # 1024 character key
        result = download_from_s3("test-bucket", long_key, "/tmp/test-file")

        assert result is True
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", long_key, "/tmp/test-file"
        )

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_unicode_characters(self, mock_get_session):
        """Test S3 download with unicode characters in key."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        unicode_key = "测试文件-🚀-ñoño.txt"
        result = download_from_s3("test-bucket", unicode_key, "/tmp/test-file")

        assert result is True
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", unicode_key, "/tmp/test-file"
        )


class TestS3DownloadReturnValues:
    """Test S3 download return values."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_returns_boolean(self, mock_get_session):
        """Test that download_from_s3 returns boolean."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert isinstance(result, bool)
        assert result is True

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_download_from_s3_returns_false_on_error(self, mock_get_session):
        """Test that download_from_s3 returns False on error."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Error")
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3("test-bucket", "test-key", "/tmp/test-file")

        assert isinstance(result, bool)
        assert result is False
