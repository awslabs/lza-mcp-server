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

"""Property tests for workspace create/list/delete lifecycle."""

import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
)

_segment = st.from_regex(r"[a-zA-Z0-9_\-]{1,12}", fullmatch=True)
_rel_path = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_segment, min_size=1, max_size=3),
)

# Strategy for file paths that won't conflict with each other
# (no path is a prefix of another, avoiding file/directory clashes).
_leaf_file = st.builds(
    lambda name: f"f_{name}.txt",
    st.from_regex(r"[a-z]{1,8}", fullmatch=True),
)


# Feature: workspace-and-templates, Property 2: Workspace create/list containment
@pytest.mark.property
class TestWorkspaceCreateListContainment:
    """Property 2: After creating N workspaces, listing should contain all N IDs."""

    @given(n=st.integers(min_value=1, max_value=8))
    @settings(max_examples=50, deadline=None)
    def test_created_workspaces_appear_in_list(self, n):
        """Create N workspaces, verify all appear in list."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            created_ids = [wm.create_workspace() for _ in range(n)]
            listed = wm.list_workspaces()

            for ws_id in created_ids:
                assert ws_id in listed
                # IDs should be valid hex strings
                int(ws_id, 16)


# Feature: workspace-and-templates, Property 3: Delete removes from listing
@pytest.mark.property
class TestDeleteRemovesFromListing:
    """Property 3: Deleting a workspace/file/folder removes it from listing."""

    @given(n=st.integers(min_value=2, max_value=6))
    @settings(max_examples=50, deadline=None)
    def test_delete_workspace_removes_from_list(self, n):
        """Create N workspaces, delete one, verify it's gone."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            ids = [wm.create_workspace() for _ in range(n)]
            target = ids[0]
            # Need a file so workspace shows in list
            for ws_id in ids:
                wm.write_file(ws_id, "marker.txt", b"x")

            wm.delete_workspace(target)
            remaining = wm.list_workspaces()

            assert target not in remaining
            for ws_id in ids[1:]:
                assert ws_id in remaining

    @given(
        paths=st.lists(_leaf_file, min_size=2, max_size=5, unique=True),
        content=st.binary(min_size=1, max_size=64),
    )
    @settings(max_examples=50, deadline=None)
    def test_delete_file_removes_from_list(self, paths, content):
        """Write multiple files, delete one, verify it's gone from listing."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            for p in paths:
                wm.write_file(ws_id, p, content)

            target = paths[0]
            wm.delete_file(ws_id, target)
            files = wm.list_files(ws_id)

            assert target not in files

    @given(content=st.binary(min_size=1, max_size=64))
    @settings(max_examples=50, deadline=None)
    def test_delete_folder_removes_contents(self, content):
        """Create a folder with files, delete it, verify contents gone."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            wm.write_file(ws_id, "keep.txt", content)
            wm.write_file(ws_id, "sub/a.txt", content)
            wm.write_file(ws_id, "sub/b.txt", content)

            wm.delete_folder(ws_id, "sub")
            files = wm.list_files(ws_id)

            assert "keep.txt" in files
            assert not any(f.startswith("sub/") for f in files)
