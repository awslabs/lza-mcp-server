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

"""Unit tests for get_uc_releases error handling."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_releases import tool_get_uc_releases


@pytest.mark.unit
@pytest.mark.uc_merge
class TestGetUCReleasesErrors:
    """Test suite for get_uc_releases error handling."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing."""
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_permission_error_accessing_directory(self, mock_context, tmp_path):
        """Test handling of PermissionError when accessing UC directory."""
        # Create test UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        # Mock Path.iterdir to raise PermissionError
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = PermissionError("Permission denied")

                result = await tool_get_uc_releases(mock_context)

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Permission denied" in result["error"]
        assert result["error_code"] == "PERMISSION_DENIED"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0
        assert "next_steps" in result
        assert "administrator" in result["next_steps"]

        # Verify error was logged
        mock_context.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_unexpected_error_during_discovery(self, mock_context, tmp_path):
        """Test handling of unexpected errors during release discovery."""
        # Create test UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        # Mock Path.iterdir to raise unexpected exception
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = RuntimeError("Unexpected filesystem error")

                result = await tool_get_uc_releases(mock_context)

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert "Unexpected filesystem error" in result["error"]
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0
        assert "next_steps" in result

        # Verify error was logged
        mock_context.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_os_error_during_directory_scan(self, mock_context, tmp_path):
        """Test handling of OSError during directory scanning."""
        # Create test UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        # Mock Path.iterdir to raise OSError
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = OSError("I/O error reading directory")

                result = await tool_get_uc_releases(mock_context)

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert result["error_code"] == "UNEXPECTED_ERROR"

    @pytest.mark.asyncio
    async def test_permission_error_includes_troubleshooting_steps(
        self, mock_context, tmp_path
    ):
        """Test that PermissionError response includes helpful troubleshooting."""
        # Create test UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        # Mock Path.iterdir to raise PermissionError
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = PermissionError("Access denied")

                result = await tool_get_uc_releases(mock_context)

        # Verify troubleshooting guidance
        assert "troubleshooting" in result
        troubleshooting = result["troubleshooting"]
        assert any("permission" in step.lower() for step in troubleshooting)
        assert any(
            "container" in step.lower() or "access" in step.lower()
            for step in troubleshooting
        )

    @pytest.mark.asyncio
    async def test_unexpected_error_includes_troubleshooting_steps(
        self, mock_context, tmp_path
    ):
        """Test that unexpected errors include troubleshooting guidance."""
        # Create test UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        # Mock Path.iterdir to raise unexpected exception
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = ValueError("Invalid directory structure")

                result = await tool_get_uc_releases(mock_context)

        # Verify troubleshooting guidance
        assert "troubleshooting" in result
        troubleshooting = result["troubleshooting"]
        assert any("log" in step.lower() for step in troubleshooting)
        assert any(
            "repository" in step.lower() or "structure" in step.lower()
            for step in troubleshooting
        )
