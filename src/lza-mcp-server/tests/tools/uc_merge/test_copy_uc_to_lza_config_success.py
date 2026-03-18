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

"""Unit tests for copy_uc_to_lza_config success scenarios."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


class TestCopyUcToLzaConfigSuccess:
    """Test successful copy operations."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_successful_copy_with_files(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test successful copy operation with files."""
        # Arrange
        mock_ctx = AsyncMock()

        # Create temporary directories
        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test files in session directory
            (session_path / "file1.yaml").write_text("content1")
            (session_path / "file2.yaml").write_text("content2")
            (session_path / "subdir").mkdir()
            (session_path / "subdir" / "file3.yaml").write_text("content3")

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["session_id"] == "test-session-id"
            assert result["files_copied"] == 3
            assert result["directories_created"] == 1
            assert "putLzaConfiguration()" in result["next_steps"]

            # Verify files were copied
            assert (lza_path / "file1.yaml").exists()
            assert (lza_path / "file2.yaml").exists()
            assert (lza_path / "subdir" / "file3.yaml").exists()
            assert (lza_path / "file1.yaml").read_text() == "content1"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_successful_copy_overwrites_existing_files(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test that copy operation overwrites existing files."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test file in session directory
            (session_path / "file1.yaml").write_text("new content")

            # Create existing file in LZA directory
            (lza_path / "file1.yaml").write_text("old content")

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == 1
            assert (lza_path / "file1.yaml").read_text() == "new content"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_successful_copy_skips_metadata_files(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test that metadata files are skipped during copy."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create test files including metadata
            (session_path / "file1.yaml").write_text("content1")
            (session_path / ".session_metadata.json").write_text('{"test": "data"}')

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == 1
            assert (lza_path / "file1.yaml").exists()
            assert not (lza_path / ".session_metadata.json").exists()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_successful_copy_creates_nested_directories(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test that nested directory structures are created."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            # Create nested directory structure
            (session_path / "level1" / "level2" / "level3").mkdir(parents=True)
            (session_path / "level1" / "level2" / "level3" / "file.yaml").write_text(
                "nested content"
            )

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == 1
            assert result["directories_created"] == 3
            assert (lza_path / "level1" / "level2" / "level3" / "file.yaml").exists()

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.SessionManager")
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config.get_extracted_lza_config_path"
    )
    async def test_successful_copy_with_empty_session_directory(
        self, mock_get_path, mock_session_manager_class
    ):
        """Test copy operation with empty session directory."""
        # Arrange
        mock_ctx = AsyncMock()

        with (
            tempfile.TemporaryDirectory() as session_dir,
            tempfile.TemporaryDirectory() as lza_dir,
        ):
            session_path = Path(session_dir)
            lza_path = Path(lza_dir)

            mock_session_manager = Mock()
            mock_session_manager.validate_session.return_value = (True, None)
            mock_session_manager.get_session_path.return_value = session_path
            mock_session_manager_class.return_value = mock_session_manager
            mock_get_path.return_value = lza_path

            # Act
            result = await copy_uc_to_lza_config(mock_ctx, "test-session-id")

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == 0
            assert result["directories_created"] == 0
