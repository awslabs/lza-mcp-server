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

"""Property test: Copy respects LZA workspace path prefix.

Feature: uc-workspace-rework, Property 6: Copy respects LZA workspace path prefix

For any path prefix and set of UC workspace files, copyUcToLzaConfig SHALL
write each file to {path_prefix}/{relative_file_path} in the LZA workspace,
such that stripping the prefix from each destination path yields the original
relative path.

**Validates: Requirements 9.6**
"""

import asyncio
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)

# --- Strategies ---

# File name segment: lowercase alphanumeric, 1-8 chars
_name_segment = st.from_regex(r"[a-z][a-z0-9]{0,7}", fullmatch=True)

# File extension
_extension = st.sampled_from([".yaml", ".yml", ".json", ".txt", ".md"])

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

# Path prefix: 1-3 segments
_path_prefix = st.one_of(
    _name_segment,
    st.builds(lambda a, b: f"{a}/{b}", _name_segment, _name_segment),
    st.builds(
        lambda a, b, c: f"{a}/{b}/{c}", _name_segment, _name_segment, _name_segment
    ),
)


# Feature: uc-workspace-rework, Property 6: Copy respects LZA workspace path prefix
@pytest.mark.property
class TestCopyRespectsPathPrefix:
    """Property 6: Copy respects LZA workspace path prefix.

    For any path prefix and set of UC workspace files, copyUcToLzaConfig SHALL
    write each file to {path_prefix}/{relative_file_path} in the LZA workspace,
    such that stripping the prefix from each destination path yields the original
    relative path.

    **Validates: Requirements 9.6**
    """

    @given(files=_file_set, prefix=_path_prefix)
    @settings(max_examples=100, deadline=None)
    def test_copy_respects_path_prefix(self, files, prefix):
        """Destination paths equal prefix + original relative path."""
        with tempfile.TemporaryDirectory() as td:
            # Arrange
            wm_dir = os.path.join(td, "workspaces")
            adapter = LocalAdapter(base_dir=wm_dir)
            wm = WorkspaceManager(storage=adapter)

            uc_ws = wm.create_workspace()
            lza_ws = wm.create_workspace()

            # Write files to UC workspace
            source_paths = set()
            for rel_path, content in files:
                wm.write_file(uc_ws, rel_path, content)
                source_paths.add(rel_path)

            ctx = AsyncMock()
            ctx.info = AsyncMock()

            # Act
            result = asyncio.run(
                copy_uc_to_lza_config(ctx, uc_ws, lza_ws, wm, path=prefix)
            )

            # Assert
            assert result["success"] is True
            assert result["files_copied"] == len(source_paths)

            # Verify each destination path is prefix/original_path
            lza_files = set(wm.list_files(lza_ws))

            expected_dest_paths = {f"{prefix}/{p}" for p in source_paths}
            assert lza_files == expected_dest_paths

            # Verify stripping prefix yields original paths
            stripped_prefix = prefix + "/"
            recovered_paths = set()
            for dest_path in lza_files:
                assert dest_path.startswith(stripped_prefix)
                recovered_paths.add(dest_path[len(stripped_prefix) :])

            assert recovered_paths == source_paths
