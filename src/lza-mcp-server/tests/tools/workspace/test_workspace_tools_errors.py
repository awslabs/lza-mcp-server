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

"""Unit tests for manage_workspace_tools.py error handling and _error_response."""

import tempfile

import pytest

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)
from awslabs.lza_mcp_server.utils.zip_utility import ZipUtility
from awslabs.lza_mcp_server.tools.workspace.manage_workspace_tools import (
    _error_response,
    register_workspace_tools,
)


class MockContext:
    """Mock MCP context."""

    pass


def _make_mock_mcp():
    """Create a mock MCP server that captures tool registrations."""
    tools = {}

    class MockMCP:
        def tool(self, name=None, description=None):
            def decorator(fn):
                tools[name or fn.__name__] = fn
                return fn

            return decorator

    return MockMCP(), tools


class TestErrorResponse:
    """Test _error_response helper function."""

    def test_validation_error(self):
        """Test error response for WorkspaceValidationError."""
        exc = WorkspaceValidationError("bad path")
        result = _error_response(exc, "testOp")

        assert result["success"] is False
        assert result["category"] == "validation"
        assert result["error_code"] == "WORKSPACE_VALIDATION_ERROR"

    def test_not_found_error(self):
        """Test error response for WorkspaceNotFoundError."""
        exc = WorkspaceNotFoundError("not found")
        result = _error_response(exc, "testOp")

        assert result["success"] is False
        assert result["category"] == "file_not_found"
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    def test_storage_error(self):
        """Test error response for WorkspaceStorageError."""
        exc = WorkspaceStorageError("disk full")
        result = _error_response(exc, "testOp")

        assert result["success"] is False
        assert result["category"] == "file_operation"
        assert result["error_code"] == "WORKSPACE_STORAGE_ERROR"

    def test_unexpected_error(self):
        """Test error response for unexpected exceptions."""
        exc = RuntimeError("something broke")
        result = _error_response(exc, "testOp")

        assert result["success"] is False
        assert result["category"] == "system"
        assert result["error_code"] == "WORKSPACE_UNEXPECTED_ERROR"

    def test_extra_context_included(self):
        """Test extra context is passed through."""
        exc = RuntimeError("oops")
        result = _error_response(exc, "testOp", workspace_id="abc", path="x.txt")

        assert result["context"]["workspace_id"] == "abc"
        assert result["context"]["path"] == "x.txt"


class TestWorkspaceToolsErrorPaths:
    """Test error paths for each workspace tool."""

    @pytest.mark.asyncio
    async def test_create_workspace_error(self):
        """Test createWorkspace handles unexpected errors."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            # Patch create_workspace to raise
            wm.create_workspace = lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("fail")
            )

            result = await tools["createWorkspace"](ctx=MockContext())
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_workspace_not_found(self):
        """Test deleteWorkspace with non-existent workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            result = await tools["deleteWorkspace"](
                ctx=MockContext(), workspace_id="aabbccddeeff"
            )
            assert result["success"] is False
            assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_write_file_invalid_path(self):
        """Test writeWorkspaceFile with path traversal."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["writeWorkspaceFile"](
                ctx=MockContext(),
                workspace_id=ws_id,
                path="../escape.txt",
                content="bad",
            )
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self):
        """Test deleteWorkspaceFile with non-existent file."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["deleteWorkspaceFile"](
                ctx=MockContext(), workspace_id=ws_id, path="missing.txt"
            )
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_folder_invalid_workspace(self):
        """Test createWorkspaceFolder with invalid workspace."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            result = await tools["createWorkspaceFolder"](
                ctx=MockContext(), workspace_id="aabbccddeeff", path="subdir"
            )
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_folder_not_found(self):
        """Test deleteWorkspaceFolder with non-existent folder."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["deleteWorkspaceFolder"](
                ctx=MockContext(), workspace_id=ws_id, path="nope"
            )
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_zip_files_error(self):
        """Test zipWorkspaceFiles with missing sources."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["zipWorkspaceFiles"](
                ctx=MockContext(),
                workspace_id=ws_id,
                source_paths=["nonexistent.txt"],
                destination_path="out.zip",
            )
            assert result["success"] is False


class TestWorkspaceToolsSuccessPaths:
    """Test success paths for workspace tools to ensure full coverage."""

    @pytest.mark.asyncio
    async def test_write_and_delete_file(self):
        """Test write then delete file success."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["writeWorkspaceFile"](
                ctx=MockContext(), workspace_id=ws_id, path="test.txt", content="hello"
            )
            assert result["success"] is True

            result = await tools["deleteWorkspaceFile"](
                ctx=MockContext(), workspace_id=ws_id, path="test.txt"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_and_delete_folder(self):
        """Test create then delete folder success."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["createWorkspaceFolder"](
                ctx=MockContext(), workspace_id=ws_id, path="subdir"
            )
            assert result["success"] is True

            result = await tools["deleteWorkspaceFolder"](
                ctx=MockContext(), workspace_id=ws_id, path="subdir"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_workspace_success(self):
        """Test deleteWorkspace success."""
        mcp, tools = _make_mock_mcp()
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            register_workspace_tools(mcp, wm, zu)

            ws_id = wm.create_workspace()
            result = await tools["deleteWorkspace"](
                ctx=MockContext(), workspace_id=ws_id
            )
            assert result["success"] is True
