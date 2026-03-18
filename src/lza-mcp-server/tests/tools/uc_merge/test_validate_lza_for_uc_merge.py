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

"""Tests for validate_lza_for_uc_merge tool."""

import pytest
from unittest.mock import AsyncMock
import yaml

from awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge import (
    validate_lza_for_uc_merge,
)


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


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_fresh_installation_success(
    mock_ctx,
    tmp_path,
    fresh_accounts_config,
    minimal_network_config,
    minimal_iam_config,
    monkeypatch,
):
    """Test validation passes for fresh installation."""
    # Setup test directory
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create config files
    (config_dir / "accounts-config.yaml").write_text(yaml.dump(fresh_accounts_config))
    (config_dir / "network-config.yaml").write_text(yaml.dump(minimal_network_config))
    (config_dir / "iam-config.yaml").write_text(yaml.dump(minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
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
    tmp_path,
    non_fresh_accounts_config,
    minimal_network_config,
    minimal_iam_config,
    monkeypatch,
):
    """Test validation fails when workload accounts exist."""
    # Setup test directory
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create config files
    (config_dir / "accounts-config.yaml").write_text(
        yaml.dump(non_fresh_accounts_config)
    )
    (config_dir / "network-config.yaml").write_text(yaml.dump(minimal_network_config))
    (config_dir / "iam-config.yaml").write_text(yaml.dump(minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "accounts" in result["context"]["failed_checks"]
    # Check the validation results contain the detailed message
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
    tmp_path,
    fresh_accounts_config,
    non_minimal_network_config,
    minimal_iam_config,
    monkeypatch,
):
    """Test validation fails when network config is not minimal."""
    # Setup test directory
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create config files
    (config_dir / "accounts-config.yaml").write_text(yaml.dump(fresh_accounts_config))
    (config_dir / "network-config.yaml").write_text(
        yaml.dump(non_minimal_network_config)
    )
    (config_dir / "iam-config.yaml").write_text(yaml.dump(minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "network" in result["context"]["failed_checks"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_non_minimal_iam(
    mock_ctx,
    tmp_path,
    fresh_accounts_config,
    minimal_network_config,
    non_minimal_iam_config,
    monkeypatch,
):
    """Test validation fails when IAM config is not minimal."""
    # Setup test directory
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create config files
    (config_dir / "accounts-config.yaml").write_text(yaml.dump(fresh_accounts_config))
    (config_dir / "network-config.yaml").write_text(yaml.dump(minimal_network_config))
    (config_dir / "iam-config.yaml").write_text(yaml.dump(non_minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    assert "iam" in result["context"]["failed_checks"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_config_not_retrieved(mock_ctx, tmp_path, monkeypatch):
    """Test validation fails when config directory doesn't exist."""
    # Patch the base path to non-existent directory
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "CONFIG_NOT_RETRIEVED"
    assert "getLzaConfiguration()" in result["error"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_missing_accounts_file(
    mock_ctx, tmp_path, minimal_network_config, minimal_iam_config, monkeypatch
):
    """Test validation fails when accounts-config.yaml is missing."""
    # Setup test directory without accounts-config.yaml
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    (config_dir / "network-config.yaml").write_text(yaml.dump(minimal_network_config))
    (config_dir / "iam-config.yaml").write_text(yaml.dump(minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "FILE_NOT_FOUND"
    assert "accounts-config.yaml" in result["error"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_validate_multiple_failures(
    mock_ctx,
    tmp_path,
    non_fresh_accounts_config,
    non_minimal_network_config,
    non_minimal_iam_config,
    monkeypatch,
):
    """Test validation reports all failures."""
    # Setup test directory
    config_dir = tmp_path / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create config files with multiple issues
    (config_dir / "accounts-config.yaml").write_text(
        yaml.dump(non_fresh_accounts_config)
    )
    (config_dir / "network-config.yaml").write_text(
        yaml.dump(non_minimal_network_config)
    )
    (config_dir / "iam-config.yaml").write_text(yaml.dump(non_minimal_iam_config))

    # Patch the base path
    monkeypatch.setattr(
        "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
        tmp_path,
    )

    # Run validation
    result = await validate_lza_for_uc_merge(mock_ctx)

    # Assertions
    assert result["success"] is False
    assert result["error_code"] == "NOT_FRESH_INSTALLATION"
    failed_checks = result["context"]["failed_checks"]
    assert "accounts" in failed_checks
    assert "network" in failed_checks
    assert "iam" in failed_checks
    assert len(failed_checks) == 3
