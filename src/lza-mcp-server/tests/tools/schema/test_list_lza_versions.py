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

"""Unit tests for list_lza_supported_versions tool."""

import pytest
import os
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.schema.list_lza_versions import (
    tool_list_lza_supported_versions,
)


class MockContext:
    """Mock context for testing."""

    async def info(self, message):
        pass

    async def error(self, message):
        pass


class TestListLzaSupportedVersions:
    """Test cases for list_lza_supported_versions tool."""

    @pytest.mark.asyncio
    async def test_list_versions_success(self):
        """Test successful listing of LZA versions."""
        mock_context = MockContext()

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["v1.13.0", "v1.12.0", "latest"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink") as mock_islink,
            patch("os.readlink", return_value="v1.13.0"),
            patch("os.path.getsize", return_value=1024 * 1024 * 5),  # 5MB
        ):
            # Configure islink to return True only for 'latest'
            mock_islink.side_effect = lambda path: path.endswith("latest")

            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        assert len(result["versions"]) == 3
        assert result["latest_version"] == "v1.13.0"
        assert "schemas_directory" in result
        assert "usage_hint" in result

    @pytest.mark.asyncio
    async def test_list_versions_with_combined_json(self):
        """Test listing versions with combined.json file information."""
        mock_context = MockContext()

        def mock_exists(path):
            # Return True for base directory and combined.json files
            return "/app/json-schemas" in path

        with (
            patch("os.path.exists", side_effect=mock_exists),
            patch("os.listdir", return_value=["v1.13.0", "v1.12.0"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", return_value=False),
            patch("os.path.getsize", return_value=1024 * 1024 * 3),  # 3MB
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        assert len(result["versions"]) == 2
        # Check that versions have schema information
        for version in result["versions"]:
            assert "has_schemas" in version
            assert "status" in version
            if version["has_schemas"]:
                assert "schema_size_mb" in version

    @pytest.mark.asyncio
    async def test_list_versions_schemas_directory_not_found(self):
        """Test handling when schemas directory doesn't exist."""
        mock_context = MockContext()

        with patch("os.path.exists", return_value=False):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is False
        assert result["error"] == "Schemas directory not found"
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_list_versions_empty_directory(self):
        """Test handling when schemas directory is empty."""
        mock_context = MockContext()

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=[]),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        assert len(result["versions"]) == 0
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_list_versions_only_files_no_directories(self):
        """Test handling when schemas directory contains only files."""
        mock_context = MockContext()

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["file1.txt", "file2.json"]),
            patch("os.path.isdir", return_value=False),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        assert len(result["versions"]) == 0

    @pytest.mark.asyncio
    async def test_list_versions_with_symlink(self):
        """Test handling of symlinked version directories."""
        mock_context = MockContext()

        def mock_islink(path):
            return path.endswith("latest")

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["v1.13.0", "latest"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", side_effect=mock_islink),
            patch("os.readlink", return_value="v1.13.0"),
            patch("os.path.getsize", return_value=1024 * 1024 * 2),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        # Find the 'latest' version entry
        latest_entry = next(v for v in result["versions"] if v["version"] == "latest")
        assert latest_entry["is_symlink"] is True
        assert latest_entry["symlink_target"] == "v1.13.0"
        assert result["latest_version"] == "v1.13.0"

    @pytest.mark.asyncio
    async def test_list_versions_incomplete_schemas(self):
        """Test handling of versions without combined.json."""
        mock_context = MockContext()

        def mock_exists(path):
            # Base directory exists, but combined.json doesn't
            if path.endswith("combined.json"):
                return False
            return "/app/json-schemas" in path

        with (
            patch("os.path.exists", side_effect=mock_exists),
            patch("os.listdir", return_value=["v1.13.0"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", return_value=False),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        assert len(result["versions"]) == 1
        assert result["versions"][0]["has_schemas"] is False
        assert result["versions"][0]["status"] == "incomplete"

    @pytest.mark.asyncio
    async def test_list_versions_listdir_error(self):
        """Test handling when listing directory fails."""
        mock_context = MockContext()

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", side_effect=PermissionError("Permission denied")),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is False
        assert "Failed to list schemas directory" in result["error"]

    @pytest.mark.asyncio
    async def test_list_versions_getsize_error(self):
        """Test handling when getting file size fails."""
        mock_context = MockContext()

        def mock_getsize(path):
            raise OSError("Cannot access file")

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["v1.13.0"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", return_value=False),
            patch("os.path.getsize", side_effect=mock_getsize),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        # Should still succeed but without size information
        assert len(result["versions"]) == 1
        assert "schema_size_mb" not in result["versions"][0]

    @pytest.mark.asyncio
    async def test_list_versions_readlink_error(self):
        """Test handling when reading symlink fails."""
        mock_context = MockContext()

        def mock_islink(path):
            return path.endswith("latest")

        def mock_readlink(path):
            raise OSError("Cannot read symlink")

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["latest"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", side_effect=mock_islink),
            patch("os.readlink", side_effect=mock_readlink),
            patch("os.path.getsize", return_value=1024 * 1024),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        # Should still succeed but without symlink target
        assert len(result["versions"]) == 1
        assert result["versions"][0]["is_symlink"] is True
        assert "symlink_target" not in result["versions"][0]

    @pytest.mark.asyncio
    async def test_list_versions_sorting(self):
        """Test that versions are sorted correctly with 'latest' first."""
        mock_context = MockContext()

        def mock_islink(path):
            return path.endswith("latest")

        with (
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["v1.12.0", "v1.13.0", "latest", "v1.11.0"]),
            patch("os.path.isdir", return_value=True),
            patch("os.path.islink", side_effect=mock_islink),
            patch("os.readlink", return_value="v1.13.0"),
            patch("os.path.getsize", return_value=1024 * 1024),
        ):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is True
        # 'latest' should be first
        assert result["versions"][0]["version"] == "latest"
        # Rest should be sorted
        version_names = [v["version"] for v in result["versions"]]
        assert version_names[0] == "latest"

    @pytest.mark.asyncio
    async def test_list_versions_unexpected_error(self):
        """Test handling of unexpected errors."""
        mock_context = MockContext()

        with patch("os.path.exists", side_effect=Exception("Unexpected error")):
            result = await tool_list_lza_supported_versions(mock_context)

        assert result["success"] is False
        assert "Error listing LZA versions" in result["error"]
        assert "unexpected error" in result["message"].lower()
