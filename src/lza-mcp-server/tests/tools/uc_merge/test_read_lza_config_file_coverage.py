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

"""Additional coverage tests for read_lza_config_file tool."""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file import (
    read_lza_config_file,
)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.mark.unit
@pytest.mark.uc_merge
class TestReadLzaConfigFileCoverage:
    """Additional coverage tests for read_lza_config_file tool."""

    @pytest.mark.asyncio
    async def test_unicode_decode_error(self, mock_ctx, tmp_path, monkeypatch):
        """Test handling of Unicode decode errors.

        Covers lines 200-214: UnicodeDecodeError exception handling
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create a file with invalid UTF-8 bytes
        test_file = config_dir / "test.yaml"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        # Patch the base path
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.LZA_CONFIG_BASE_PATH",
            tmp_path,
        )

        # Run the tool
        result = await read_lza_config_file(mock_ctx, "test.yaml")

        # Assertions
        assert result["success"] is False
        assert result["error_code"] == "ENCODING_ERROR"
        assert "Failed to decode file as UTF-8" in result["error"]
        assert "troubleshooting" in result
        assert "context" in result
        assert result["context"]["file_path"] == "test.yaml"

    @pytest.mark.asyncio
    async def test_permission_error(self, mock_ctx, tmp_path, monkeypatch):
        """Test handling of permission errors.

        Covers lines 215-229: PermissionError exception handling
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create a test file
        test_file = config_dir / "test.yaml"
        test_file.write_text("test: content")

        # Patch the base path
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.LZA_CONFIG_BASE_PATH",
            tmp_path,
        )

        # Mock read_text to raise PermissionError
        with patch.object(Path, "read_text") as mock_read:
            mock_read.side_effect = PermissionError("Access denied")

            # Run the tool
            result = await read_lza_config_file(mock_ctx, "test.yaml")

        # Assertions
        assert result["success"] is False
        assert result["error_code"] == "ACCESS_DENIED"
        assert "Permission denied" in result["error"]
        assert "troubleshooting" in result
        assert "context" in result
        assert result["context"]["file_path"] == "test.yaml"

    @pytest.mark.asyncio
    async def test_unexpected_error_reading_file(self, mock_ctx, tmp_path, monkeypatch):
        """Test handling of unexpected errors during file read.

        Covers lines 230-243: General exception handling
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create a test file
        test_file = config_dir / "test.yaml"
        test_file.write_text("test: content")

        # Patch the base path
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.LZA_CONFIG_BASE_PATH",
            tmp_path,
        )

        # Mock read_text to raise unexpected error
        with patch.object(Path, "read_text") as mock_read:
            mock_read.side_effect = RuntimeError("Unexpected filesystem error")

            # Run the tool
            result = await read_lza_config_file(mock_ctx, "test.yaml")

        # Assertions
        assert result["success"] is False
        assert "Failed to read file" in result["error"]
        assert "troubleshooting" in result
        assert "context" in result
        assert result["context"]["file_path"] == "test.yaml"
        assert result["context"]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_outer_exception_handler(self, mock_ctx, tmp_path, monkeypatch):
        """Test the outer exception handler (lines 243-245).

        Covers the top-level except block that catches unexpected errors
        before any file operations begin.
        """
        # Patch LZA_CONFIG_BASE_PATH to a valid path so the base_directory check passes
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)
        (config_dir / "test.yaml").write_text("content")

        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.LZA_CONFIG_BASE_PATH",
            tmp_path,
        )

        # Patch validate_path_security to raise an unexpected exception
        with patch(
            "awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file.validate_path_security",
            side_effect=RuntimeError("Unexpected system failure"),
        ):
            result = await read_lza_config_file(mock_ctx, "test.yaml")

        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "Unexpected system failure" in result["error"]
        assert "troubleshooting" in result
