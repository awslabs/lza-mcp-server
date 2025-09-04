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

"""Unit tests for cleanup validation zip module."""

import pytest
import os
import tempfile
from unittest.mock import patch, AsyncMock

from awslabs.lza_mcp_server.tools.validation.cleanup_validation_zip import (
    tool_cleanup_validation_zip,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class TestToolCleanupValidationZip:
    """Test cases for tool_cleanup_validation_zip function."""

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_success(self):
        """Test successful cleanup of existing ZIP file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await tool_cleanup_validation_zip(mock_ctx, temp_dir)

            assert result["success"] is True
            assert result["message"] == "ZIP file cleaned up successfully"
            assert result["zip_path"] == zip_path
            assert result["existed"] is True
            assert not os.path.exists(zip_path)  # File should be deleted

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_file_not_exists(self):
        """Test cleanup when ZIP file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await tool_cleanup_validation_zip(mock_ctx, temp_dir)

            assert result["success"] is True
            assert result["message"] == "ZIP file already cleaned up"
            assert result["existed"] is False

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_default_path(self):
        """Test cleanup with default share path."""
        mock_ctx = MockContext()

        with (
            patch("os.path.expanduser") as mock_expanduser,
            patch("os.path.exists", return_value=False),
        ):
            mock_expanduser.return_value = "/expanded/path"

            result = await tool_cleanup_validation_zip(mock_ctx)

            mock_expanduser.assert_called_once_with("~/Documents/lza-config")
            assert result["success"] is True
            assert result["existed"] is False

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_permission_error(self):
        """Test cleanup with permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.remove", side_effect=PermissionError("Permission denied")),
            ):
                result = await tool_cleanup_validation_zip(mock_ctx, temp_dir)

            assert result["success"] is False
            assert "Failed to clean up ZIP file" in result["error"]
            assert "Permission denied" in result["error"]
            assert "troubleshooting" in result
            assert len(result["troubleshooting"]) == 3

            # Verify context calls
            mock_ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_os_error(self):
        """Test cleanup with OS error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.remove", side_effect=OSError("File system error")),
            ):
                result = await tool_cleanup_validation_zip(mock_ctx, temp_dir)

            assert result["success"] is False
            assert "Failed to clean up ZIP file" in result["error"]
            assert "File system error" in result["error"]

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_path_expansion_error(self):
        """Test cleanup with path expansion error."""
        mock_ctx = MockContext()

        with patch("os.path.expanduser", side_effect=Exception("Path expansion error")):
            result = await tool_cleanup_validation_zip(mock_ctx)

            assert result["success"] is False
            assert "Failed to clean up ZIP file" in result["error"]
            assert "Path expansion error" in result["error"]

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_custom_share_path(self):
        """Test cleanup with custom share path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = "~/custom/lza-config"
            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.path.exists", return_value=False),
            ):
                result = await tool_cleanup_validation_zip(mock_ctx, custom_path)

            assert result["success"] is True
            assert result["existed"] is False

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_file_locked(self):
        """Test cleanup when file is locked by another process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            # Simulate file being locked
            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch(
                    "os.remove",
                    side_effect=OSError("The process cannot access the file"),
                ),
            ):
                result = await tool_cleanup_validation_zip(mock_ctx, temp_dir)

            assert result["success"] is False
            assert "troubleshooting" in result
            troubleshooting_text = " ".join(result["troubleshooting"])
            assert "locked by another process" in troubleshooting_text
