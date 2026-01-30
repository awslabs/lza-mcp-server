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

"""Unit tests for copy_uc_to_lza_config cleanup operations."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


class TestCopyUcToLzaConfigCleanup:
    """Test cleanup operations after successful copy."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_session_cleanup_after_successful_copy(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test that session directory is cleaned up after successful copy."""
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

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["session_cleaned_up"] is True
            assert not session_path.exists()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_cleanup_failure_does_not_fail_operation(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test that cleanup failure does not fail the overall operation."""
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

            # Simulate cleanup failure by making directory read-only after copy
            # We'll patch rmtree to raise an error
            with patch(
                "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.shutil.rmtree"
            ) as mock_rmtree:
                mock_rmtree.side_effect = PermissionError("Cannot delete directory")

                # Act
                result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == 1
            # Verify warning was logged
            mock_ctx.warning.assert_called_once()
            assert "Could not remove session directory" in str(
                mock_ctx.warning.call_args
            )

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.shutil.rmtree")
    async def test_cleanup_logs_info_messages(
        self, mock_rmtree, mock_get_path, mock_session_manager_class
    ):
        """Test that cleanup logs appropriate info messages."""
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

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True

            # Verify info messages were logged
            info_calls = [str(call) for call in mock_ctx.info.call_args_list]
            assert any("Cleaning up session directory" in call for call in info_calls)
            assert any("Session directory removed" in call for call in info_calls)
