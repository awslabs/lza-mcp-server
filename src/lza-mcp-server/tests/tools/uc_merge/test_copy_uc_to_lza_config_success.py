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

"""Unit tests for copy_uc_to_lza_config success scenarios (workspace-based)."""

import os
import tempfile

import pytest
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)
from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager


def _make_wm(base_dir):
    adapter = LocalAdapter(base_dir=base_dir)
    return WorkspaceManager(storage=adapter)


class TestCopyUcToLzaConfigSuccess:
    """Test successful copy operations using workspace-based API."""

    @pytest.mark.asyncio
    async def test_successful_copy_with_files(self):
        """Test successful workspace-to-workspace copy."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            # Create UC workspace with files
            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "file1.yaml", b"content1")
            wm.write_file(uc_ws, "file2.yaml", b"content2")
            wm.write_file(uc_ws, "subdir/file3.yaml", b"content3")

            # Create LZA workspace
            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            assert result["uc_workspace_id"] == uc_ws
            assert result["lza_workspace_id"] == lza_ws
            assert result["files_copied"] == 3
            assert "putLzaConfiguration" in result["next_steps"]

            # Verify files were copied
            lza_files = set(wm.list_files(lza_ws))
            assert "file1.yaml" in lza_files
            assert "file2.yaml" in lza_files
            assert "subdir/file3.yaml" in lza_files
            assert wm.read_file(lza_ws, "file1.yaml") == b"content1"

    @pytest.mark.asyncio
    async def test_successful_copy_overwrites_existing_files(self):
        """Test that copy operation overwrites existing files."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "file1.yaml", b"new content")

            lza_ws = wm.create_workspace()
            wm.write_file(lza_ws, "file1.yaml", b"old content")

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            assert result["files_copied"] == 1
            assert wm.read_file(lza_ws, "file1.yaml") == b"new content"

    @pytest.mark.asyncio
    async def test_successful_copy_skips_metadata_files(self):
        """Test that .session_metadata.json is skipped during copy."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "file1.yaml", b"content1")
            wm.write_file(uc_ws, ".session_metadata.json", b'{"test": "data"}')

            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            assert result["files_copied"] == 1
            lza_files = set(wm.list_files(lza_ws))
            assert "file1.yaml" in lza_files
            assert ".session_metadata.json" not in lza_files

    @pytest.mark.asyncio
    async def test_successful_copy_creates_nested_directories(self):
        """Test that nested directory structures are preserved."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "level1/level2/level3/file.yaml", b"nested content")

            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            assert result["files_copied"] == 1
            assert result["directories_created"] >= 1
            assert (
                wm.read_file(lza_ws, "level1/level2/level3/file.yaml")
                == b"nested content"
            )

    @pytest.mark.asyncio
    async def test_successful_copy_with_empty_uc_workspace(self):
        """Test copy operation with empty UC workspace."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            assert result["files_copied"] == 0
            assert result["directories_created"] == 0

    @pytest.mark.asyncio
    async def test_successful_copy_with_path_prefix(self):
        """Test copy with optional path prefix for LZA workspace."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "file1.yaml", b"content1")
            wm.write_file(uc_ws, "subdir/file2.yaml", b"content2")

            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(
                mock_ctx, uc_ws, lza_ws, wm, path="config/uc"
            )

            assert result["success"] is True
            assert result["files_copied"] == 2
            lza_files = set(wm.list_files(lza_ws))
            assert "config/uc/file1.yaml" in lza_files
            assert "config/uc/subdir/file2.yaml" in lza_files
