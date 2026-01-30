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

"""Unit tests for copy_uc_to_lza_config error handling."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


class TestCopyUcToLzaConfigErrors:
    """Test error handling for copy operations."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.shutil.copy2")
    async def test_permission_error_during_copy(
        self, mock_copy2, mock_get_path, mock_session_manager_class
    ):
        """Test handling of permission errors during copy."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test file
            (session_path / "file1.yaml").write_text("content1")

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Simulate permission error
            mock_copy2.side_effect = PermissionError("Permission denied")

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is False
            assert result["error_code"] == "ACCESS_DENIED"
            assert "Permission denied" in result["error"]
            assert result["category"] == "file_operation"
            assert "file system permissions" in result["troubleshooting"][0]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.shutil.copy2")
    async def test_os_error_during_copy(
        self, mock_copy2, mock_get_path, mock_session_manager_class
    ):
        """Test handling of OS errors during copy."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test file
            (session_path / "file1.yaml").write_text("content1")

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Simulate OS error
            mock_copy2.side_effect = OSError("Disk full")

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is False
            assert result["error_code"] == "FILE_OPERATION_ERROR"
            assert "File system error" in result["error"]
            assert "Disk full" in result["error"]
            assert result["category"] == "file_operation"
            assert "disk space" in result["troubleshooting"][0]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.shutil.copy2")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.categorize_uc_merge_error"
    )
    async def test_generic_exception_during_copy(
        self, mock_categorize, mock_copy2, mock_get_path, mock_session_manager_class
    ):
        """Test handling of generic exceptions during copy."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test file
            (session_path / "file1.yaml").write_text("content1")

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Simulate generic exception
            mock_copy2.side_effect = ValueError("Unexpected error")
            mock_categorize.return_value = {
                "error_code": "UNEXPECTED_ERROR",
                "category": "FILE_OPERATION",
                "troubleshooting": ["Check system logs"],
            }

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is False
            assert result["error_code"] == "UNEXPECTED_ERROR"
            assert "Failed to copy files" in result["error"]
            assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    async def test_unexpected_error_in_outer_try_block(
        self, mock_session_manager_class
    ):
        """Test handling of unexpected errors in outer try block."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_session_manager_class.side_effect = RuntimeError("Unexpected error")

        # Act
        result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "Unexpected error during copy operation" in result["error"]
        assert result["category"] == "file_operation"
