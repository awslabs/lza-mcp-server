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

"""Unit tests for ConfigurationManager configuration selection."""

import pytest
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    select_configuration,
)


class TestSelectConfiguration:
    """Test configuration selection logic."""

    @pytest.mark.asyncio
    async def test_select_single_configuration(self):
        """Test selection with single configuration."""
        # Arrange
        mock_ctx = AsyncMock()
        discovered_configs = ["/path/to/config"]

        # Act
        result = await select_configuration(mock_ctx, discovered_configs)

        # Assert
        assert result == "/path/to/config"
        mock_ctx.info.assert_called_once()
        assert "single discovered" in str(mock_ctx.info.call_args)

    @pytest.mark.asyncio
    async def test_select_multiple_configurations(self):
        """Test selection with multiple configurations returns first."""
        # Arrange
        mock_ctx = AsyncMock()
        discovered_configs = ["/path/to/config1", "/path/to/config2", "/path/to/config3"]

        # Act
        result = await select_configuration(mock_ctx, discovered_configs)

        # Assert
        assert result == "/path/to/config1"
        mock_ctx.info.assert_called_once()
        assert "Multiple configurations" in str(mock_ctx.info.call_args)

    @pytest.mark.asyncio
    async def test_select_empty_list_raises_error(self):
        """Test selection with empty list raises ValueError."""
        # Arrange
        mock_ctx = AsyncMock()
        discovered_configs = []

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await select_configuration(mock_ctx, discovered_configs)
        
        assert "No LZA configurations available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_select_none_raises_error(self):
        """Test selection with None raises error."""
        # Arrange
        mock_ctx = AsyncMock()
        discovered_configs = None

        # Act & Assert
        with pytest.raises((ValueError, TypeError)):
            await select_configuration(mock_ctx, discovered_configs)

    @pytest.mark.asyncio
    async def test_select_preserves_path_format(self):
        """Test selection preserves original path format."""
        # Arrange
        mock_ctx = AsyncMock()
        original_path = "/workspace/lza-config/production"
        discovered_configs = [original_path]

        # Act
        result = await select_configuration(mock_ctx, discovered_configs)

        # Assert
        assert result == original_path
        assert isinstance(result, str)
