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

"""Unit tests for ConfigurationManager configuration discovery."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    ConfigurationManager,
)


class TestDiscoverConfigurations:
    """Test configuration discovery in workspace."""

    @pytest.mark.asyncio
    async def test_discover_single_configuration(self):
        """Test discovery of single LZA configuration."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "lza-config"
            config_dir.mkdir()
            (config_dir / "accounts-config.yaml").write_text("test")
            (config_dir / "organization-config.yaml").write_text("test")

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 1
            assert str(config_dir) in result
            mock_ctx.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_multiple_configurations(self):
        """Test discovery of multiple LZA configurations."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create first config
            config1 = Path(temp_dir) / "config1"
            config1.mkdir()
            (config1 / "accounts-config.yaml").write_text("test")
            (config1 / "organization-config.yaml").write_text("test")
            
            # Create second config
            config2 = Path(temp_dir) / "config2"
            config2.mkdir()
            (config2 / "accounts-config.yaml").write_text("test")
            (config2 / "organization-config.yaml").write_text("test")

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 2
            assert str(config1) in result
            assert str(config2) in result

    @pytest.mark.asyncio
    async def test_discover_nested_configurations(self):
        """Test discovery of nested LZA configurations."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            nested = Path(temp_dir) / "workspace" / "configs" / "lza"
            nested.mkdir(parents=True)
            (nested / "accounts-config.yaml").write_text("test")
            (nested / "organization-config.yaml").write_text("test")

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 1
            assert str(nested) in result

    @pytest.mark.asyncio
    async def test_discover_no_configurations(self):
        """Test discovery when no configurations exist."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some files but not LZA configs
            (Path(temp_dir) / "random.txt").write_text("test")

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 0
            assert result == []

    @pytest.mark.asyncio
    async def test_discover_incomplete_configuration(self):
        """Test discovery ignores incomplete configurations."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory with only one required file
            incomplete = Path(temp_dir) / "incomplete"
            incomplete.mkdir()
            (incomplete / "accounts-config.yaml").write_text("test")
            # Missing organization-config.yaml

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_discover_with_extra_files(self):
        """Test discovery finds configs even with extra files present."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "accounts-config.yaml").write_text("test")
            (config_dir / "organization-config.yaml").write_text("test")
            (config_dir / "extra-file.yaml").write_text("extra")
            (config_dir / "README.md").write_text("readme")

            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 1
            assert str(config_dir) in result

    @pytest.mark.asyncio
    async def test_discover_empty_directory(self):
        """Test discovery in empty directory."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Act
            result = await manager.discover_configurations(mock_ctx, temp_dir)

            # Assert
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_discover_nonexistent_path(self):
        """Test discovery with nonexistent path returns empty list."""
        # Arrange
        manager = ConfigurationManager()
        mock_ctx = AsyncMock()
        workspace_path = "/nonexistent/path/that/does/not/exist"

        # Act
        result = await manager.discover_configurations(mock_ctx, workspace_path)

        # Assert - os.walk doesn't raise exception, just returns empty
        assert len(result) == 0
