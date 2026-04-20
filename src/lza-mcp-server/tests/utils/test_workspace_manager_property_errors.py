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

"""Property tests for input validation vs storage error distinction."""

import tempfile
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)

_traversal_paths = st.sampled_from(
    [
        "../escape.txt",
        "../../etc/passwd",
        "/absolute/path",
    ]
)

_segment = st.from_regex(r"[a-zA-Z0-9_\-]{1,8}", fullmatch=True)
_valid_path = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_segment, min_size=1, max_size=3),
)


# Feature: workspace-and-templates, Property 14: Input validation errors
# are distinct from storage errors
@pytest.mark.property
class TestErrorDistinction:
    """Property 14: Validation errors and storage errors are different types."""

    @given(bad_path=_traversal_paths)
    @settings(max_examples=50, deadline=None)
    def test_validation_errors_are_validation_type(self, bad_path):
        """Path traversal and absolute paths raise WorkspaceValidationError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.write_file(ws_id, bad_path, b"x")

    def test_empty_path_raises_validation_error(self):
        """Empty path is a validation error, not a storage error."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.write_file(ws_id, "", b"x")

    def test_nonexistent_workspace_raises_not_found(self):
        """Accessing a non-existent workspace raises WorkspaceNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            with pytest.raises(WorkspaceNotFoundError):
                wm.read_file("aabbccddeeff", "file.txt")

    def test_nonexistent_file_raises_not_found(self):
        """Reading a missing file raises WorkspaceNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceNotFoundError):
                wm.read_file(ws_id, "missing.txt")

    @given(path=_valid_path)
    @settings(max_examples=50, deadline=None)
    def test_storage_failure_raises_storage_error(self, path):
        """When the adapter raises an unexpected error, it becomes
        WorkspaceStorageError, not WorkspaceValidationError."""
        mock_adapter = Mock()
        mock_adapter.exists.return_value = True
        mock_adapter.create_directory.return_value = None
        mock_adapter.write.side_effect = OSError("disk full")

        wm = WorkspaceManager(storage=mock_adapter)

        with pytest.raises(WorkspaceStorageError):
            wm.write_file("aabbccddeeff", path, b"data")

    def test_error_types_are_distinct_classes(self):
        """The three error types should not share a common base
        (other than Exception)."""
        assert not issubclass(WorkspaceValidationError, WorkspaceStorageError)
        assert not issubclass(WorkspaceStorageError, WorkspaceValidationError)
        assert not issubclass(WorkspaceNotFoundError, WorkspaceValidationError)
        assert not issubclass(WorkspaceNotFoundError, WorkspaceStorageError)
