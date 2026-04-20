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

"""Unit tests for resources/workspace.py MCP resource handlers."""

import json
import tempfile

import pytest

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.resources.workspace import register_workspace_resources


def _make_mock_mcp():
    """Create a mock MCP server that captures resource registrations."""
    resources = {}

    class MockMCP:
        def resource(self, uri_pattern):
            def decorator(fn):
                resources[uri_pattern] = fn
                return fn

            return decorator

    return MockMCP(), resources


class TestListWorkspacesResource:
    """Test the workspace://list resource."""

    @pytest.mark.asyncio
    async def test_list_empty(self):
        """Test listing workspaces when none exist."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            result = await resources["workspace://list"]()
            parsed = json.loads(result)
            assert parsed == []

    @pytest.mark.asyncio
    async def test_list_with_workspaces(self):
        """Test listing workspaces returns created IDs."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            result = await resources["workspace://list"]()
            parsed = json.loads(result)
            assert ws_id in parsed

    @pytest.mark.asyncio
    async def test_list_error(self):
        """Test listing workspaces handles errors."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            # Break the storage to trigger error
            wm._storage.list = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("boom")
            )

            result = await resources["workspace://list"]()
            parsed = json.loads(result)
            assert "error" in parsed


class TestListWorkspaceFilesResource:
    """Test the workspace://{workspace_id}/files resource."""

    @pytest.mark.asyncio
    async def test_list_files_success(self):
        """Test listing files in a workspace."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"content")

            result = await resources["workspace://{workspace_id}/files"](
                workspace_id=ws_id
            )
            parsed = json.loads(result)
            assert "a.txt" in parsed

    @pytest.mark.asyncio
    async def test_list_files_not_found(self):
        """Test listing files for non-existent workspace."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            result = await resources["workspace://{workspace_id}/files"](
                workspace_id="aabbccddeeff"
            )
            parsed = json.loads(result)
            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_list_files_unexpected_error(self):
        """Test listing files handles unexpected errors (generic Exception path)."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            # Patch list_files to raise a generic exception (not WorkspaceNotFoundError)
            wm.list_files = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("disk error")
            )

            result = await resources["workspace://{workspace_id}/files"](
                workspace_id=ws_id
            )
            parsed = json.loads(result)
            assert "error" in parsed


class TestReadWorkspaceFileResource:
    """Test the workspace://{workspace_id}/file/{path} resource."""

    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """Test reading a file successfully."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "hello.txt", b"world")

            result = await resources["workspace://{workspace_id}/file/{path}"](
                workspace_id=ws_id, path="hello.txt"
            )
            assert result == "world"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """Test reading non-existent file."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            result = await resources["workspace://{workspace_id}/file/{path}"](
                workspace_id=ws_id, path="missing.txt"
            )
            parsed = json.loads(result)
            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_read_binary_file(self):
        """Test reading binary file returns error."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "bin.dat", bytes(range(256)))

            result = await resources["workspace://{workspace_id}/file/{path}"](
                workspace_id=ws_id, path="bin.dat"
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert "binary" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_read_file_unexpected_error(self):
        """Test reading file handles unexpected errors."""
        mcp, resources = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_workspace_resources(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")

            # Break read to trigger generic exception
            wm._storage.read = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("io error")
            )

            result = await resources["workspace://{workspace_id}/file/{path}"](
                workspace_id=ws_id, path="test.txt"
            )
            parsed = json.loads(result)
            assert "error" in parsed
