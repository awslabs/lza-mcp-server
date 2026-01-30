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

"""Unit tests for utils S3 download functionality."""

from unittest.mock import patch, Mock
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.utils.utils import download_from_s3


class TestUtilsS3Download:
    """Test S3 download functionality."""

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_success(self, mock_get_session):
        """Test successful S3 file download."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket", key="test-key.txt", local_path="/tmp/test.txt"
        )

        assert result is True
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once_with("s3")
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "test-key.txt", "/tmp/test.txt"
        )

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_client_error(self, mock_get_session):
        """Test S3 download with ClientError."""
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}
        mock_s3_client.download_file.side_effect = ClientError(
            error_response, "GetObject"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket", key="nonexistent.txt", local_path="/tmp/test.txt"
        )

        assert result is False
        mock_s3_client.download_file.assert_called_once()

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_access_denied(self, mock_get_session):
        """Test S3 download with access denied error."""
        mock_s3_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_client.download_file.side_effect = ClientError(
            error_response, "GetObject"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="restricted-bucket", key="secret.txt", local_path="/tmp/test.txt"
        )

        assert result is False

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_bucket_not_found(self, mock_get_session):
        """Test S3 download with bucket not found error."""
        mock_s3_client = Mock()
        error_response = {
            "Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}
        }
        mock_s3_client.download_file.side_effect = ClientError(
            error_response, "GetObject"
        )
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="nonexistent-bucket", key="file.txt", local_path="/tmp/test.txt"
        )

        assert result is False

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_generic_exception(self, mock_get_session):
        """Test S3 download with generic exception."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Network error")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket", key="file.txt", local_path="/tmp/test.txt"
        )

        assert result is False

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_with_nested_key(self, mock_get_session):
        """Test S3 download with nested key path."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket",
            key="path/to/nested/file.txt",
            local_path="/tmp/test.txt",
        )

        assert result is True
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "path/to/nested/file.txt", "/tmp/test.txt"
        )

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_with_special_characters(self, mock_get_session):
        """Test S3 download with special characters in key."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket",
            key="file with spaces & special-chars.txt",
            local_path="/tmp/test.txt",
        )

        assert result is True
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "file with spaces & special-chars.txt", "/tmp/test.txt"
        )

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_creates_s3_client(self, mock_get_session):
        """Test that S3 client is created correctly."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        download_from_s3(
            bucket="test-bucket", key="test.txt", local_path="/tmp/test.txt"
        )

        mock_session.client.assert_called_once_with("s3")

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_timeout_error(self, mock_get_session):
        """Test S3 download with timeout error."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Connection timeout")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket", key="large-file.zip", local_path="/tmp/test.zip"
        )

        assert result is False

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_empty_bucket_name(self, mock_get_session):
        """Test S3 download with empty bucket name."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Invalid bucket name")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(bucket="", key="file.txt", local_path="/tmp/test.txt")

        assert result is False

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_session")
    def test_download_from_s3_empty_key(self, mock_get_session):
        """Test S3 download with empty key."""
        mock_s3_client = Mock()
        mock_s3_client.download_file.side_effect = Exception("Invalid key")
        mock_session = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = download_from_s3(
            bucket="test-bucket", key="", local_path="/tmp/test.txt"
        )

        assert result is False
