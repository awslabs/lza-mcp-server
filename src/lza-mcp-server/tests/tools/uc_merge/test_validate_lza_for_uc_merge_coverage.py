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

"""Additional coverage tests for validate_lza_for_uc_merge tool."""

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
def minimal_network_config():
    """Minimal network configuration."""
    return {"transitGateways": [], "endpointPolicies": [], "vpcs": []}


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


@pytest.mark.unit
@pytest.mark.uc_merge
class TestValidateLzaForUcMergeCoverage:
    """Additional coverage tests for validate_lza_for_uc_merge tool."""

    @pytest.mark.asyncio
    async def test_accounts_config_parse_error(
        self,
        mock_ctx,
        tmp_path,
        minimal_network_config,
        minimal_iam_config,
        monkeypatch,
    ):
        """Test handling of accounts config parse error.

        Covers lines 116-117, 122: Exception handling when parsing accounts config
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create invalid YAML file
        (config_dir / "accounts-config.yaml").write_text("invalid: yaml: content: [")
        (config_dir / "network-config.yaml").write_text(
            yaml.dump(minimal_network_config)
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
        assert "accounts" in result["context"]["failed_checks"]
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["accounts"]["message"]

    @pytest.mark.asyncio
    async def test_network_config_parse_error(
        self, mock_ctx, tmp_path, fresh_accounts_config, minimal_iam_config, monkeypatch
    ):
        """Test handling of network config parse error.

        Covers lines 143-144, 149: Exception handling when parsing network config
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create config files with invalid network YAML
        (config_dir / "accounts-config.yaml").write_text(
            yaml.dump(fresh_accounts_config)
        )
        (config_dir / "network-config.yaml").write_text("invalid: yaml: content: [")
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
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["network"]["message"]

    @pytest.mark.asyncio
    async def test_iam_config_parse_error(
        self,
        mock_ctx,
        tmp_path,
        fresh_accounts_config,
        minimal_network_config,
        monkeypatch,
    ):
        """Test handling of IAM config parse error.

        Covers lines 170-171, 176: Exception handling when parsing IAM config
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Create config files with invalid IAM YAML
        (config_dir / "accounts-config.yaml").write_text(
            yaml.dump(fresh_accounts_config)
        )
        (config_dir / "network-config.yaml").write_text(
            yaml.dump(minimal_network_config)
        )
        (config_dir / "iam-config.yaml").write_text("invalid: yaml: content: [")

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
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["iam"]["message"]

    @pytest.mark.asyncio
    async def test_missing_network_config_file(
        self, mock_ctx, tmp_path, fresh_accounts_config, minimal_iam_config, monkeypatch
    ):
        """Test validation fails when network-config.yaml is missing."""
        # Setup test directory without network-config.yaml
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        (config_dir / "accounts-config.yaml").write_text(
            yaml.dump(fresh_accounts_config)
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
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "network-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_iam_config_file(
        self,
        mock_ctx,
        tmp_path,
        fresh_accounts_config,
        minimal_network_config,
        monkeypatch,
    ):
        """Test validation fails when iam-config.yaml is missing."""
        # Setup test directory without iam-config.yaml
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        (config_dir / "accounts-config.yaml").write_text(
            yaml.dump(fresh_accounts_config)
        )
        (config_dir / "network-config.yaml").write_text(
            yaml.dump(minimal_network_config)
        )

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
        assert "iam-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_unexpected_error_during_validation(
        self, mock_ctx, tmp_path, monkeypatch
    ):
        """Test handling of unexpected errors during validation.

        Covers lines 208-221: General exception handling
        """
        # Setup test directory
        config_dir = tmp_path / "retrieved-config"
        config_dir.mkdir(parents=True)

        # Patch the base path
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.validate_lza_for_uc_merge.LZA_CONFIG_BASE_PATH",
            tmp_path,
        )

        # Mock Path.exists to raise an exception
        from pathlib import Path
        from unittest.mock import patch

        def mock_exists(self):
            # Let the first check pass (base_directory.exists())
            if str(self).endswith("retrieved-config"):
                return True
            # Raise exception on subsequent checks
            raise RuntimeError("Unexpected filesystem error")

        with patch.object(Path, "exists", mock_exists):
            result = await validate_lza_for_uc_merge(mock_ctx)

        # Assertions
        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "Unexpected error" in result["error"]
        assert "context" in result
        assert result["context"]["error_type"] == "RuntimeError"
