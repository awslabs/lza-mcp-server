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

"""Unit tests for S3UploadUtils configuration discovery."""

import pytest
from unittest.mock import patch, AsyncMock

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError


class TestDiscoverAndSelectConfiguration:
    """Test configuration discovery and selection."""

    @pytest.mark.asyncio
    async def test_discovery_with_valid_provided_path(self):
        """Test discovery with valid provided configuration path."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        config_path = "/path/to/config"

        utils.config_manager.validate_configuration_path = AsyncMock(return_value=True)

        # Act
        result = await utils._discover_and_select_configuration(
            mock_ctx, config_path=config_path
        )

        # Assert
        assert result["success"] is True
        assert result["selected_config"] == config_path
        assert result["discovery_method"] == "provided_path"
        utils.config_manager.validate_configuration_path.assert_called_once_with(
            config_path
        )

    @pytest.mark.asyncio
    async def test_discovery_with_invalid_provided_path(self):
        """Test discovery with invalid provided configuration path."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        config_path = "/invalid/path"

        error = S3UploadError(
            message="Invalid configuration path",
            error_code="INVALID_PATH",
            category="VALIDATION",
        )
        utils.config_manager.validate_configuration_path = AsyncMock(side_effect=error)

        # Act
        result = await utils._discover_and_select_configuration(
            mock_ctx, config_path=config_path
        )

        # Assert
        assert result["success"] is False
        assert result["message"] == "Invalid configuration path provided"
        assert result["error_code"] == "INVALID_PATH"

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.select_configuration"
    )
    async def test_discovery_workspace_search_success(self, mock_select_config):
        """Test successful workspace configuration discovery."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        workspace_path = "/workspace"

        discovered_configs = ["/workspace/config1", "/workspace/config2"]
        selected_config = "/workspace/config1"

        utils.config_manager.discover_configurations = AsyncMock(
            return_value=discovered_configs
        )
        mock_select_config.return_value = selected_config

        # Act
        result = await utils._discover_and_select_configuration(
            mock_ctx, workspace_path=workspace_path
        )

        # Assert
        assert result["success"] is True
        assert result["selected_config"] == selected_config
        assert result["discovered_configs"] == discovered_configs
        assert result["discovery_method"] == "workspace_search"
        utils.config_manager.discover_configurations.assert_called_once_with(
            mock_ctx, workspace_path
        )
        mock_select_config.assert_called_once_with(mock_ctx, discovered_configs)

    @pytest.mark.asyncio
    async def test_discovery_no_configurations_found(self):
        """Test discovery when no configurations are found."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()
        workspace_path = "/empty/workspace"

        utils.config_manager.discover_configurations = AsyncMock(return_value=[])

        # Act
        result = await utils._discover_and_select_configuration(
            mock_ctx, workspace_path=workspace_path
        )

        # Assert
        assert result["success"] is False
        assert "No valid LZA configurations found" in result["error"]
        assert result["workspace_searched"] == workspace_path
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_discovery_handles_s3_upload_error(self):
        """Test discovery handles S3UploadError exceptions."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()

        error = S3UploadError(
            message="Discovery failed",
            error_code="DISCOVERY_ERROR",
            category="VALIDATION",
        )
        utils.config_manager.discover_configurations = AsyncMock(side_effect=error)

        # Act
        result = await utils._discover_and_select_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "DISCOVERY_ERROR"
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_handles_unexpected_exception(self):
        """Test discovery handles unexpected exceptions."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()

        utils.config_manager.discover_configurations = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        # Act
        result = await utils._discover_and_select_configuration(mock_ctx)

        # Assert
        assert result["success"] is False
        assert "Configuration discovery failed" in result["error"]
        assert result["error_code"] is not None
        assert "troubleshooting" in result
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_uses_default_workspace_path(self):
        """Test discovery uses default workspace path when not provided."""
        # Arrange
        utils = S3UploadUtils()
        mock_ctx = AsyncMock()

        utils.config_manager.discover_configurations = AsyncMock(return_value=[])

        # Act
        result = await utils._discover_and_select_configuration(mock_ctx)

        # Assert
        utils.config_manager.discover_configurations.assert_called_once_with(
            mock_ctx, "."
        )
