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

"""Property tests for WorkspaceManager file write/read round-trip."""

import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

# Strategy: valid relative path segments (no empty, no "..", no absolute)
_segment = st.from_regex(r"[a-zA-Z0-9_\-]{1,12}", fullmatch=True)
_rel_path = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_segment, min_size=1, max_size=4),
)


# Feature: workspace-and-templates, Property 1: File write/read round-trip
@pytest.mark.property
class TestFileWriteReadRoundTrip:
    """Property 1: For any workspace, valid path, and byte content,
    writing then reading should return identical content."""

    @given(path=_rel_path, content=st.binary(min_size=0, max_size=4096))
    @settings(max_examples=100, deadline=None)
    def test_write_read_roundtrip(self, path, content):
        """Write arbitrary content, read it back, assert equality."""
        with tempfile.TemporaryDirectory() as td:
            # Arrange
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Act
            wm.write_file(ws_id, path, content)
            result = wm.read_file(ws_id, path)

            # Assert
            assert result == content
