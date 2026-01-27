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

"""Unit tests for AWS tools module - simplified version."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError, NoCredentialsError

# Import the actual modules to ensure coverage
from awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools import (
    register_aws_tools,
)
from awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity import (
    tool_check_aws_connectivity,
)
from awslabs.lza_mcp_server.aws_access import get_aws_session, get_aws_account_id
from awslabs.lza_mcp_server.constants import DEFAULT_REGION, BUCKET_PREFIX


# Mock fixtures for testing
class MockSTSClient:
    def __init__(self, account_id="123456789012", user_arn=None, user_id=None):
        self.account_id = account_id
        self.user_arn = user_arn or f"arn:aws:iam::{account_id}:user/test-user"
        self.user_id = user_id or "AIDACKCEVSQ6C2EXAMPLE"

    def get_caller_identity(self):
        return {
            "Account": self.account_id,
            "Arn": self.user_arn,
            "UserId": self.user_id,
        }


class MockS3Client:
    def __init__(self, existing_buckets=None):
        self.existing_buckets = existing_buckets or []

    def head_bucket(self, Bucket):
        if Bucket not in self.existing_buckets:
            raise ClientError(
                error_response={"Error": {"Code": "404", "Message": "Not Found"}},
                operation_name="HeadBucket",
            )
        return {}

    def create_bucket(self, **kwargs):
        return {}

    def put_bucket_lifecycle_configuration(self, **kwargs):
        return {}

    def put_bucket_tagging(self, **kwargs):
        return {}


class MockContext:
    async def info(self, message):
        pass

    async def error(self, message):
        pass


class TestGetAwsSession:
    """Test cases for get_aws_session function."""

    def test_get_aws_session_default_region(self):
        """Test creating AWS session with default region."""
        # Patch AWS_REGION in the aws_access module since it's read at import time
        with patch("awslabs.lza_mcp_server.aws_access.AWS_REGION", DEFAULT_REGION), \
             patch("boto3.Session") as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            result = get_aws_session()

            mock_session_class.assert_called_once_with(region_name=DEFAULT_REGION)
            assert result == mock_session


class TestGetAwsAccountId:
    """Test cases for get_aws_account_id function."""

    def test_get_aws_account_id_success(self):
        """Test successful retrieval of AWS account ID."""
        mock_sts_client = MockSTSClient(account_id="123456789012")

        with patch(
            "awslabs.lza_mcp_server.aws_access.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            result = get_aws_account_id()

            assert result == "123456789012"
            mock_session.client.assert_called_once_with("sts")

    def test_get_aws_account_id_client_error(self):
        """Test handling of ClientError when getting account ID."""
        with patch(
            "awslabs.lza_mcp_server.aws_access.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = ClientError(
                error_response={
                    "Error": {"Code": "AccessDenied", "Message": "Access denied"}
                },
                operation_name="GetCallerIdentity",
            )
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            with pytest.raises(ClientError):
                get_aws_account_id()

    def test_get_aws_account_id_no_credentials(self):
        """Test handling of NoCredentialsError when getting account ID."""
        with patch(
            "awslabs.lza_mcp_server.aws_access.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            with pytest.raises(NoCredentialsError):
                get_aws_account_id()


class TestRegisterAwsTools:
    """Test cases for register_aws_service_tools function."""

    def test_register_aws_service_tools_success(self):
        """Test successful registration of AWS tools."""
        mock_mcp = Mock()

        register_aws_tools(mock_mcp)

        # Verify that tool registration was called
        assert mock_mcp.tool.call_count == 2

        # Verify the tools were registered with correct names
        tool_calls = mock_mcp.tool.call_args_list
        tool_names = [call[1]["name"] for call in tool_calls]

        assert "checkAwsConnectivity" in tool_names
        assert "getDeployedLzaVersion" in tool_names


class TestEnvironmentVariableHandling:
    """Test cases for environment variable handling."""

    def test_default_region_constant(self):
        """Test that DEFAULT_REGION constant is set correctly."""
        assert DEFAULT_REGION == "us-east-1"

    def test_bucket_prefix_constant(self):
        """Test that BUCKET_PREFIX constant is set correctly."""
        assert BUCKET_PREFIX == "awslabs-lza-mcp-server"


class TestAsyncAwsOperations:
    """Test cases for async AWS operations."""

    @pytest.mark.asyncio
    async def test_check_aws_connectivity_tool_success(self):
        """Test successful AWS connectivity check tool."""
        mock_sts_client = MockSTSClient(
            account_id="123456789012",
            user_arn="arn:aws:iam::123456789012:user/test-user",
            user_id="AIDACKCEVSQ6C2EXAMPLE",
        )

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            mock_context = MockContext()
            result = await tool_check_aws_connectivity(mock_context)

            assert result["connected"] is True
            assert result["account_id"] == "123456789012"
            assert result["user_arn"] == "arn:aws:iam::123456789012:user/test-user"
            assert result["user_id"] == "AIDACKCEVSQ6C2EXAMPLE"
            assert "region" in result
            assert "Successfully connected" in result["message"]

    @pytest.mark.asyncio
    async def test_check_aws_connectivity_tool_no_credentials(self):
        """Test AWS connectivity check tool with no credentials error."""
        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity.get_aws_session"
        ) as mock_get_session:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()
            mock_session.client.return_value = mock_sts_client
            mock_get_session.return_value = mock_session

            mock_context = MockContext()
            result = await tool_check_aws_connectivity(mock_context)

            assert result["connected"] is False
            assert "error" in result
            assert "troubleshooting" in result
