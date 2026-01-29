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

"""Unit tests for S3Manager bucket name determination."""

import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager


class TestDetermineBucketName:
    """Test bucket name determination logic."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_account_id")
    @patch(
        "awslabs.lza_mcp_server.orchestration.core.s3_manager.AWS_REGION", "us-east-1"
    )
    async def test_determine_bucket_name_with_defaults(self, mock_get_account_id):
        """Test bucket name determination using default account ID and region."""
        mock_get_account_id.return_value = "123456789012"

        manager = S3Manager()
        bucket_name = await manager.determine_bucket_name()

        assert bucket_name == "aws-accelerator-config-123456789012-us-east-1"
        mock_get_account_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_determine_bucket_name_with_provided_values(self):
        """Test bucket name determination with provided account ID and region."""
        manager = S3Manager()
        bucket_name = await manager.determine_bucket_name(
            account_id="987654321098", region="us-west-2"
        )

        assert bucket_name == "aws-accelerator-config-987654321098-us-west-2"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_account_id")
    async def test_determine_bucket_name_with_partial_values(self, mock_get_account_id):
        """Test bucket name determination with only region provided."""
        mock_get_account_id.return_value = "123456789012"

        manager = S3Manager()
        bucket_name = await manager.determine_bucket_name(region="eu-west-1")

        assert bucket_name == "aws-accelerator-config-123456789012-eu-west-1"
        mock_get_account_id.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.orchestration.core.s3_manager.AWS_REGION",
        "ap-southeast-1",
    )
    async def test_determine_bucket_name_with_account_id_only(self):
        """Test bucket name determination with only account ID provided."""
        manager = S3Manager()
        bucket_name = await manager.determine_bucket_name(account_id="111222333444")

        assert bucket_name == "aws-accelerator-config-111222333444-ap-southeast-1"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_account_id")
    async def test_determine_bucket_name_empty_account_id(self, mock_get_account_id):
        """Test bucket name determination fails with empty account ID."""
        mock_get_account_id.return_value = ""

        manager = S3Manager()

        with pytest.raises(ValueError, match="Invalid AWS context"):
            await manager.determine_bucket_name()

    @pytest.mark.asyncio
    async def test_determine_bucket_name_empty_region(self):
        """Test bucket name determination fails with empty region."""
        manager = S3Manager()

        with pytest.raises(ValueError, match="Invalid AWS context"):
            await manager.determine_bucket_name(account_id="123456789012", region="")

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_account_id")
    async def test_determine_bucket_name_get_account_id_fails(
        self, mock_get_account_id
    ):
        """Test bucket name determination when get_aws_account_id fails."""
        mock_get_account_id.side_effect = Exception("Failed to get account ID")

        manager = S3Manager()

        with pytest.raises(Exception, match="Failed to get account ID"):
            await manager.determine_bucket_name()
