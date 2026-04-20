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

"""Unit tests for copy_uc_to_lza_config error handling (workspace-based)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceStorageError,
)


class TestCopyUcToLzaConfigErrors:
    """Test error handling for workspace-based copy operations."""

    @pytest.mark.asyncio
    async def test_storage_error_during_list(self):
        """Test handling of storage errors when listing UC workspace files."""
        mock_ctx = AsyncMock()
        mock_wm = MagicMock()
        mock_wm.list_files.side_effect = WorkspaceStorageError("Storage failure")

        result = await copy_uc_to_lza_config(
            mock_ctx, "aabbccddeeff", "112233445566", mock_wm
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_read_error_skips_file(self):
        """Test that read errors for individual files are skipped gracefully."""
        mock_ctx = AsyncMock()
        mock_wm = MagicMock()

        # First call lists UC files, second call lists LZA files
        mock_wm.list_files.side_effect = [
            ["file1.yaml", "file2.yaml"],
            ["existing.yaml"],
        ]
        # First read fails, second succeeds
        mock_wm.read_file.side_effect = [
            WorkspaceStorageError("Read failed"),
            b"content2",
        ]

        result = await copy_uc_to_lza_config(
            mock_ctx, "aabbccddeeff", "112233445566", mock_wm
        )

        assert result["success"] is True
        assert result["files_copied"] == 1

    @pytest.mark.asyncio
    async def test_write_error_skips_file(self):
        """Test that write errors for individual files are skipped gracefully."""
        mock_ctx = AsyncMock()
        mock_wm = MagicMock()

        mock_wm.list_files.side_effect = [
            ["file1.yaml", "file2.yaml"],
            ["existing.yaml"],
        ]
        mock_wm.read_file.side_effect = [b"content1", b"content2"]
        mock_wm.write_file.side_effect = [
            WorkspaceStorageError("Write failed"),
            None,
        ]

        result = await copy_uc_to_lza_config(
            mock_ctx, "aabbccddeeff", "112233445566", mock_wm
        )

        assert result["success"] is True
        assert result["files_copied"] == 1

    @pytest.mark.asyncio
    async def test_unexpected_error_in_outer_try_block(self):
        """Test handling of unexpected errors in outer try block."""
        mock_ctx = AsyncMock()
        mock_wm = MagicMock()
        mock_wm.list_files.side_effect = RuntimeError("Unexpected error")

        result = await copy_uc_to_lza_config(
            mock_ctx, "aabbccddeeff", "112233445566", mock_wm
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
