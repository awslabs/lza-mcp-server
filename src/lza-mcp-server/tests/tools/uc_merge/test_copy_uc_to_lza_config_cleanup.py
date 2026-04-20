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

"""Unit tests for copy_uc_to_lza_config workspace lifecycle (workspace-based).

With the workspace-based implementation, session cleanup is no longer performed
by copyUcToLzaConfig. Workspaces are managed separately. These tests verify
that both workspaces remain intact after the copy operation.
"""

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


class TestCopyUcToLzaConfigWorkspaceLifecycle:
    """Test that workspaces remain intact after copy."""

    @pytest.mark.asyncio
    async def test_uc_workspace_preserved_after_copy(self):
        """Test that UC workspace is not deleted after successful copy."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "file1.yaml", b"content1")

            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            # UC workspace should still exist
            uc_files = wm.list_files(uc_ws)
            assert "file1.yaml" in uc_files

    @pytest.mark.asyncio
    async def test_lza_workspace_preserved_after_copy(self):
        """Test that LZA workspace retains existing files after copy."""
        mock_ctx = AsyncMock()

        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))

            uc_ws = wm.create_workspace()
            wm.write_file(uc_ws, "uc-file.yaml", b"uc content")

            lza_ws = wm.create_workspace()
            wm.write_file(lza_ws, "existing.yaml", b"existing content")

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, lza_ws, wm)

            assert result["success"] is True
            lza_files = set(wm.list_files(lza_ws))
            assert "existing.yaml" in lza_files
            assert "uc-file.yaml" in lza_files
