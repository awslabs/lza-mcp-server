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

"""Unit tests for WorkspaceManager operations (error paths and storage errors)."""

import tempfile

import pytest

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)


class TestCreateWorkspaceErrors:
    """Test create_workspace error paths."""

    def test_create_workspace_storage_error(self):
        """Test create_workspace wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            # Break create_directory to trigger storage error
            adapter.create_directory = lambda *a, **kw: (_ for _ in ()).throw(
                OSError("disk full")
            )

            with pytest.raises(
                WorkspaceStorageError, match="Failed to create workspace"
            ):
                wm.create_workspace()


class TestDeleteWorkspaceErrors:
    """Test delete_workspace error paths."""

    def test_delete_workspace_not_found(self):
        """Test deleting non-existent workspace."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            with pytest.raises(WorkspaceNotFoundError):
                wm.delete_workspace("aabbccddeeff")

    def test_delete_workspace_storage_error(self):
        """Test delete_workspace wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Break delete_directory
            adapter.delete_directory = lambda *a, **kw: (_ for _ in ()).throw(
                OSError("permission denied")
            )

            with pytest.raises(
                WorkspaceStorageError, match="Failed to delete workspace"
            ):
                wm.delete_workspace(ws_id)


class TestListWorkspacesErrors:
    """Test list_workspaces error paths."""

    def test_list_workspaces_storage_error(self):
        """Test list_workspaces wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            adapter.list = lambda *a, **kw: (_ for _ in ()).throw(OSError("io error"))

            with pytest.raises(
                WorkspaceStorageError, match="Failed to list workspaces"
            ):
                wm.list_workspaces()


class TestWriteFileErrors:
    """Test write_file error paths."""

    def test_write_file_storage_error(self):
        """Test write_file wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Break write to trigger storage error
            adapter.write = lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full"))

            with pytest.raises(WorkspaceStorageError, match="Failed to write file"):
                wm.write_file(ws_id, "test.txt", b"data")


class TestReadFileErrors:
    """Test read_file error paths."""

    def test_read_file_not_found(self):
        """Test reading non-existent file."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceNotFoundError, match="not found"):
                wm.read_file(ws_id, "missing.txt")

    def test_read_file_storage_error(self):
        """Test read_file wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")

            # Break read to trigger storage error (not FileNotFoundError)
            adapter.read = lambda *a, **kw: (_ for _ in ()).throw(OSError("io error"))

            with pytest.raises(WorkspaceStorageError, match="Failed to read file"):
                wm.read_file(ws_id, "test.txt")


class TestDeleteFileErrors:
    """Test delete_file error paths."""

    def test_delete_file_not_found(self):
        """Test deleting non-existent file."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceNotFoundError, match="not found"):
                wm.delete_file(ws_id, "missing.txt")

    def test_delete_file_storage_error(self):
        """Test delete_file wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")

            # Break delete to trigger storage error
            adapter.delete = lambda *a, **kw: (_ for _ in ()).throw(
                OSError("permission denied")
            )

            with pytest.raises(WorkspaceStorageError, match="Failed to delete file"):
                wm.delete_file(ws_id, "test.txt")


class TestListFilesErrors:
    """Test list_files error paths."""

    def test_list_files_storage_error(self):
        """Test list_files wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Break list to trigger storage error
            adapter.list = lambda *a, **kw: (_ for _ in ()).throw(OSError("io error"))

            with pytest.raises(WorkspaceStorageError, match="Failed to list files"):
                wm.list_files(ws_id)


class TestCreateFolderErrors:
    """Test create_folder error paths."""

    def test_create_folder_storage_error(self):
        """Test create_folder wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            adapter.create_directory = lambda *a, **kw: (_ for _ in ()).throw(
                OSError("permission denied")
            )

            with pytest.raises(WorkspaceStorageError, match="Failed to create folder"):
                wm.create_folder(ws_id, "subdir")


class TestDeleteFolderErrors:
    """Test delete_folder error paths."""

    def test_delete_folder_not_found(self):
        """Test deleting non-existent folder."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceNotFoundError, match="not found"):
                wm.delete_folder(ws_id, "nope")

    def test_delete_folder_storage_error(self):
        """Test delete_folder wraps storage errors."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.create_folder(ws_id, "subdir")

            adapter.delete_directory = lambda *a, **kw: (_ for _ in ()).throw(
                OSError("permission denied")
            )

            with pytest.raises(WorkspaceStorageError, match="Failed to delete folder"):
                wm.delete_folder(ws_id, "subdir")


class TestWorkspaceManagerReRaisePaths:
    """Test the re-raise paths for WorkspaceValidationError/WorkspaceNotFoundError."""

    def test_write_file_reraises_validation_error(self):
        """Test write_file re-raises WorkspaceValidationError from storage."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Break write to raise WorkspaceValidationError
            adapter.write = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceValidationError("bad data")
            )

            with pytest.raises(WorkspaceValidationError, match="bad data"):
                wm.write_file(ws_id, "test.txt", b"data")

    def test_read_file_reraises_validation_error(self):
        """Test read_file re-raises WorkspaceValidationError from storage."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")

            # Break read to raise WorkspaceValidationError
            adapter.read = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceValidationError("bad path")
            )

            with pytest.raises(WorkspaceValidationError, match="bad path"):
                wm.read_file(ws_id, "test.txt")

    def test_create_folder_reraises_validation_error(self):
        """Test create_folder re-raises WorkspaceValidationError from storage."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Break create_directory to raise WorkspaceValidationError
            adapter.create_directory = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceValidationError("bad path")
            )

            with pytest.raises(WorkspaceValidationError, match="bad path"):
                wm.create_folder(ws_id, "subdir")

    def test_delete_file_reraises_validation_error(self):
        """Test delete_file re-raises WorkspaceValidationError from storage."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.write_file(ws_id, "test.txt", b"data")

            # Break delete to raise WorkspaceValidationError
            adapter.delete = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceValidationError("bad path")
            )

            with pytest.raises(WorkspaceValidationError, match="bad path"):
                wm.delete_file(ws_id, "test.txt")

    def test_delete_folder_reraises_validation_error(self):
        """Test delete_folder re-raises WorkspaceValidationError from storage."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()
            wm.create_folder(ws_id, "subdir")

            # Break delete_directory to raise WorkspaceValidationError
            adapter.delete_directory = lambda *a, **kw: (_ for _ in ()).throw(
                WorkspaceValidationError("bad path")
            )

            with pytest.raises(WorkspaceValidationError, match="bad path"):
                wm.delete_folder(ws_id, "subdir")
