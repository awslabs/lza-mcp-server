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

"""Additional coverage tests for validate_lza_for_uc_merge tool (workspace-based)."""

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
class TestValidateLzaForUcMergeCoverage:
    """Additional coverage tests for validate_lza_for_uc_merge tool."""

    @pytest.mark.asyncio
    async def test_accounts_config_parse_error(
        self, mock_ctx, minimal_network_config, minimal_iam_config
    ):
        """Test handling of accounts config parse error."""
        wm = _make_wm(
            {
                "accounts-config.yaml": b"invalid: yaml: content: [",
                "network-config.yaml": yaml.dump(minimal_network_config).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "accounts" in result["context"]["failed_checks"]
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["accounts"]["message"]

    @pytest.mark.asyncio
    async def test_network_config_parse_error(
        self, mock_ctx, fresh_accounts_config, minimal_iam_config
    ):
        """Test handling of network config parse error."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
                "network-config.yaml": b"invalid: yaml: content: [",
                "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "network" in result["context"]["failed_checks"]
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["network"]["message"]

    @pytest.mark.asyncio
    async def test_iam_config_parse_error(
        self, mock_ctx, fresh_accounts_config, minimal_network_config
    ):
        """Test handling of IAM config parse error."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
                "network-config.yaml": yaml.dump(minimal_network_config).encode(),
                "iam-config.yaml": b"invalid: yaml: content: [",
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "NOT_FRESH_INSTALLATION"
        assert "iam" in result["context"]["failed_checks"]
        validation_results = result["context"]["validation_results"]
        assert "Failed to parse" in validation_results["iam"]["message"]

    @pytest.mark.asyncio
    async def test_missing_network_config_file(
        self, mock_ctx, fresh_accounts_config, minimal_iam_config
    ):
        """Test validation fails when network-config.yaml is missing."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
                "iam-config.yaml": yaml.dump(minimal_iam_config).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "network-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_iam_config_file(
        self, mock_ctx, fresh_accounts_config, minimal_network_config
    ):
        """Test validation fails when iam-config.yaml is missing."""
        wm = _make_wm(
            {
                "accounts-config.yaml": yaml.dump(fresh_accounts_config).encode(),
                "network-config.yaml": yaml.dump(minimal_network_config).encode(),
            }
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "iam-config.yaml" in result["error"]

    @pytest.mark.asyncio
    async def test_unexpected_error_during_validation(self, mock_ctx):
        """Test handling of unexpected errors during validation."""
        wm = MagicMock()
        # Make ctx.info raise to trigger the outer exception handler
        mock_ctx.info = AsyncMock(
            side_effect=RuntimeError("Unexpected filesystem error")
        )

        result = await validate_lza_for_uc_merge(mock_ctx, "abcdef123456", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "Unexpected error" in result["error"]
        assert "context" in result
        assert result["context"]["error_type"] == "RuntimeError"
