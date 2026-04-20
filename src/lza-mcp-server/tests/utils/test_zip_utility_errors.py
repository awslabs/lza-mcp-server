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

"""Unit tests for ZipUtility error paths."""

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


class TestZipUtilityValidation:
    """Test ZipUtility input validation."""

    def test_empty_source_paths(self):
        """Test empty source_paths raises WorkspaceValidationError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError, match="cannot be empty"):
                zu.create_zip(ws_id, [], "out.zip")

    def test_missing_source_paths(self):
        """Test missing source paths raises WorkspaceNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceNotFoundError, match="not found"):
                zu.create_zip(ws_id, ["nonexistent.txt"], "out.zip")

    def test_path_traversal_in_source(self):
        """Test path traversal in source raises WorkspaceValidationError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                zu.create_zip(ws_id, ["../escape.txt"], "out.zip")

    def test_path_traversal_in_destination(self):
        """Test path traversal in destination raises WorkspaceValidationError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"data")

            with pytest.raises(WorkspaceValidationError):
                zu.create_zip(ws_id, ["a.txt"], "../escape.zip")


class TestZipUtilityBuildErrors:
    """Test ZipUtility zip build error paths."""

    def test_read_error_during_zip_build(self):
        """Test error during zip build wraps as WorkspaceStorageError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"data")

            # Break read_file after list_files succeeds
            call_count = [0]

            def broken_read(wid, path, **kw):
                call_count[0] += 1
                raise OSError("disk error")

            wm.read_file = broken_read

            with pytest.raises(WorkspaceStorageError, match="Failed to build zip"):
                zu.create_zip(ws_id, ["a.txt"], "out.zip")

    def test_write_error_during_zip_save(self):
        """Test error during zip write wraps as WorkspaceStorageError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"data")

            # Break write_file to fail during zip save
            original_write = wm.write_file

            def broken_write(wid, path, content, **kw):
                if path.endswith(".zip"):
                    raise OSError("disk full")
                return original_write(wid, path, content, **kw)

            wm.write_file = broken_write

            with pytest.raises(WorkspaceStorageError, match="Failed to write zip"):
                zu.create_zip(ws_id, ["a.txt"], "out.zip")


class TestZipUtilitySuccess:
    """Test ZipUtility success paths."""

    def test_zip_single_file(self):
        """Test zipping a single file."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "hello.txt", b"world")

            zu.create_zip(ws_id, ["hello.txt"], "out.zip")

            # Verify zip was created
            zip_content = wm.read_file(ws_id, "out.zip")
            assert len(zip_content) > 0

    def test_zip_folder(self):
        """Test zipping a folder."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "data/a.txt", b"aaa")
            wm.write_file(ws_id, "data/b.txt", b"bbb")

            zu.create_zip(ws_id, ["data"], "out.zip")

            zip_content = wm.read_file(ws_id, "out.zip")
            assert len(zip_content) > 0


class TestZipUtilityReRaisePaths:
    """Test ZipUtility re-raise paths for WorkspaceValidationError/WorkspaceNotFoundError."""

    def test_build_reraises_workspace_not_found(self):
        """Test zip build re-raises WorkspaceNotFoundError from read_file."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"data")

            # Break read_file to raise WorkspaceNotFoundError during zip build
            wm.read_file = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceNotFoundError("file gone")
            )

            with pytest.raises(WorkspaceNotFoundError, match="file gone"):
                zu.create_zip(ws_id, ["a.txt"], "out.zip")

    def test_write_reraises_workspace_validation_error(self):
        """Test zip write re-raises WorkspaceValidationError from write_file."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "a.txt", b"data")

            # Break write_file to raise WorkspaceValidationError during zip save
            original_write = wm.write_file

            def broken_write(wid, path, content, **kw):
                if path.endswith(".zip"):
                    raise WorkspaceValidationError("bad dest")
                return original_write(wid, path, content, **kw)

            wm.write_file = broken_write

            with pytest.raises(WorkspaceValidationError, match="bad dest"):
                zu.create_zip(ws_id, ["a.txt"], "out.zip")
