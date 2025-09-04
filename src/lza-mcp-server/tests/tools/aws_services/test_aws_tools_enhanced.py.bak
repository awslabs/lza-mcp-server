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

"""Enhanced unit tests for AWS tools module."""

import pytest
from unittest.mock import patch, Mock
from botocore.exceptions import ClientError, NoCredentialsError
from awslabs.lza_mcp_server.aws_access import get_aws_account_id
from awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket import (
    get_validation_bucket,
)
from awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools import (
    register_aws_service_tools,
)


class TestGetAwsAccountId:
    """Test cases for get_aws_account_id function."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_success(self, mock_get_session):
        """Test successful retrieval of AWS account ID."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_get_session.return_value = mock_session

        result = get_aws_account_id()

        assert result == "123456789012"
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once_with("sts")
        mock_sts_client.get_caller_identity.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_client_error(self, mock_get_session):
        """Test get_aws_account_id with ClientError."""
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

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_no_credentials(self, mock_get_session):
        """Test get_aws_account_id with no credentials."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()
        mock_session.client.return_value = mock_sts_client
        mock_get_session.return_value = mock_session

        with pytest.raises(NoCredentialsError):
            get_aws_account_id()


class TestGetValidationBucket:
    """Test cases for get_validation_bucket function."""

    @patch("awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_session")
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_account_id"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.VALIDATION_BUCKET",
        "",
    )
    def test_get_validation_bucket_create_new_us_east_1(
        self, mock_get_account_id, mock_get_session
    ):
        """Test creating new validation bucket in us-east-1."""
        mock_get_account_id.return_value = "123456789012"
        mock_session = Mock()
        mock_s3_client = Mock()

        # Mock head_bucket to raise 404 (bucket doesn't exist)
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadBucket",
        )

        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.AWS_REGION",
            "us-east-1",
        ):
            result = get_validation_bucket()

        # Verify bucket creation without location constraint for us-east-1
        mock_s3_client.create_bucket.assert_called_once_with(Bucket=result)
        mock_s3_client.put_bucket_lifecycle_configuration.assert_called_once()
        mock_s3_client.put_bucket_tagging.assert_called_once()
        assert result.startswith("awslabs-lza-mcp-server-123456789012-us-east-1")

    @patch("awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_session")
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_account_id"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.VALIDATION_BUCKET",
        "",
    )
    def test_get_validation_bucket_create_new_other_region(
        self, mock_get_account_id, mock_get_session
    ):
        """Test creating new validation bucket in non-us-east-1 region."""
        mock_get_account_id.return_value = "123456789012"
        mock_session = Mock()
        mock_s3_client = Mock()

        # Mock head_bucket to raise 404 (bucket doesn't exist)
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadBucket",
        )

        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.AWS_REGION",
            "eu-west-1",
        ):
            result = get_validation_bucket()

        # Verify bucket creation with location constraint for non-us-east-1
        mock_s3_client.create_bucket.assert_called_once_with(
            Bucket=result, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        mock_s3_client.put_bucket_lifecycle_configuration.assert_called_once()
        mock_s3_client.put_bucket_tagging.assert_called_once()

    @patch("awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_session")
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.VALIDATION_BUCKET",
        "existing-bucket",
    )
    def test_get_validation_bucket_existing_bucket(self, mock_get_session):
        """Test using existing validation bucket."""
        mock_session = Mock()
        mock_s3_client = Mock()

        # Mock head_bucket to succeed (bucket exists)
        mock_s3_client.head_bucket.return_value = {}

        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        result = get_validation_bucket()

        assert result == "existing-bucket"
        mock_s3_client.head_bucket.assert_called_once_with(Bucket="existing-bucket")
        mock_s3_client.create_bucket.assert_not_called()

    @patch("awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_session")
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.get_aws_account_id"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.setup_S3_bucket.VALIDATION_BUCKET",
        "",
    )
    def test_get_validation_bucket_access_denied(
        self, mock_get_account_id, mock_get_session
    ):
        """Test get_validation_bucket with access denied error."""
        mock_get_account_id.return_value = "123456789012"
        mock_session = Mock()
        mock_s3_client = Mock()

        # Mock head_bucket to raise access denied
        mock_s3_client.head_bucket.side_effect = ClientError(
            error_response={"Error": {"Code": "403", "Message": "Access Denied"}},
            operation_name="HeadBucket",
        )

        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        with pytest.raises(ClientError):
            get_validation_bucket()


class TestRegisterAwsTools:
    """Test cases for register_aws_tools function."""

    def test_register_aws_tools(self):
        """Test that AWS tools are registered with MCP."""
        mock_mcp = Mock()
        mock_tool_decorator = Mock()
        mock_mcp.tool.return_value = mock_tool_decorator

        register_aws_service_tools(mock_mcp)

        # Verify that tool decorator was called
        mock_mcp.tool.assert_called()

        # Check that tools were registered (multiple tools are registered)
        assert mock_mcp.tool.call_count > 0

    def test_register_aws_tools_integration(self):
        """Test that AWS tools registration works without errors."""
        mock_mcp = Mock()

        # This should not raise any exceptions
        register_aws_service_tools(mock_mcp)

        # Verify that multiple tools were registered
        assert mock_mcp.tool.call_count >= 1
