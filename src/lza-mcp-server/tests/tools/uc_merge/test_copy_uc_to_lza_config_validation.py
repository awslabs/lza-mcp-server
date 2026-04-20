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

"""Unit tests for copy_uc_to_lza_config validation (workspace-based)."""

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


class TestCopyUcToLzaConfigValidation:
    """Test validation logic for copy_uc_to_lza_config."""

    @pytest.mark.asyncio
    async def test_missing_uc_workspace_id(self):
        """Test error when uc_workspace_id is not provided."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))
            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, "", lza_ws, wm)

            assert result["success"] is False
            assert result["error_code"] == "MISSING_WORKSPACE_ID"
            assert "UC workspace ID is required" in result["error"]
            assert result["category"] == "validation"

    @pytest.mark.asyncio
    async def test_missing_uc_workspace_id_none(self):
        """Test error when uc_workspace_id is None."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))
            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, None, lza_ws, wm)

            assert result["success"] is False
            assert result["error_code"] == "MISSING_WORKSPACE_ID"

    @pytest.mark.asyncio
    async def test_missing_lza_workspace_id(self):
        """Test error when lza_workspace_id is not provided."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))
            uc_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, "", wm)

            assert result["success"] is False
            assert result["error_code"] == "MISSING_WORKSPACE_ID"
            assert "LZA workspace ID is required" in result["error"]

    @pytest.mark.asyncio
    async def test_uc_workspace_not_found(self):
        """Test error when UC workspace does not exist."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))
            lza_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, "aabbccddeeff", lza_ws, wm)

            assert result["success"] is False
            assert result["error_code"] == "WORKSPACE_NOT_FOUND"
            assert "UC workspace" in result["error"]

    @pytest.mark.asyncio
    async def test_lza_workspace_not_found(self):
        """Test error when LZA workspace does not exist."""
        mock_ctx = AsyncMock()
        with tempfile.TemporaryDirectory() as td:
            wm = _make_wm(os.path.join(td, "workspaces"))
            uc_ws = wm.create_workspace()

            result = await copy_uc_to_lza_config(mock_ctx, uc_ws, "aabbccddeeff", wm)

            assert result["success"] is False
            assert result["error_code"] == "WORKSPACE_NOT_FOUND"
            assert "LZA workspace" in result["error"]
