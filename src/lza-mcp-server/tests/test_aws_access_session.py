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

"""Unit tests for AWS session and client creation in aws_access module."""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import NoCredentialsError

from awslabs.lza_mcp_server.aws_access import (
    get_aws_session,
    get_aws_account_id,
    get_s3_client,
    get_codepipeline_client,
    get_codebuild_client,
    get_logs_client,
)


class TestAWSSessionCreation:
    """Test AWS session creation."""

    @patch.dict("os.environ", {"AWS_REGION": "us-west-2"})
    @patch("awslabs.lza_mcp_server.aws_access.boto3.Session")
    def test_get_aws_session_with_custom_region(self, mock_session_class):
        """Test AWS session creation with custom region from environment."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Need to reload the module to pick up the new environment variable
        import importlib
        import awslabs.lza_mcp_server.aws_access as aws_access_module

        importlib.reload(aws_access_module)

        session = aws_access_module.get_aws_session()

        assert session is not None
        # Verify session was created with the region from environment
        mock_session_class.assert_called_with(region_name="us-west-2")

    @patch("awslabs.lza_mcp_server.aws_access.boto3.Session")
    def test_get_aws_session_default_region(self, mock_session_class):
        """Test AWS session creation with default region."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session is not None
        mock_session_class.assert_called_once()

    def test_get_aws_session_returns_valid_session(self):
        """Test that get_aws_session returns a valid boto3 session."""
        session = get_aws_session()

        assert session is not None
        assert hasattr(session, "client")
        assert hasattr(session, "resource")
        assert callable(session.client)


class TestAWSAccountAccess:
    """Test AWS account ID retrieval."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_success(self, mock_get_session):
        """Test successful AWS account ID retrieval."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts_client
        mock_get_session.return_value = mock_session

        account_id = get_aws_account_id()

        assert account_id == "123456789012"
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once_with("sts")
        mock_sts_client.get_caller_identity.assert_called_once()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_no_credentials(self, mock_get_session):
        """Test AWS account ID retrieval with no credentials."""
        mock_get_session.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            get_aws_account_id()

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_aws_account_id_different_account(self, mock_get_session):
        """Test AWS account ID retrieval with different account."""
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "999888777666"}
        mock_session.client.return_value = mock_sts_client
        mock_get_session.return_value = mock_session

        account_id = get_aws_account_id()

        assert account_id == "999888777666"


class TestS3ClientCreation:
    """Test S3 client creation with configuration."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_s3_client_success(self, mock_get_session):
        """Test successful S3 client creation."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        client = get_s3_client()

        assert client is not None
        mock_get_session.assert_called_once()
        mock_session.client.assert_called_once()

        # Verify client was created with correct service name and config
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "s3"
        assert "config" in call_args[1]

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_s3_client_with_retry_config(self, mock_get_session):
        """Test S3 client creation includes retry configuration."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        client = get_s3_client()

        assert client is not None
        call_args = mock_session.client.call_args
        config = call_args[1]["config"]

        # Verify retry configuration is present
        assert hasattr(config, "retries")

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_s3_client_with_timeout_config(self, mock_get_session):
        """Test S3 client creation includes timeout configuration."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        client = get_s3_client()

        assert client is not None
        call_args = mock_session.client.call_args
        config = call_args[1]["config"]

        # Verify timeout configuration is present
        assert hasattr(config, "connect_timeout")
        assert hasattr(config, "read_timeout")

    def test_get_s3_client_returns_valid_client(self):
        """Test that get_s3_client returns a valid S3 client."""
        client = get_s3_client()

        assert client is not None
        assert hasattr(client, "list_buckets")
        assert hasattr(client, "get_object")
        assert hasattr(client, "put_object")


class TestCodePipelineClientCreation:
    """Test CodePipeline client creation with configuration."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_codepipeline_client_success(self, mock_get_session):
        """Test successful CodePipeline client creation."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_codepipeline_client()

        assert client is not None
        mock_get_session.assert_called_once()
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "codepipeline"

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_codepipeline_client_with_config(self, mock_get_session):
        """Test CodePipeline client creation includes configuration."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_codepipeline_client()

        assert client is not None
        call_args = mock_session.client.call_args
        assert "config" in call_args[1]

    def test_get_codepipeline_client_returns_valid_client(self):
        """Test that get_codepipeline_client returns a valid client."""
        client = get_codepipeline_client()

        assert client is not None
        assert hasattr(client, "get_pipeline")
        assert hasattr(client, "start_pipeline_execution")


class TestCodeBuildClientCreation:
    """Test CodeBuild client creation with configuration."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_codebuild_client_success(self, mock_get_session):
        """Test successful CodeBuild client creation."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_codebuild_client()

        assert client is not None
        mock_get_session.assert_called_once()
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "codebuild"

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_codebuild_client_with_config(self, mock_get_session):
        """Test CodeBuild client creation includes configuration."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_codebuild_client()

        assert client is not None
        call_args = mock_session.client.call_args
        assert "config" in call_args[1]

    def test_get_codebuild_client_returns_valid_client(self):
        """Test that get_codebuild_client returns a valid client."""
        client = get_codebuild_client()

        assert client is not None
        assert hasattr(client, "batch_get_builds")
        assert hasattr(client, "start_build")


class TestLogsClientCreation:
    """Test CloudWatch Logs client creation with configuration."""

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_logs_client_success(self, mock_get_session):
        """Test successful CloudWatch Logs client creation."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_logs_client()

        assert client is not None
        mock_get_session.assert_called_once()
        call_args = mock_session.client.call_args
        assert call_args[0][0] == "logs"

    @patch("awslabs.lza_mcp_server.aws_access.get_aws_session")
    def test_get_logs_client_with_config(self, mock_get_session):
        """Test CloudWatch Logs client creation includes configuration."""
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        client = get_logs_client()

        assert client is not None
        call_args = mock_session.client.call_args
        assert "config" in call_args[1]

    def test_get_logs_client_returns_valid_client(self):
        """Test that get_logs_client returns a valid client."""
        client = get_logs_client()

        assert client is not None
        assert hasattr(client, "get_log_events")
        assert hasattr(client, "describe_log_streams")
