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

"""Unit tests for ConfigurationManager ZIP cleanup."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    cleanup_configuration_zip,
)


class TestCleanupConfigurationZip:
    """Test ZIP file cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_existing_file(self):
        """Test cleanup of existing ZIP file."""
        # Arrange
        mock_ctx = AsyncMock()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            zip_path = temp_file.name

        # Act
        result = await cleanup_configuration_zip(mock_ctx, zip_path)

        # Assert
        assert result["success"] is True
        assert "cleaned up" in result["message"].lower()
        assert not os.path.exists(zip_path)
        mock_ctx.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self):
        """Test cleanup when file doesn't exist."""
        # Arrange
        mock_ctx = AsyncMock()
        zip_path = "/nonexistent/path/file.zip"

        # Act
        result = await cleanup_configuration_zip(mock_ctx, zip_path)

        # Assert
        assert result["success"] is True
        assert "already cleaned up" in result["message"]
        mock_ctx.info.assert_called_once()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("os.remove")
    async def test_cleanup_handles_permission_error(self, mock_remove, mock_exists):
        """Test cleanup handles permission errors."""
        # Arrange
        mock_ctx = AsyncMock()
        zip_path = "/protected/file.zip"
        mock_exists.return_value = True
        mock_remove.side_effect = PermissionError("Permission denied")

        # Act
        result = await cleanup_configuration_zip(mock_ctx, zip_path)

        # Assert
        assert result["success"] is False
        assert "Cleanup error" in result["error"]
        assert "Permission denied" in result["error"]
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("os.remove")
    async def test_cleanup_handles_os_error(self, mock_remove, mock_exists):
        """Test cleanup handles OS errors."""
        # Arrange
        mock_ctx = AsyncMock()
        zip_path = "/path/file.zip"
        mock_exists.return_value = True
        mock_remove.side_effect = OSError("Disk error")

        # Act
        result = await cleanup_configuration_zip(mock_ctx, zip_path)

        # Assert
        assert result["success"] is False
        assert "Cleanup error" in result["error"]
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_relative_path(self):
        """Test cleanup with relative path."""
        # Arrange
        mock_ctx = AsyncMock()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            zip_path = temp_file.name
        
        # Get relative path
        rel_path = os.path.relpath(zip_path)

        # Act
        result = await cleanup_configuration_zip(mock_ctx, rel_path)

        # Assert
        assert result["success"] is True
        assert not os.path.exists(zip_path)
