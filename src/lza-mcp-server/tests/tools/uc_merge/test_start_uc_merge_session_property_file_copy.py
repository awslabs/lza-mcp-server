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

"""Property test: UC file copy preserves directory structure.

Feature: uc-workspace-rework, Property 2: UC file copy preserves directory structure

For any valid UC release directory containing an arbitrary set of files and
subdirectories, start_uc_merge_session SHALL write every file to the workspace
such that the set of relative paths in the workspace equals the set of relative
paths in the source directory (plus .session_metadata.json).

**Validates: Requirements 7.2**
"""

import asyncio
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)

# --- Strategies ---

# File name segment: lowercase alphanumeric, 1-8 chars
_name_segment = st.from_regex(r"[a-z][a-z0-9]{0,7}", fullmatch=True)

# File extension
_extension = st.sampled_from([".yaml", ".yml", ".json", ".txt", ".md", ".py"])

# File name with extension
_filename = st.builds(lambda name, ext: name + ext, _name_segment, _extension)

# Directory path: 0-2 nested segments
_dir_path = st.one_of(
    st.just(""),
    _name_segment,
    st.builds(lambda a, b: f"{a}/{b}", _name_segment, _name_segment),
)

# A file entry: (relative_path, content_bytes)
_file_entry = st.builds(
    lambda d, f, c: (f"{d}/{f}" if d else f, c),
    _dir_path,
    _filename,
    st.binary(min_size=1, max_size=100),
)

# A set of file entries (1-10 files with unique paths)
_file_set = st.lists(_file_entry, min_size=1, max_size=10, unique_by=lambda x: x[0])


# Feature: uc-workspace-rework, Property 2: UC file copy preserves directory structure
@pytest.mark.property
class TestUcFileCopyPreservesDirectoryStructure:
    """Property 2: UC file copy preserves directory structure.

    For any valid UC release directory containing an arbitrary set of files
    and subdirectories, start_uc_merge_session SHALL write every file to the
    workspace such that the set of relative paths in the workspace equals the
    set of relative paths in the source directory (plus .session_metadata.json).

    **Validates: Requirements 7.2**
    """

    @given(files=_file_set)
    @settings(max_examples=100, deadline=None)
    def test_file_copy_preserves_structure(self, files):
        """All source files appear in workspace with matching relative paths,
        plus .session_metadata.json."""
        import os

        with tempfile.TemporaryDirectory() as td:
            # Arrange - create a fake UC release directory structure
            uc_base = os.path.join(td, "uc")
            release_dir = os.path.join(uc_base, "v1.0.0")
            model_dir = os.path.join(release_dir, "hub-and-spoke")
            os.makedirs(model_dir)

            # Write source files
            source_paths = set()
            for rel_path, content in files:
                full_path = os.path.join(model_dir, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(content)
                source_paths.add(rel_path)

            # Create workspace manager with local adapter
            ws_dir = os.path.join(td, "workspaces")
            adapter = LocalAdapter(base_dir=ws_dir)
            wm = WorkspaceManager(storage=adapter)

            ctx = AsyncMock()
            ctx.info = AsyncMock()
            ctx.error = AsyncMock()

            # Patch the UC path functions to point to our temp dirs
            from unittest.mock import patch

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path",
                    return_value=__import__("pathlib").Path(release_dir),
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path",
                    return_value=__import__("pathlib").Path(model_dir),
                ),
            ):
                # Act
                result = asyncio.run(
                    tool_start_uc_merge_session(ctx, "v1.0.0", "hub-and-spoke", wm)
                )

            # Assert - success
            assert result["success"] is True
            workspace_id = result["workspace_id"]

            # Get all files in workspace
            workspace_files = set(wm.list_files(workspace_id))

            # Expected: source paths + .session_metadata.json
            expected_paths = source_paths | {".session_metadata.json"}

            assert workspace_files == expected_paths
