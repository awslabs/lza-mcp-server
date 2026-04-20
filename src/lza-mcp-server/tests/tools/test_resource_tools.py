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

"""Unit tests for resource_tools.py (listResources and readResource)."""

import json
import tempfile

import pytest

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.tools.resource_tools import register_resource_tools


def _make_mock_mcp():
    """Create a mock MCP server that captures tool registrations."""
    tools = {}

    class MockMCP:
        def tool(self):
            def decorator(fn):
                tools[fn.__name__] = fn
                return fn

            return decorator

    return MockMCP(), tools


class TestListResources:
    """Test the listResources tool."""

    @pytest.mark.asyncio
    async def test_returns_route_map(self):
        """Test listResources returns a JSON route map."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["listResources"]()
            parsed = json.loads(result)

            assert "workspace://list" in parsed
            assert "workspace://{workspace_id}/files" in parsed
            assert "workspace://{workspace_id}/file/{path}" in parsed


class TestReadResourceWorkspaceList:
    """Test readResource with workspace://list URI."""

    @pytest.mark.asyncio
    async def test_list_workspaces(self):
        """Test reading workspace://list returns workspace IDs."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            result = await tools["readResource"](uri="workspace://list")
            parsed = json.loads(result)

            assert ws_id in parsed

    @pytest.mark.asyncio
    async def test_list_workspaces_empty(self):
        """Test reading workspace://list when no workspaces exist."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["readResource"](uri="workspace://list")
            parsed = json.loads(result)

            assert parsed == []


class TestReadResourceWorkspaceFiles:
    """Test readResource with workspace://{id}/files URI."""

    @pytest.mark.asyncio
    async def test_list_files(self):
        """Test listing files in a workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"hello")

            result = await tools["readResource"](uri=f"workspace://{ws_id}/files")
            parsed = json.loads(result)

            assert "test.txt" in parsed

    @pytest.mark.asyncio
    async def test_list_files_workspace_not_found(self):
        """Test listing files for non-existent workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["readResource"](uri="workspace://aabbccddeeff/files")
            parsed = json.loads(result)

            assert "error" in parsed


class TestReadResourceWorkspaceFile:
    """Test readResource with workspace://{id}/file/{path} URI."""

    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """Test reading a file from a workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "hello.txt", b"world")

            result = await tools["readResource"](
                uri=f"workspace://{ws_id}/file/hello.txt"
            )
            assert result == "world"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """Test reading a non-existent file."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            result = await tools["readResource"](
                uri=f"workspace://{ws_id}/file/missing.txt"
            )
            parsed = json.loads(result)

            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_read_binary_file(self):
        """Test reading a binary file returns error."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "binary.bin", bytes(range(256)))

            result = await tools["readResource"](
                uri=f"workspace://{ws_id}/file/binary.bin"
            )
            parsed = json.loads(result)

            assert "error" in parsed
            assert "binary" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_read_file_workspace_not_found(self):
        """Test reading file from non-existent workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["readResource"](
                uri="workspace://aabbccddeeff/file/test.txt"
            )
            parsed = json.loads(result)

            assert "error" in parsed


class TestReadResourceGenericErrors:
    """Test readResource generic exception paths."""

    @pytest.mark.asyncio
    async def test_workspace_list_generic_error(self):
        """Test workspace://list generic exception path."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            # Break list_workspaces to trigger generic exception
            wm.list_workspaces = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("boom")
            )

            result = await tools["readResource"](uri="workspace://list")
            parsed = json.loads(result)
            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_workspace_files_generic_error(self):
        """Test workspace://{id}/files generic exception path."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            # Break list_files to trigger generic exception (not WorkspaceNotFoundError)
            wm.list_files = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("io error")
            )

            result = await tools["readResource"](uri=f"workspace://{ws_id}/files")
            parsed = json.loads(result)
            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_workspace_file_generic_error(self):
        """Test workspace://{id}/file/{path} generic exception path."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")
            # Break read_file to trigger generic exception
            wm.read_file = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("io error")
            )

            result = await tools["readResource"](
                uri=f"workspace://{ws_id}/file/test.txt"
            )
            parsed = json.loads(result)
            assert "error" in parsed


class TestReadResourceUnsupported:
    """Test readResource with unsupported URIs."""

    @pytest.mark.asyncio
    async def test_unsupported_uri(self):
        """Test unsupported URI returns error with supported patterns."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["readResource"](uri="unknown://something")
            parsed = json.loads(result)

            assert "error" in parsed
            assert "supported_patterns" in parsed

    @pytest.mark.asyncio
    async def test_empty_uri(self):
        """Test empty URI returns unsupported error."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            register_resource_tools(mcp, wm)

            result = await tools["readResource"](uri="")
            parsed = json.loads(result)

            assert "error" in parsed
