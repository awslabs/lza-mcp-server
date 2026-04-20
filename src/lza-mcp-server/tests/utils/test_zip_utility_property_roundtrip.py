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

"""Property tests for ZipUtility zip round-trip (Property 6)."""

import io
import tempfile
import zipfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.utils.zip_utility import ZipUtility

# Strategy: valid relative path segments (lowercase only to avoid macOS case-insensitive collisions)
_segment = st.from_regex(r"[a-z][a-z0-9_\-]{0,11}", fullmatch=True)

# Strategy: flat file paths only (single segment) to avoid file/directory conflicts
# where "a" is both a file and a directory prefix
_flat_path = _segment


# Strategy: a file entry is a (path, content) pair
_file_entry = st.tuples(_flat_path, st.binary(min_size=1, max_size=2048))

# Strategy: a non-empty set of file entries with unique paths
_file_set = st.lists(_file_entry, min_size=1, max_size=8).map(
    lambda entries: dict(entries)  # dedup by path
)


# Feature: workspace-and-templates, Property 6: Zip round-trip
@pytest.mark.property
class TestZipRoundTrip:
    """Property 6: For any workspace containing any set of files,
    creating a zip archive and extracting it should produce files
    with identical content and relative paths."""

    @given(files=_file_set)
    @settings(max_examples=100, deadline=None)
    def test_zip_roundtrip_all_files(self, files):
        """Zip all workspace files, extract, compare contents."""
        with tempfile.TemporaryDirectory() as td:
            # Arrange
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()

            for path, content in files.items():
                wm.write_file(ws_id, path, content)

            source_paths = list(files.keys())
            zip_dest = "output.zip"

            # Act — create zip
            zu.create_zip(ws_id, source_paths, zip_dest)

            # Read the zip back and extract in-memory
            zip_bytes = wm.read_file(ws_id, zip_dest)

            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                archived_names = set(zf.namelist())
                # Assert — same set of paths
                assert archived_names == set(files.keys())
                # Assert — identical content for each file
                for name in archived_names:
                    assert zf.read(name) == files[name]

    @given(files=_file_set)
    @settings(max_examples=100, deadline=None)
    def test_zip_roundtrip_folder_source(self, files):
        """Zip a folder source, extract, compare contents."""
        with tempfile.TemporaryDirectory() as td:
            # Arrange — put all files under a "data/" prefix
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            zu = ZipUtility(workspace_manager=wm)
            ws_id = wm.create_workspace()

            prefixed = {f"data/{path}": content for path, content in files.items()}
            for path, content in prefixed.items():
                wm.write_file(ws_id, path, content)

            zip_dest = "archive.zip"

            # Act — zip the folder
            zu.create_zip(ws_id, ["data"], zip_dest)

            # Read the zip back
            zip_bytes = wm.read_file(ws_id, zip_dest)

            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                archived_names = set(zf.namelist())
                assert archived_names == set(prefixed.keys())
                for name in archived_names:
                    assert zf.read(name) == prefixed[name]
