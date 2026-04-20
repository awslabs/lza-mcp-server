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

"""Property test: Workspace-to-workspace copy completeness and metadata exclusion.

Feature: uc-workspace-rework, Property 5: Workspace-to-workspace copy completeness
and metadata exclusion

For any set of files in a UC workspace (including .session_metadata.json),
copyUcToLzaConfig SHALL copy all files except .session_metadata.json to the
LZA workspace, and the returned files_copied count SHALL equal the number of
non-metadata files in the source workspace.

**Validates: Requirements 9.1, 9.2, 9.4**
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

# Whether to include .session_metadata.json
_include_metadata = st.booleans()


# Feature: uc-workspace-rework, Property 5: Workspace-to-workspace copy completeness and metadata exclusion
@pytest.mark.property
class TestCopyCompleteness:
    """Property 5: Workspace-to-workspace copy completeness and metadata exclusion.

    For any set of files in a UC workspace (including .session_metadata.json),
    copyUcToLzaConfig SHALL copy all files except .session_metadata.json to the
    LZA workspace, and the returned files_copied count SHALL equal the number of
    non-metadata files in the source workspace.

    **Validates: Requirements 9.1, 9.2, 9.4**
    """

    @given(files=_file_set, include_metadata=_include_metadata)
    @settings(max_examples=100, deadline=None)
    def test_copy_completeness_and_metadata_exclusion(self, files, include_metadata):
        """All non-metadata files are copied; metadata is excluded; count matches."""
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

            # Optionally add .session_metadata.json
            if include_metadata:
                wm.write_file(
                    uc_ws,
                    ".session_metadata.json",
                    b'{"network_model": "test", "uc_release": "v1.0.0"}',
                )

            ctx = AsyncMock()
            ctx.info = AsyncMock()

            # Act
            result = asyncio.run(copy_uc_to_lza_config(ctx, uc_ws, lza_ws, wm))

            # Assert
            assert result["success"] is True

            # files_copied should equal number of non-metadata source files
            expected_count = len(source_paths)
            assert result["files_copied"] == expected_count

            # LZA workspace should contain exactly the non-metadata files
            lza_files = set(wm.list_files(lza_ws))
            assert lza_files == source_paths

            # .session_metadata.json should NOT be in LZA workspace
            assert ".session_metadata.json" not in lza_files
