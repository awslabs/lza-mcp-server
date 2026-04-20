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

"""Property tests for workspace directory cleanliness invariant."""

import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

_segment = st.from_regex(r"[a-zA-Z0-9_\-]{1,12}", fullmatch=True)
_rel_path = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_segment, min_size=1, max_size=3),
)

# Leaf-only file paths that won't conflict with each other
_leaf_file = st.builds(
    lambda name: f"f_{name}.txt",
    st.from_regex(r"[a-z]{1,8}", fullmatch=True),
)


# Feature: workspace-and-templates, Property 4: Workspace directory cleanliness invariant
@pytest.mark.property
class TestWorkspaceDirectoryCleanliness:
    """Property 4: Listing files returns only user-written paths;
    listing workspaces returns only workspace IDs."""

    @given(
        paths=st.lists(_leaf_file, min_size=1, max_size=5, unique=True),
        content=st.binary(min_size=1, max_size=64),
    )
    @settings(max_examples=100, deadline=None)
    def test_list_files_only_returns_written_paths(self, paths, content):
        """After writing files, list_files should only contain those paths."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            for p in paths:
                wm.write_file(ws_id, p, content)

            listed = set(wm.list_files(ws_id))
            written = set(paths)

            # Every listed file was explicitly written
            assert listed == written

    @given(n=st.integers(min_value=1, max_value=6))
    @settings(max_examples=50, deadline=None)
    def test_list_workspaces_only_returns_workspace_ids(self, n):
        """list_workspaces should only return IDs of created workspaces."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            created = set()
            for _ in range(n):
                ws_id = wm.create_workspace()
                # Write a file so workspace is discoverable via list
                wm.write_file(ws_id, "marker.txt", b"x")
                created.add(ws_id)

            listed = set(wm.list_workspaces())
            assert listed == created
