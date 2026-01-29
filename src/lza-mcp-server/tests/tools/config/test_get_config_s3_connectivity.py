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

"""Unit tests for S3ConfigRetrieval AWS connectivity checks."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestEnsureAwsConnectivity:
    """Test AWS connectivity verification."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.get_aws_session")
    async def test_ensure_aws_connectivity_success(self, mock_get_session):
        """Test successful AWS connectivity check."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test-user",
        }
        mock_session = Mock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = "us-east-1"
        mock_get_session.return_value = mock_session

        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()

        result = await retrieval.ensure_aws_connectivity(mock_ctx)

        assert result["success"] is True
        assert result["account_id"] == "123456789012"
        assert result["user_arn"] == "arn:aws:iam::123456789012:user/test-user"
        assert result["region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.get_aws_session")
    async def test_ensure_aws_connectivity_failure(self, mock_get_session):
        """Test AWS connectivity check failure."""
        mock_get_session.side_effect = Exception("No credentials found")

        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()

        with pytest.raises(Exception, match="AWS connectivity check failed"):
            await retrieval.ensure_aws_connectivity(mock_ctx)

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.get_aws_session")
    async def test_ensure_aws_connectivity_sts_error(self, mock_get_session):
        """Test AWS connectivity check when STS call fails."""
        mock_sts = Mock()
        mock_sts.get_caller_identity.side_effect = Exception("Access denied")
        mock_session = Mock()
        mock_session.client.return_value = mock_sts
        mock_get_session.return_value = mock_session

        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()

        with pytest.raises(Exception, match="AWS connectivity check failed"):
            await retrieval.ensure_aws_connectivity(mock_ctx)
