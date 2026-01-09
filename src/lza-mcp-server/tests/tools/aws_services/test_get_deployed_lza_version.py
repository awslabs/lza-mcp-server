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

"""Unit tests for get_deployed_lza_version tool."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version import (
    tool_get_deployed_lza_version,
)


class MockContext:
    """Mock context for testing."""

    async def info(self, message):
        pass

    async def error(self, message):
        pass


class MockSTSClient:
    """Mock STS client for testing."""

    def __init__(self, account_id="123456789012"):
        self.account_id = account_id

    def get_caller_identity(self):
        return {
            "Account": self.account_id,
            "Arn": f"arn:aws:iam::{self.account_id}:user/test-user",
            "UserId": "AIDACKCEVSQ6C2EXAMPLE",
        }


class MockSSMClient:
    """Mock SSM client for testing."""

    def __init__(self, version="1.13.0", raise_error=None):
        self.version = version
        self.raise_error = raise_error

    def get_parameter(self, Name):
        if self.raise_error:
            raise self.raise_error

        return {
            "Parameter": {
                "Name": Name,
                "Type": "String",
                "Value": self.version,
                "Version": 1,
                "LastModifiedDate": datetime(2024, 1, 1, 12, 0, 0),
                "ARN": f"arn:aws:ssm:us-east-1:123456789012:parameter{Name}",
            }
        }


class TestGetDeployedLzaVersion:
    """Test cases for get_deployed_lza_version tool."""

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_success(self):
        """Test successful retrieval of LZA version."""
        mock_context = MockContext()
        mock_sts_client = MockSTSClient()
        mock_ssm_client = MockSSMClient(version="1.13.0")

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.side_effect = lambda service: (
                mock_sts_client if service == "sts" else mock_ssm_client
            )
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is True
        assert result["version"] == "v1.13.0"
        assert result["raw_version"] == "1.13.0"
        assert result["account_id"] == "123456789012"
        assert "region" in result
        assert "parameter_name" in result
        assert "last_modified" in result

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_with_v_prefix(self):
        """Test retrieval when version already has 'v' prefix."""
        mock_context = MockContext()
        mock_sts_client = MockSTSClient()
        mock_ssm_client = MockSSMClient(version="v1.13.0")

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.side_effect = lambda service: (
                mock_sts_client if service == "sts" else mock_ssm_client
            )
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is True
        assert result["version"] == "v1.13.0"
        assert result["raw_version"] == "v1.13.0"

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_parameter_not_found(self):
        """Test handling when SSM parameter is not found."""
        mock_context = MockContext()
        mock_sts_client = MockSTSClient()

        error = ClientError(
            error_response={
                "Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}
            },
            operation_name="GetParameter",
        )
        mock_ssm_client = MockSSMClient(raise_error=error)

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.side_effect = lambda service: (
                mock_sts_client if service == "sts" else mock_ssm_client
            )
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is False
        assert result["error"] == "ParameterNotFound"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_access_denied(self):
        """Test handling when access is denied to SSM parameter."""
        mock_context = MockContext()
        mock_sts_client = MockSTSClient()

        error = ClientError(
            error_response={
                "Error": {"Code": "AccessDeniedException", "Message": "Access denied"}
            },
            operation_name="GetParameter",
        )
        mock_ssm_client = MockSSMClient(raise_error=error)

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.side_effect = lambda service: (
                mock_sts_client if service == "sts" else mock_ssm_client
            )
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is False
        assert result["error"] == "AccessDeniedException"
        assert "troubleshooting" in result
        assert any("IAM permissions" in item for item in result["troubleshooting"])

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_aws_connectivity_failure(self):
        """Test handling when AWS connectivity check fails."""
        mock_context = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = Exception(
                "Connection error"
            )
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_ssm_client_error(self):
        """Test handling of generic SSM client errors."""
        mock_context = MockContext()
        mock_sts_client = MockSTSClient()

        error = ClientError(
            error_response={
                "Error": {"Code": "InternalServerError", "Message": "Internal error"}
            },
            operation_name="GetParameter",
        )
        mock_ssm_client = MockSSMClient(raise_error=error)

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.side_effect = lambda service: (
                mock_sts_client if service == "sts" else mock_ssm_client
            )
            mock_get_session.return_value = mock_session

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_unexpected_error(self):
        """Test handling of unexpected errors."""
        mock_context = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.get_deployed_lza_version.get_aws_session"
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Unexpected error")

            result = await tool_get_deployed_lza_version(mock_context)

        assert result["success"] is False
        assert "error" in result
        assert "Unexpected error" in result["message"]
        assert "troubleshooting" in result
