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

"""Unit tests for copy_uc_to_lza_config validation."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


class TestCopyUcToLzaConfigValidation:
    """Test validation logic for copy_uc_to_lza_config."""

    @pytest.mark.asyncio
    async def test_missing_session_id(self):
        """Test error when session_id is not provided."""
        # Arrange
        mock_ctx = AsyncMock()

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "MISSING_SESSION_ID"
        assert "Session ID is required" in result["error"]
        assert result["category"] == "validation"
        assert "start_uc_merge_session()" in result["next_steps"]

    @pytest.mark.asyncio
    async def test_missing_session_id_none(self):
        """Test error when session_id is None."""
        # Arrange
        mock_ctx = AsyncMock()

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, None)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "MISSING_SESSION_ID"
        assert "Session ID is required" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    async def test_invalid_session(self, mock_session_manager_class):
        """Test error when session is invalid."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_session_manager = Mock()
        mock_session_manager.validate_session.return_value = (
            False,
            "Session not found",
        )
        mock_session_manager_class.return_value = mock_session_manager

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "invalid-session-id")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION"
        assert "Session not found" in result["error"]
        assert result["category"] == "validation"
        assert "invalid-session-id" in result["context"]["session_id"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_lza_config_path_not_found(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test error when LZA config path is None."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_session_manager = Mock()
        mock_session_manager.validate_session.return_value = (True, None)
        mock_session_manager.get_session_path.return_value = Path("/tmp/session")
        mock_session_manager_class.return_value = mock_session_manager
        mock_get_path.return_value = None

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "valid-session-id")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "LZA_CONFIG_NOT_FOUND"
        assert "LZA configuration directory not found" in result["error"]
        assert "getLzaConfiguration()" in result["next_steps"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_lza_config_directory_does_not_exist(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test error when LZA config directory does not exist."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_session_manager = Mock()
        mock_session_manager.validate_session.return_value = (True, None)
        mock_session_manager.get_session_path.return_value = Path("/tmp/session")
        mock_session_manager_class.return_value = mock_session_manager

        mock_lza_path = Mock(spec=Path)
        mock_lza_path.exists.return_value = False
        mock_lza_path.__str__ = Mock(return_value="/tmp/lza-config")
        mock_get_path.return_value = mock_lza_path

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "valid-session-id")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "LZA_CONFIG_NOT_FOUND"
        assert "does not exist" in result["error"]
        assert result["category"] == "file_not_found"
        assert "/tmp/lza-config" in result["context"]["lza_config_path"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_session_directory_does_not_exist(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test error when session directory does not exist."""
        # Arrange
        mock_ctx = AsyncMock()

        mock_session_path = Mock(spec=Path)
        mock_session_path.exists.return_value = False
        mock_session_path.__str__ = Mock(return_value="/tmp/session")

        mock_session_manager = Mock()
        mock_session_manager.validate_session.return_value = (True, None)
        mock_session_manager.get_session_path.return_value = mock_session_path
        mock_session_manager_class.return_value = mock_session_manager

        mock_lza_path = Mock(spec=Path)
        mock_lza_path.exists.return_value = True
        mock_get_path.return_value = mock_lza_path

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "valid-session-id")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "SESSION_NOT_FOUND"
        assert "Session directory does not exist" in result["error"]
        assert result["category"] == "file_not_found"
        assert "/tmp/session" in result["context"]["session_path"]
