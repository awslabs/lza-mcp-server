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

"""Tests for validate_lza_for_uc_merge tool (workspace-based)."""

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock

from awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge import (
    validate_lza_for_uc_merge,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceNotFoundError


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.fixture
def fresh_accounts_config():
    """Fresh accounts configuration with only mandatory accounts."""
    return {
        "mandatoryAccounts": [
            {"name": "Management", "email": "mgmt@example.com"},
            {"name": "LogArchive", "email": "log@example.com"},
            {"name": "Audit", "email": "audit@example.com"},
        ],
        "workloadAccounts": [],
    }


@pytest.fixture
def non_fresh_accounts_config():
    """Non-fresh accounts configuration with workload accounts."""
    return {
        "mandatoryAccounts": [
            {"name": "Management", "email": "mgmt@example.com"},
            {"name": "LogArchive", "email": "log@example.com"},
            {"name": "Audit", "email": "audit@example.com"},
        ],
        "workloadAccounts": [
            {"name": "Dev", "email": "dev@example.com"},
            {"name": "Prod", "email": "prod@example.com"},
        ],
    }


@pytest.fixture
def minimal_network_config():
    """Minimal network configuration."""
    return {"transitGateways": [], "endpointPolicies": [], "vpcs": []}


@pytest.fixture
def non_minimal_network_config():
    """Non-minimal network configuration with VPCs."""
    return {
        "transitGateways": [],
        "endpointPolicies": [],
        "vpcs": [{"name": "vpc-1", "cidr": "10.0.0.0/16"}],
    }


@pytest.fixture
def minimal_iam_config():
    """Minimal IAM configuration."""
    return {
        "providers": [],
        "policySets": [],
        "roleSets": [],
        "groupSets": [],
        "userSets": [],
    }


@pytest.fixture
def non_minimal_iam_config():
    """Non-minimal IAM configuration with roles."""
    return {
        "providers": [],
        "policySets": [],
        "roleSets": [{"name": "AdminRole"}],
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
@pytest.mark.asyncio
async def test_validate_fresh_installation_success(
    mock_ctx,
    fresh_accounts_config,
    minimal_network_config,
    minimal_iam_config,
):
    """Test validation passes for fresh installation."""
    # Arrange
    wm = _make_wm(
        {
            "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
            "network-config.yaml": yaml.dump(minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
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


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_non_fresh_accounts(
    mock_ctx,
    non_fresh_accounts_config,
    minimal_network_config,
    minimal_iam_config,
):
    """Test validation fails when workload accounts exist."""
    wm = _make_wm(
        {
            "accounts-config.yaml": yaml.dump(non_fresh_accounts_config).encode(),
            "network-config.yaml": yaml.dump(minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
        }
    )

    result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "accounts" in result["context"]["failed_checks"]
    validation_results = result["context"]["validation_results"]
    assert (
        "workloadAccounts contains 2 accounts"
        in validation_results["accounts"]["message"]
    )


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_non_minimal_network(
    mock_ctx,
    fresh_accounts_config,
    non_minimal_network_config,
    minimal_iam_config,
):
    """Test validation fails when network config is not minimal."""
    wm = _make_wm(
        {
            "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
            "network-config.yaml": yaml.dump(non_minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
        }
    )

    result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "network" in result["context"]["failed_checks"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_non_minimal_iam(
    mock_ctx,
    fresh_accounts_config,
    minimal_network_config,
    non_minimal_iam_config,
):
    """Test validation fails when IAM config is not minimal."""
    wm = _make_wm(
        {
            "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
            "network-config.yaml": yaml.dump(minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(non_minimal_iam_config).encode(),
        }
    )

    result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "iam" in result["context"]["failed_checks"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_config_not_retrieved(mock_ctx):
    """Test validation fails when workspace_id is not provided."""
    wm = MagicMock()

    result = await validate_lza_for_uc_merge(mock_ctx, "", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "MISSING_WORKSPACE_ID"
    assert "workspace_id" in result["error"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_missing_accounts_file(
    mock_ctx, minimal_network_config, minimal_iam_config
):
    """Test validation fails when accounts-config.yaml is missing."""
    wm = _make_wm(
        {
            "network-config.yaml": yaml.dump(minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
        }
    )

    result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "FILE_NOT_FOUND"
    assert "accounts-config.yaml" in result["error"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_multiple_failures(
    mock_ctx,
    non_fresh_accounts_config,
    non_minimal_network_config,
    non_minimal_iam_config,
):
    """Test validation reports all failures."""
    wm = _make_wm(
        {
            "accounts-config.yaml": yaml.dump(non_fresh_accounts_config).encode(),
            "network-config.yaml": yaml.dump(non_minimal_network_config).encode(),
            "iam-config.yaml": yaml.dump(non_minimal_iam_config).encode(),
        }
    )

    result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    failed_checks = result["context"]["failed_checks"]
    assert "accounts" in failed_checks
    assert "network" in failed_checks
    assert "iam" in failed_checks
    assert len(failed_checks) == 3
