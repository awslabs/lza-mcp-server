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

"""Property test: Session metadata round-trip.

Feature: uc-workspace-rework, Property 3: Session metadata round-trip

For any valid network_model and uc_release strings, writing session metadata
via start_uc_merge_session and then reading it back via WorkspaceManager.read_file
SHALL produce the same network_model and uc_release values.

**Validates: Requirements 7.3, 8.1**
"""

import asyncio
import json
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import AsyncMock, patch

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)

# --- Strategies ---

# Valid uc_release: vX.Y.Z format
_uc_release = st.builds(
    lambda major, minor, patch_v: f"v{major}.{minor}.{patch_v}",
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
)

# Valid network_model: lowercase letters, numbers, hyphens
_network_model = st.from_regex(r"[a-z][a-z0-9\-]{0,19}", fullmatch=True)


# Feature: uc-workspace-rework, Property 3: Session metadata round-trip
@pytest.mark.property
class TestSessionMetadataRoundTrip:
    """Property 3: Session metadata round-trip.

    For any valid network_model and uc_release strings, writing session
    metadata via start_uc_merge_session and then reading it back via
    WorkspaceManager.read_file SHALL produce the same network_model and
    uc_release values.

    **Validates: Requirements 7.3, 8.1**
    """

    @given(uc_release=_uc_release, network_model=_network_model)
    @settings(max_examples=100, deadline=None)
    def test_metadata_round_trip(self, uc_release, network_model):
        """Metadata written by start_uc_merge_session can be read back
        with identical network_model and uc_release values."""

        with tempfile.TemporaryDirectory() as td:
            # Arrange - create a minimal UC release directory
            uc_base = os.path.join(td, "uc")
            release_dir = os.path.join(uc_base, uc_release)
            model_dir = os.path.join(release_dir, network_model)
            os.makedirs(model_dir)

            # Create at least one file so the model dir is valid
            with open(os.path.join(model_dir, "config.yaml"), "w") as f:
                f.write("test: true")

            # Create workspace manager
            ws_dir = os.path.join(td, "workspaces")
            adapter = LocalAdapter(base_dir=ws_dir)
            wm = WorkspaceManager(storage=adapter)

            ctx = AsyncMock()
            ctx.info = AsyncMock()
            ctx.error = AsyncMock()

            import pathlib

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path",
                    return_value=pathlib.Path(release_dir),
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path",
                    return_value=pathlib.Path(model_dir),
                ),
            ):
                # Act - create session
                result = asyncio.run(
                    tool_start_uc_merge_session(ctx, uc_release, network_model, wm)
                )

            # Assert - session created successfully
            assert result["success"] is True
            workspace_id = result["workspace_id"]

            # Read back metadata
            metadata_bytes = wm.read_file(workspace_id, ".session_metadata.json")
            metadata = json.loads(metadata_bytes.decode())

            # Assert round-trip
            assert metadata["network_model"] == network_model
            assert metadata["uc_release"] == uc_release
            assert "created_at" in metadata
