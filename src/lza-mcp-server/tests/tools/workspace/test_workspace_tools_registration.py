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

"""Unit tests for workspace tools and resources registration."""

import json
import tempfile

import pytest
from unittest.mock import MagicMock

from awslabs.lza_mcp_server.tools.workspace.manage_workspace_tools import (
    register_workspace_tools,
)
from awslabs.lza_mcp_server.resources.workspace import (
    register_workspace_resources,
)
from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.utils.zip_utility import ZipUtility


def _make_mock_mcp():
    """Create a mock MCP that captures tool and resource registrations."""
    mock = MagicMock()
    tools = {}
    resources = {}

    def capture_tool(**kwargs):
        def decorator(fn):
            tools[kwargs["name"]] = fn
            return fn

        return decorator

    def capture_resource(uri):
        def decorator(fn):
            resources[uri] = fn
            return fn

        return decorator

    mock.tool = capture_tool
    mock.resource = capture_resource
    return mock, tools, resources


class TestWorkspaceToolsRegistration:
    """Verify all 7 workspace tools are registered."""

    def test_registers_all_workspace_tools(self):
        """All 7 workspace tools should be registered."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)

            # Act
            register_workspace_tools(mock_mcp, wm, zu)

        # Assert
        expected_tools = {
            "createWorkspace",
            "deleteWorkspace",
            "writeWorkspaceFile",
            "deleteWorkspaceFile",
            "createWorkspaceFolder",
            "deleteWorkspaceFolder",
            "zipWorkspaceFiles",
        }
        assert set(tools.keys()) == expected_tools


class TestWorkspaceResourcesRegistration:
    """Verify workspace resource URIs are registered."""

    def test_registers_workspace_resources(self):
        """All 3 workspace resource URIs should be registered."""
        # Arrange
        mock_mcp, _, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            # Act
            register_workspace_resources(mock_mcp, wm)

        # Assert
        expected_uris = {
            "workspace://list",
            "workspace://{workspace_id}/files",
            "workspace://{workspace_id}/file/{path}",
        }
        assert set(resources.keys()) == expected_uris


class TestWorkspaceToolsDelegation:
    """Verify workspace tools delegate to WorkspaceManager correctly."""

    @pytest.mark.asyncio
    async def test_create_workspace_returns_id(self):
        """create_workspace should return a workspace ID."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mock_mcp, wm, zu)
            ctx = MagicMock()

            # Act
            result = await tools["createWorkspace"](ctx)

        # Assert
        assert result["success"] is True
        assert "workspace_id" in result

    @pytest.mark.asyncio
    async def test_write_and_delete_file(self):
        """write_workspace_file then delete_workspace_file should succeed."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mock_mcp, wm, zu)
            ctx = MagicMock()

            ws = await tools["createWorkspace"](ctx)
            ws_id = ws["workspace_id"]

            # Act
            write_result = await tools["writeWorkspaceFile"](
                ctx, ws_id, "test.txt", "hello"
            )
            delete_result = await tools["deleteWorkspaceFile"](ctx, ws_id, "test.txt")

        # Assert
        assert write_result["success"] is True
        assert delete_result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_workspace_nonexistent(self):
        """delete_workspace with bad ID should return error."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mock_mcp, wm, zu)
            ctx = MagicMock()

            # Act
            result = await tools["deleteWorkspace"](ctx, "nonexistent")

        # Assert
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_and_delete_folder(self):
        """create_workspace_folder then delete_workspace_folder should succeed."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mock_mcp, wm, zu)
            ctx = MagicMock()

            ws = await tools["createWorkspace"](ctx)
            ws_id = ws["workspace_id"]

            # Act
            create_result = await tools["createWorkspaceFolder"](ctx, ws_id, "subdir")
            delete_result = await tools["deleteWorkspaceFolder"](ctx, ws_id, "subdir")

        # Assert
        assert create_result["success"] is True
        assert delete_result["success"] is True

    @pytest.mark.asyncio
    async def test_zip_files_success(self):
        """zip_workspace_files should create a zip archive."""
        # Arrange
        mock_mcp, tools, _ = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mock_mcp, wm, zu)
            ctx = MagicMock()

            ws = await tools["createWorkspace"](ctx)
            ws_id = ws["workspace_id"]
            await tools["writeWorkspaceFile"](ctx, ws_id, "a.txt", "content-a")

            # Act
            result = await tools["zipWorkspaceFiles"](ctx, ws_id, ["a.txt"], "out.zip")

        # Assert
        assert result["success"] is True
        assert result["zip_path"] == "out.zip"


class TestWorkspaceResourcesDelegation:
    """Verify workspace resources delegate correctly."""

    @pytest.mark.asyncio
    async def test_list_workspaces_resource(self):
        """workspace://list should return JSON array."""
        # Arrange
        mock_mcp, _, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mock_mcp, wm)

            ws_id = wm.create_workspace()

            # Act
            result = await resources["workspace://list"]()

        # Assert
        ids = json.loads(result)
        assert ws_id in ids

    @pytest.mark.asyncio
    async def test_list_files_resource(self):
        """workspace://{id}/files should return file list."""
        # Arrange
        mock_mcp, _, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mock_mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "hello.txt", b"world")

            # Act
            result = await resources["workspace://{workspace_id}/files"](ws_id)

        # Assert
        files = json.loads(result)
        assert "hello.txt" in files

    @pytest.mark.asyncio
    async def test_read_file_resource(self):
        """workspace://{id}/file/{path} should return file content."""
        # Arrange
        mock_mcp, _, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mock_mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "data.txt", b"test-content")

            # Act
            result = await resources["workspace://{workspace_id}/file/{path}"](
                ws_id, "data.txt"
            )

        # Assert
        assert result == "test-content"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """Reading a non-existent file should return error JSON."""
        # Arrange
        mock_mcp, _, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mock_mcp, wm)

            ws_id = wm.create_workspace()

            # Act
            result = await resources["workspace://{workspace_id}/file/{path}"](
                ws_id, "missing.txt"
            )

        # Assert
        parsed = json.loads(result)
        assert "error" in parsed
