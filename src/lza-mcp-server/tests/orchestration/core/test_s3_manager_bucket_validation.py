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

"""Unit tests for S3Manager bucket validation."""

import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager


class TestValidateCustomBucketName:
    """Test custom bucket name validation."""

    @pytest.mark.asyncio
    @patch.object(S3Manager, "verify_bucket_exists")
    async def test_validate_valid_bucket(self, mock_verify):
        """Test validation of a valid and accessible bucket."""
        mock_verify.return_value = True

        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("valid-bucket-name")

        assert result["valid"] is True
        assert result["bucket_name"] == "valid-bucket-name"
        assert "valid and accessible" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_empty_bucket_name(self):
        """Test validation fails for empty bucket name."""
        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("")

        assert result["valid"] is False
        assert "cannot be empty" in result["error"]
        assert result["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_validate_bucket_name_too_short(self):
        """Test validation fails for bucket name too short."""
        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("ab")

        assert result["valid"] is False
        assert "between 3 and 63 characters" in result["error"]
        assert result["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_validate_bucket_name_too_long(self):
        """Test validation fails for bucket name too long."""
        manager = S3Manager()
        long_name = "a" * 64
        result = await manager.validate_custom_bucket_name(long_name)

        assert result["valid"] is False
        assert "between 3 and 63 characters" in result["error"]
        assert result["error_type"] == "validation"

    @pytest.mark.asyncio
    async def test_validate_bucket_name_not_lowercase(self):
        """Test validation fails for non-lowercase bucket name."""
        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("MyBucket")

        assert result["valid"] is False
        assert "must be lowercase" in result["error"]
        assert result["error_type"] == "validation"

    @pytest.mark.asyncio
    @patch.object(S3Manager, "verify_bucket_exists")
    async def test_validate_bucket_does_not_exist(self, mock_verify):
        """Test validation fails when bucket doesn't exist."""
        mock_verify.return_value = False

        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("nonexistent-bucket")

        assert result["valid"] is False
        assert "does not exist" in result["error"]
        assert result["error_type"] == "access"
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    @patch.object(S3Manager, "verify_bucket_exists")
    async def test_validate_bucket_verification_exception(self, mock_verify):
        """Test validation handles exceptions from verify_bucket_exists."""
        mock_verify.side_effect = Exception("Network error")

        manager = S3Manager()
        result = await manager.validate_custom_bucket_name("error-bucket")

        assert result["valid"] is False
        assert "Failed to validate" in result["error"]
        assert result["error_type"] == "unexpected"
        assert "troubleshooting" in result
