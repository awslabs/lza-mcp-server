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

"""Property test: Workspace path resolution for validation.

Feature: uc-workspace-rework, Property 1: Workspace path resolution for validation

For any valid workspace_id, optional path prefix, and set of LZA config files
stored in the workspace at that path, validateLzaForUcMerge SHALL read each file
from {path}/{filename} via WorkspaceManager and produce the same validation result
as parsing the file content directly.

**Validates: Requirements 6.1**
"""

import tempfile

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager
from awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge import (
    validate_lza_for_uc_merge,
)
from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_fresh_installation_accounts,
    validate_fresh_installation_iam,
    validate_fresh_installation_network,
)

# --- Strategies ---

# Path segment: lowercase alphanumeric with hyphens, 1-8 chars
_segment = st.from_regex(r"[a-z][a-z0-9\-]{0,7}", fullmatch=True)

# Optional path prefix: empty string or 1-3 segments joined by "/"
_path_prefix = st.one_of(
    st.just(""),
    st.builds(
        lambda parts: "/".join(parts), st.lists(_segment, min_size=1, max_size=3)
    ),
)

# Accounts config: either fresh (empty workloadAccounts) or non-fresh
_accounts_config = st.one_of(
    st.just({"workloadAccounts": []}),
    st.builds(
        lambda n: {"workloadAccounts": [{"name": f"wl-{i}"} for i in range(n)]},
        st.integers(min_value=1, max_value=3),
    ),
)

# Network config: either minimal (empty arrays) or non-minimal
_network_config = st.one_of(
    st.just({"transitGateways": [], "endpointPolicies": [], "vpcs": []}),
    st.just({"transitGateways": [], "endpointPolicies": [], "vpcs": [{"name": "v1"}]}),
)

# IAM config: either minimal (empty arrays) or non-minimal
_iam_config = st.one_of(
    st.just(
        {
            "providers": [],
            "policySets": [],
            "roleSets": [],
            "groupSets": [],
            "userSets": [],
        }
    ),
    st.just(
        {
            "providers": [],
            "policySets": [],
            "roleSets": [{"name": "r1"}],
            "groupSets": [],
            "userSets": [],
        }
    ),
)


# Feature: uc-workspace-rework, Property 1: Workspace path resolution for validation
@pytest.mark.property
class TestWorkspacePathResolutionForValidation:
    """Property 1: Workspace path resolution for validation.

    For any valid workspace_id, optional path prefix, and set of LZA config
    files stored in the workspace at that path, validateLzaForUcMerge SHALL
    read each file from {path}/{filename} via WorkspaceManager and produce
    the same validation result as parsing the file content directly.

    **Validates: Requirements 6.1**
    """

    @given(
        path_prefix=_path_prefix,
        accounts=_accounts_config,
        network=_network_config,
        iam=_iam_config,
    )
    @settings(max_examples=100, deadline=None)
    def test_path_resolution_matches_direct_parsing(
        self, path_prefix, accounts, network, iam
    ):
        """validateLzaForUcMerge reads from {path}/{filename} and produces
        the same validation result as parsing the file content directly."""
        import asyncio

        with tempfile.TemporaryDirectory() as td:
            # Arrange
            adapter = LocalAdapter(base_dir=td)
            wm = WorkspaceManager(storage=adapter)
            ws_id = wm.create_workspace()

            # Write config files at the path prefix
            prefix = f"{path_prefix}/" if path_prefix else ""
            wm.write_file(
                ws_id, f"{prefix}accounts-config.yaml", yaml.dump(accounts).encode()
            )
            wm.write_file(
                ws_id, f"{prefix}network-config.yaml", yaml.dump(network).encode()
            )
            wm.write_file(ws_id, f"{prefix}iam-config.yaml", yaml.dump(iam).encode())

            ctx = AsyncMock()
            ctx.info = AsyncMock()
            ctx.error = AsyncMock()

            # Act - run the tool
            result = asyncio.run(validate_lza_for_uc_merge(ctx, ws_id, path_prefix, wm))

            # Compute expected validation results directly
            acc_valid, acc_msg = validate_fresh_installation_accounts(accounts)
            net_valid, net_msg = validate_fresh_installation_network(network)
            iam_valid, iam_msg = validate_fresh_installation_iam(iam)
            all_passed = acc_valid and net_valid and iam_valid

            # Assert - tool result matches direct parsing
            if all_passed:
                assert result["success"] is True
                assert result["validation_passed"] is True
                assert result["checks"]["accounts"]["passed"] is True
                assert result["checks"]["network"]["passed"] is True
                assert result["checks"]["iam"]["passed"] is True
            else:
                assert result["success"] is False
                assert result["error_code"] == "NOT_FRESH_INSTALLATION"
                checks = result["context"]["validation_results"]
                assert checks["accounts"]["passed"] == acc_valid
                assert checks["network"]["passed"] == net_valid
                assert checks["iam"]["passed"] == iam_valid
