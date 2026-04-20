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

"""Unit tests for reworked validateLzaForUcMerge using WorkspaceManager.

Tests cover: valid workspace, missing workspace_id, missing files,
failed validation checks, workspace errors.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock

from awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge import (
    validate_lza_for_uc_merge,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.fixture
def fresh_accounts():
    return {"workloadAccounts": []}


@pytest.fixture
def minimal_network():
    return {"transitGateways": [], "endpointPolicies": [], "vpcs": []}


@pytest.fixture
def minimal_iam():
    return {
        "providers": [],
        "policySets": [],
        "roleSets": [],
        "groupSets": [],
        "userSets": [],
    }


def _make_wm(file_map):
    """Create a mock WorkspaceManager that returns bytes from file_map."""
    wm = MagicMock()

    def read_file(ws_id, path, context=None):
        if path in file_map:
            return file_map[path]
        raise WorkspaceNotFoundError(f"File '{path}' not found in workspace '{ws_id}'")

    wm.read_file = MagicMock(side_effect=read_file)
    return wm


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaWorkspaceSuccess:
    """Tests for successful validation with workspace."""

    @pytest.mark.asyncio
    async def test_fresh_installation_passes(
        self, mock_ctx, fresh_accounts, minimal_network, minimal_iam
    ):
        """Req 6.1, 6.4, 6.5: Valid workspace with fresh config passes all checks."""
        # Arrange
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "network-config.yaml": yaml.dump(minimal_network).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        # Act
        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        # Assert
        assert result["success"] is True
        assert result["validation_passed"] is True
        assert result["checks"]["accounts"]["passed"] is True
        assert result["checks"]["network"]["passed"] is True
        assert result["checks"]["iam"]["passed"] is True
        assert "get_uc_releases" in result["next_steps"]

    @pytest.mark.asyncio
    async def test_with_path_prefix(
        self, mock_ctx, fresh_accounts, minimal_network, minimal_iam
    ):
        """Req 6.1: Reads files from {path}/{filename} when path is provided."""
        # Arrange
        wm = _make_wm(
            {
                "config/accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "config/network-config.yaml": yaml.dump(minimal_network).encode(),
                "config/iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        # Act
        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "config", wm)

        # Assert
        assert result["success"] is True
        assert result["validation_passed"] is True
        wm.read_file.assert_any_call("abcdef123456", "config/accounts-config.yaml")
        wm.read_file.assert_any_call("abcdef123456", "config/network-config.yaml")
        wm.read_file.assert_any_call("abcdef123456", "config/iam-config.yaml")


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaWorkspaceMissingId:
    """Tests for missing workspace_id."""

    @pytest.mark.asyncio
    async def test_empty_workspace_id(self, mock_ctx):
        """Req 6.2: Returns error when workspace_id is empty."""
        wm = MagicMock()
        result = await validate_lza_for_uc_merge(mock_ctx, "", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "MISSING_WORKSPACE_ID"
        assert "workspace_id" in result["error"]

    @pytest.mark.asyncio
    async def test_none_workspace_id(self, mock_ctx):
        """Req 6.2: Returns error when workspace_id is None."""
        wm = MagicMock()
        result = await validate_lza_for_uc_merge(mock_ctx, None, "", wm)

        assert result["success"] is False
        assert result["error_code"] == "MISSING_WORKSPACE_ID"


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaWorkspaceMissingFiles:
    """Tests for missing config files in workspace."""

    @pytest.mark.asyncio
    async def test_missing_accounts_config(
        self, mock_ctx, minimal_network, minimal_iam
    ):
        """Req 6.3: Returns FILE_NOT_FOUND when accounts-config.yaml is missing."""
        wm = _make_wm(
            {
                "network-config.yaml": yaml.dump(minimal_network).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "accounts-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_network_config(self, mock_ctx, fresh_accounts, minimal_iam):
        """Req 6.3: Returns FILE_NOT_FOUND when network-config.yaml is missing."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "network-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_iam_config(self, mock_ctx, fresh_accounts, minimal_network):
        """Req 6.3: Returns FILE_NOT_FOUND when iam-config.yaml is missing."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "network-config.yaml": yaml.dump(minimal_network).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "iam-config.yaml" in result["error"]


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaWorkspaceFailedChecks:
    """Tests for failed validation checks."""

    @pytest.mark.asyncio
    async def test_non_fresh_accounts(self, mock_ctx, minimal_network, minimal_iam):
        """Req 6.4: Fails when workload accounts exist."""
        non_fresh = {"workloadAccounts": [{"name": "Dev"}, {"name": "Prod"}]}
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(non_fresh).encode(),
                "network-config.yaml": yaml.dump(minimal_network).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "accounts" in result["context"]["failed_checks"]

    @pytest.mark.asyncio
    async def test_non_minimal_network(self, mock_ctx, fresh_accounts, minimal_iam):
        """Req 6.4: Fails when network config has VPCs."""
        non_minimal = {
            "transitGateways": [],
            "endpointPolicies": [],
            "vpcs": [{"name": "v1"}],
        }
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "network-config.yaml": yaml.dump(non_minimal).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "network" in result["context"]["failed_checks"]

    @pytest.mark.asyncio
    async def test_non_minimal_iam(self, mock_ctx, fresh_accounts, minimal_network):
        """Req 6.4: Fails when IAM config has roles."""
        non_minimal = {
            "providers": [],
            "policySets": [],
            "roleSets": [{"name": "Admin"}],
            "groupSets": [],
            "userSets": [],
        }
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts).encode(),
                "network-config.yaml": yaml.dump(minimal_network).encode(),
                "iam-config.yaml": yaml.dump(non_minimal).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "iam" in result["context"]["failed_checks"]

    @pytest.mark.asyncio
    async def test_multiple_failures(self, mock_ctx):
        """Req 6.4: Reports all failed checks."""
        non_fresh_accounts = {"workloadAccounts": [{"name": "Dev"}]}
        non_minimal_network = {
            "transitGateways": [],
            "endpointPolicies": [],
            "vpcs": [{"name": "v1"}],
        }
        non_minimal_iam = {
            "providers": [],
            "policySets": [],
            "roleSets": [{"name": "Admin"}],
            "groupSets": [],
            "userSets": [],
        }
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(non_fresh_accounts).encode(),
                "network-config.yaml": yaml.dump(non_minimal_network).encode(),
                "iam-config.yaml": yaml.dump(non_minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        failed = result["context"]["failed_checks"]
        assert "accounts" in failed
        assert "network" in failed
        assert "iam" in failed


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaWorkspaceErrors:
    """Tests for workspace error handling."""

    @pytest.mark.asyncio
    async def test_workspace_not_found(self, mock_ctx):
        """Req 6.3: Returns WORKSPACE_NOT_FOUND when workspace doesn't exist."""
        wm = MagicMock()
        wm.read_file = MagicMock(
            side_effect=WorkspaceNotFoundError("Workspace 'bad123bad123' not found")
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "bad123bad123", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_workspace_validation_error(self, mock_ctx):
        """Returns WORKSPACE_VALIDATION_ERROR for invalid paths."""
        wm = MagicMock()
        wm.read_file = MagicMock(
            side_effect=WorkspaceValidationError("Path traversal detected")
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "../etc", wm)

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_workspace_storage_error(self, mock_ctx):
        """Returns WORKSPACE_STORAGE_ERROR for storage failures."""
        wm = MagicMock()
        wm.read_file = MagicMock(side_effect=WorkspaceStorageError("Disk full"))

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_STORAGE_ERROR"

    @pytest.mark.asyncio
    async def test_unexpected_error(self, mock_ctx):
        """Returns UNEXPECTED_ERROR for unknown exceptions outside file reads."""
        wm = MagicMock()
        # Simulate an error that occurs outside the per-file try blocks
        # by making ctx.info raise (which is called before any file reads)
        mock_ctx.info = AsyncMock(side_effect=RuntimeError("Something broke"))

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert result["context"]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_parse_error_in_accounts(
        self, mock_ctx, minimal_network, minimal_iam
    ):
        """Handles YAML parse errors gracefully."""
        wm = _make_wm(
            {
                "accounts-config.yaml": b"invalid: yaml: [",
                "network-config.yaml": yaml.dump(minimal_network).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "accounts" in result["context"]["failed_checks"]
