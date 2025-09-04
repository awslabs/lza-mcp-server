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

"""Unit tests for validate configuration share module."""

import pytest
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError, NoCredentialsError

from awslabs.lza_mcp_server.tools.validation.validate_configuration_share import (
    tool_validate_configuration_from_share,
    _validate_from_docker_path,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class MockSTSClient:
    """Mock STS client for testing."""

    def __init__(self, account_id="123456789012"):
        self.account_id = account_id

    def get_caller_identity(self):
        return {"Account": self.account_id}


class TestValidateFromDockerPath:
    """Test cases for _validate_from_docker_path function."""

    @pytest.mark.asyncio
    async def test_validate_from_docker_path_success(self):
        """Test successful validation from Docker path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file with valid config
            zip_path = os.path.join(temp_dir, "config.zip")
            config_content = "key: value\n"

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", config_content)

            mock_ctx = MockContext()

            with patch(
                "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.validate_configuration_impl"
            ) as mock_validate:
                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await _validate_from_docker_path(mock_ctx, zip_path)

                assert result["valid"] is True
                assert result["message"] == "Success"
                mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_from_docker_path_file_not_found(self):
        """Test validation when ZIP file doesn't exist."""
        mock_ctx = MockContext()

        result = await _validate_from_docker_path(mock_ctx, "/nonexistent/config.zip")

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "ZIP file not found" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_from_docker_path_default_path(self):
        """Test validation with default Docker path from environment."""
        mock_ctx = MockContext()

        with patch.dict(os.environ, {"LZA_CONFIG_CONTAINER_PATH": "/custom/path"}):
            with patch("os.path.exists", return_value=False):
                result = await _validate_from_docker_path(mock_ctx)

                assert result["valid"] is False
                assert "/custom/path/config.zip" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_from_docker_path_extraction_error(self):
        """Test validation with ZIP extraction error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an invalid ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("not a zip file")

            mock_ctx = MockContext()

            result = await _validate_from_docker_path(mock_ctx, zip_path)

            assert result["valid"] is False
            assert "Validation failed" in result["message"]


class TestToolValidateConfigurationFromShare:
    """Test cases for tool_validate_configuration_from_share function."""

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_aws_credentials_fail(self):
        """Test validation when AWS credentials validation fails."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
        ) as mock_session:
            mock_session.side_effect = NoCredentialsError()

            result = await tool_validate_configuration_from_share(mock_ctx)

            assert result["valid"] is False
            assert "AWS credentials validation failed" in result["errors"][0]["message"]
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_aws_credentials_success(self):
        """Test validation with successful AWS credentials but missing ZIP."""
        mock_ctx = MockContext()

        mock_sts_client = MockSTSClient()

        with (
            patch(
                "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
            ) as mock_session,
            patch("os.path.exists", return_value=False),
        ):
            mock_session_obj = Mock()
            mock_session_obj.client.return_value = mock_sts_client
            mock_session.return_value = mock_session_obj

            result = await tool_validate_configuration_from_share(mock_ctx)

            assert result["valid"] is False
            assert (
                "config.zip not found in shared volume"
                in result["errors"][0]["message"]
            )
            assert "instructions" in result
            assert "PREREQUISITE STEPS MISSING" in result["instructions"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_success(self):
        """Test successful validation from share."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", "key: value\n")

            mock_ctx = MockContext()
            mock_sts_client = MockSTSClient()

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
                ) as mock_session,
                patch.dict(os.environ, {"LZA_CONFIG_CONTAINER_PATH": temp_dir}),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_session_obj = Mock()
                mock_session_obj.client.return_value = mock_sts_client
                mock_session.return_value = mock_session_obj

                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_share(mock_ctx)

                assert result["valid"] is True
                assert "validation_completed" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_custom_path(self):
        """Test validation with custom share path."""
        mock_ctx = MockContext()
        custom_path = "~/custom/lza-config"

        with (
            patch(
                "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
            ) as mock_session,
            patch("os.path.expanduser", return_value="/expanded/custom/path"),
            patch("os.path.exists", return_value=False),
        ):
            mock_sts_client = MockSTSClient()
            mock_session_obj = Mock()
            mock_session_obj.client.return_value = mock_sts_client
            mock_session.return_value = mock_session_obj

            result = await tool_validate_configuration_from_share(mock_ctx, custom_path)

            assert result["valid"] is False
            assert "config.zip not found" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_client_error(self):
        """Test validation with AWS client error."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
        ) as mock_session:
            mock_sts_client = Mock()
            mock_sts_client.get_caller_identity.side_effect = ClientError(
                error_response={
                    "Error": {"Code": "AccessDenied", "Message": "Access denied"}
                },
                operation_name="GetCallerIdentity",
            )
            mock_session_obj = Mock()
            mock_session_obj.client.return_value = mock_sts_client
            mock_session.return_value = mock_session_obj

            result = await tool_validate_configuration_from_share(mock_ctx)

            assert result["valid"] is False
            assert "AWS credentials validation failed" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_unexpected_error(self):
        """Test validation with unexpected error."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session",
            side_effect=Exception("Unexpected error"),
        ):
            result = await tool_validate_configuration_from_share(mock_ctx)

            assert result["valid"] is False
            assert "AWS connectivity required for LZA validation" in result["message"]
            assert (
                "AWS credentials validation failed: Unexpected error"
                in result["errors"][0]["message"]
            )

    @pytest.mark.asyncio
    async def test_validate_configuration_from_share_workflow_tracking(self):
        """Test that workflow status is properly tracked."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validate_configuration_share.get_aws_session"
        ) as mock_session:
            mock_session.side_effect = NoCredentialsError()

            result = await tool_validate_configuration_from_share(mock_ctx)

            # Check workflow status fields are present
            assert "discovered_configs" in result
            assert "selected_config" in result
            assert "zip_created" in result
            assert "zip_cleaned" in result
            assert "steps_completed" in result
            assert isinstance(result["steps_completed"], list)
