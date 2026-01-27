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

"""Unit tests for ConfigurationManager ZIP creation."""

import pytest
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    create_configuration_zip,
)


class TestCreateConfigurationZip:
    """Test ZIP file creation operations."""

    @pytest.mark.asyncio
    async def test_create_zip_success(self):
        """Test successful ZIP creation."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            (config_path / "accounts-config.yaml").write_text("test: data")
            (config_path / "organization-config.yaml").write_text("org: data")
            
            output_path = Path(temp_dir) / "output.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), str(output_path)
            )

            # Assert
            assert result["success"] is True
            assert result["zip_path"] == str(output_path)
            assert result["file_size"] > 0
            assert os.path.exists(output_path)
            
            # Verify ZIP contents
            with zipfile.ZipFile(output_path, "r") as zipf:
                names = zipf.namelist()
                assert "accounts-config.yaml" in names
                assert "organization-config.yaml" in names

    @pytest.mark.asyncio
    async def test_create_zip_with_subdirectories(self):
        """Test ZIP creation with nested directory structure."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            
            # Create nested structure
            (config_path / "accounts-config.yaml").write_text("test")
            subdir = config_path / "subdir"
            subdir.mkdir()
            (subdir / "nested.yaml").write_text("nested")
            
            output_path = Path(temp_dir) / "output.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), str(output_path)
            )

            # Assert
            assert result["success"] is True
            with zipfile.ZipFile(output_path, "r") as zipf:
                names = zipf.namelist()
                assert "accounts-config.yaml" in names
                assert "subdir/nested.yaml" in names

    @pytest.mark.asyncio
    async def test_create_zip_nonexistent_config_path(self):
        """Test ZIP creation with nonexistent config path."""
        # Arrange
        mock_ctx = AsyncMock()
        config_path = "/nonexistent/path"
        output_path = "/tmp/output.zip"

        # Act
        result = await create_configuration_zip(mock_ctx, config_path, output_path)

        # Assert
        assert result["success"] is False
        assert "does not exist" in result["error"]
        mock_ctx.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_zip_config_path_is_file(self):
        """Test ZIP creation when config path is a file, not directory."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            config_path = temp_file.name
        
        output_path = "/tmp/output.zip"

        try:
            # Act
            result = await create_configuration_zip(
                mock_ctx, config_path, output_path
            )

            # Assert
            assert result["success"] is False
            assert "not a directory" in result["error"]
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_create_zip_invalid_output_path(self):
        """Test ZIP creation with invalid output path."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            (config_path / "test.yaml").write_text("test")
            
            # Use invalid characters in path
            output_path = "\x00invalid/path.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), output_path
            )

            # Assert
            assert result["success"] is False
            assert "Invalid output file path" in result["error"]

    @pytest.mark.asyncio
    async def test_create_zip_creates_output_directory(self):
        """Test ZIP creation creates output directory if it doesn't exist."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            (config_path / "test.yaml").write_text("test")
            
            # Output path in non-existent directory
            output_path = Path(temp_dir) / "new_dir" / "subdir" / "output.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), str(output_path)
            )

            # Assert
            assert result["success"] is True
            assert os.path.exists(output_path)
            assert os.path.exists(output_path.parent)

    @pytest.mark.asyncio
    async def test_create_zip_empty_directory(self):
        """Test ZIP creation with empty directory."""
        # Arrange
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            
            output_path = Path(temp_dir) / "output.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), str(output_path)
            )

            # Assert
            assert result["success"] is True
            assert os.path.exists(output_path)
            
            # Verify ZIP is empty
            with zipfile.ZipFile(output_path, "r") as zipf:
                assert len(zipf.namelist()) == 0

    @pytest.mark.asyncio
    @patch("zipfile.ZipFile")
    async def test_create_zip_handles_zipfile_error(self, mock_zipfile):
        """Test ZIP creation handles zipfile errors."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_zipfile.side_effect = Exception("ZIP error")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config"
            config_path.mkdir()
            output_path = Path(temp_dir) / "output.zip"

            # Act
            result = await create_configuration_zip(
                mock_ctx, str(config_path), str(output_path)
            )

            # Assert
            assert result["success"] is False
            assert "Error creating ZIP" in result["error"]
