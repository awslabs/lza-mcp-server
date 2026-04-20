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

"""Property tests for user scoping, hashing, and no-auth pass-through."""

import hashlib
import tempfile
from typing import Any, Optional

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
)


class FakeAuthAdapter:
    """Auth adapter that returns a fixed user ID."""

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    def get_user_id(self, context: Any) -> Optional[str]:
        return self._user_id


class NoneAuthAdapter:
    """Auth adapter that always returns None."""

    def get_user_id(self, context: Any) -> Optional[str]:
        return None


# Feature: workspace-and-templates, Property 11: User scoping isolation
@pytest.mark.property
class TestUserScopingIsolation:
    """Property 11: Two distinct users cannot see each other's workspaces."""

    @given(
        user_a=st.text(
            min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N"))
        ),
        user_b=st.text(
            min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N"))
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_user_isolation(self, user_a, user_b):
        assume(user_a != user_b)

        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)

            wm_a = WorkspaceManager(storage=adapter, auth=FakeAuthAdapter(user_a))
            wm_b = WorkspaceManager(storage=adapter, auth=FakeAuthAdapter(user_b))

            ws_a = wm_a.create_workspace()
            wm_a.write_file(ws_a, "a.txt", b"data-a")

            ws_b = wm_b.create_workspace()
            wm_b.write_file(ws_b, "b.txt", b"data-b")

            # User A sees only their workspace
            assert ws_a in wm_a.list_workspaces()
            assert ws_b not in wm_a.list_workspaces()

            # User B sees only their workspace
            assert ws_b in wm_b.list_workspaces()
            assert ws_a not in wm_b.list_workspaces()

            # Cross-access should fail
            with pytest.raises(WorkspaceNotFoundError):
                wm_a.read_file(ws_b, "b.txt")

            with pytest.raises(WorkspaceNotFoundError):
                wm_b.read_file(ws_a, "a.txt")


# Feature: workspace-and-templates, Property 12: User directory is one-way hash
@pytest.mark.property
class TestUserDirectoryHash:
    """Property 12: Per-user directory name equals SHA-256 hex digest."""

    @given(user_id=st.text(min_size=1, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_scope_is_sha256(self, user_id):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter, auth=FakeAuthAdapter(user_id))

            expected_hash = hashlib.sha256(user_id.encode()).hexdigest()
            scope = wm._get_scope()

            assert scope == expected_hash

    @given(
        user_a=st.text(min_size=1, max_size=50),
        user_b=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100, deadline=None)
    def test_distinct_users_distinct_hashes(self, user_a, user_b):
        """Collision resistance: distinct IDs produce distinct directories."""
        assume(user_a != user_b)

        hash_a = hashlib.sha256(user_a.encode()).hexdigest()
        hash_b = hashlib.sha256(user_b.encode()).hexdigest()

        assert hash_a != hash_b


# Feature: workspace-and-templates, Property 13: No auth pass-through
@pytest.mark.property
class TestNoAuthPassThrough:
    """Property 13: Without an AuthAdapter, workspaces live under 'shared'."""

    @given(n=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50, deadline=None)
    def test_no_auth_uses_shared_scope(self, n):
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)

            assert wm._get_scope() == "shared"

            ids = []
            for _ in range(n):
                ws_id = wm.create_workspace()
                wm.write_file(ws_id, "f.txt", b"x")
                ids.append(ws_id)

            listed = wm.list_workspaces()
            for ws_id in ids:
                assert ws_id in listed

    @given(n=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50, deadline=None)
    def test_none_auth_adapter_uses_shared_scope(self, n):
        """AuthAdapter returning None behaves same as no adapter."""
        with tempfile.TemporaryDirectory() as td:
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter, auth=NoneAuthAdapter())

            assert wm._get_scope() == "shared"

            ids = []
            for _ in range(n):
                ws_id = wm.create_workspace()
                wm.write_file(ws_id, "f.txt", b"x")
                ids.append(ws_id)

            listed = wm.list_workspaces()
            for ws_id in ids:
                assert ws_id in listed
