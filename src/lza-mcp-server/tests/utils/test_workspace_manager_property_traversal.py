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

"""Property tests for path traversal rejection."""

import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceValidationError,
)

# Strategy: paths that attempt to escape the workspace root
_traversal_paths = st.one_of(
    # Direct traversal
    st.just("../secret.txt"),
    st.just("../../etc/passwd"),
    # Traversal after descending into a subdirectory
    st.builds(
        lambda seg: f"{seg}/../../escape.txt",
        st.from_regex(r"[a-z]{1,6}", fullmatch=True),
    ),
    # Deep traversal
    st.builds(
        lambda n: "/".join([".."] * n + ["escape.txt"]),
        st.integers(min_value=1, max_value=6),
    ),
    # Absolute paths
    st.just("/etc/passwd"),
    st.just("/tmp/evil"),
)


# Feature: workspace-and-templates, Property 5: Path traversal rejection
@pytest.mark.property
class TestPathTraversalRejection:
    """Property 5: Any path with '..' escaping the workspace root or
    any absolute path should be rejected for every operation type."""

    @given(bad_path=_traversal_paths)
    @settings(max_examples=100, deadline=None)
    def test_write_rejects_traversal(self, bad_path):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.write_file(ws_id, bad_path, b"evil")

    @given(bad_path=_traversal_paths)
    @settings(max_examples=100, deadline=None)
    def test_read_rejects_traversal(self, bad_path):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.read_file(ws_id, bad_path)

    @given(bad_path=_traversal_paths)
    @settings(max_examples=100, deadline=None)
    def test_delete_file_rejects_traversal(self, bad_path):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.delete_file(ws_id, bad_path)

    @given(bad_path=_traversal_paths)
    @settings(max_examples=100, deadline=None)
    def test_create_folder_rejects_traversal(self, bad_path):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.create_folder(ws_id, bad_path)

    @given(bad_path=_traversal_paths)
    @settings(max_examples=100, deadline=None)
    def test_delete_folder_rejects_traversal(self, bad_path):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            with pytest.raises(WorkspaceValidationError):
                wm.delete_folder(ws_id, bad_path)
