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

"""Unit tests for S3ConfigRetrieval bucket name validation."""

from unittest.mock import patch

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestValidateBucketName:
    """Test bucket name validation."""

    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.validate_s3_bucket_name")
    def test_validate_bucket_name_valid(self, mock_validate):
        """Test validation of valid bucket name."""
        mock_validate.return_value = (True, None)

        retrieval = S3ConfigRetrieval()
        result = retrieval._validate_bucket_name("valid-bucket-name")

        assert result["valid"] is True
        mock_validate.assert_called_once_with("valid-bucket-name")

    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.validate_s3_bucket_name")
    def test_validate_bucket_name_invalid(self, mock_validate):
        """Test validation of invalid bucket name."""
        mock_validate.return_value = (False, "Bucket name must be lowercase")

        retrieval = S3ConfigRetrieval()
        result = retrieval._validate_bucket_name("InvalidBucket")

        assert result["valid"] is False
        assert "InvalidBucket" in result["error"]
        assert "must be lowercase" in result["error"]

    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.validate_s3_bucket_name")
    def test_validate_bucket_name_empty(self, mock_validate):
        """Test validation of empty bucket name."""
        mock_validate.return_value = (False, "Bucket name cannot be empty")

        retrieval = S3ConfigRetrieval()
        result = retrieval._validate_bucket_name("")

        assert result["valid"] is False
        assert "cannot be empty" in result["error"]

    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.validate_s3_bucket_name")
    def test_validate_bucket_name_too_short(self, mock_validate):
        """Test validation of bucket name that's too short."""
        mock_validate.return_value = (
            False,
            "Bucket name must be at least 3 characters",
        )

        retrieval = S3ConfigRetrieval()
        result = retrieval._validate_bucket_name("ab")

        assert result["valid"] is False
        assert "at least 3 characters" in result["error"]

    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.validate_s3_bucket_name")
    def test_validate_bucket_name_too_long(self, mock_validate):
        """Test validation of bucket name that's too long."""
        long_name = "a" * 64
        mock_validate.return_value = (
            False,
            "Bucket name must be at most 63 characters",
        )

        retrieval = S3ConfigRetrieval()
        result = retrieval._validate_bucket_name(long_name)

        assert result["valid"] is False
        assert "at most 63 characters" in result["error"]
