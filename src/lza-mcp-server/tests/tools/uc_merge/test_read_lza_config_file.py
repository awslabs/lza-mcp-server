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

"""Tests for read_lza_config_file tool."""

import pytest
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.tools.uc_merge.read_lza_config_file import (
    read_lza_config_file,
    get_next_steps_for_file,
)
from awslabs.lza_mcp_server.error_categories import ErrorCategory


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


@pytest.fixture
def temp_lza_config(tmp_path):
    """Create a temporary LZA configuration directory structure."""
    # Create the base directory structure
    config_dir = tmp_path / "lza-config" / "retrieved-config"
    config_dir.mkdir(parents=True)

    # Create sample configuration files
    (config_dir / "accounts-config.yaml").write_text(
        "mandatoryAccounts:\n"
        "  - email: management@example.com\n"
        "    name: Management\n"
        "workloadAccounts: []\n"
    )

    (config_dir / "global-config.yaml").write_text(
        "homeRegion: us-east-1\nenabledRegions:\n  - us-east-1\n"
    )

    (config_dir / "network-config.yaml").write_text(
        "transitGateways: []\nvpcs: []\nendpointPolicies: []\n"
    )

    (config_dir / "iam-config.yaml").write_text(
        "providers: []\npolicySets: []\nroleSets: []\ngroupSets: []\nuserSets: []\n"
    )

    # Create a subdirectory with a file
    subdir = config_dir / "policies"
    subdir.mkdir()
    (subdir / "policy.json").write_text('{"Version": "2012-10-17"}')

    return config_dir


# ============================================================================
# Unit Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_read_valid_file(mock_ctx, temp_lza_config, monkeypatch):
    """Test reading a valid configuration file."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = await read_lza_config_file(mock_ctx, "accounts-config.yaml")

    assert result["success"] is True
    assert result["file_path"] == "accounts-config.yaml"
    assert "mandatoryAccounts" in result["content"]
    assert "workloadAccounts" in result["content"]
    assert result["size_bytes"] > 0
    assert "next_steps" in result
    assert "mandatory account emails" in result["next_steps"]


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_read_file_in_subdirectory(mock_ctx, temp_lza_config, monkeypatch):
    """Test reading a file in a subdirectory."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = await read_lza_config_file(mock_ctx, "policies/policy.json")

    assert result["success"] is True
    assert result["file_path"] == "policies/policy.json"
    assert "Version" in result["content"]
    assert result["size_bytes"] > 0


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_file_not_found(mock_ctx, temp_lza_config, monkeypatch):
    """Test error when file does not exist."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = await read_lza_config_file(mock_ctx, "nonexistent-file.yaml")

    assert result["success"] is False
    assert result["error_code"] == "FILE_NOT_FOUND"
    assert result["category"] == ErrorCategory.FILE_NOT_FOUND
    assert "not found" in result["error"].lower()
    assert "troubleshooting" in result
    assert "next_steps" in result


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_config_not_retrieved(mock_ctx, tmp_path, monkeypatch):
    """Test error when LZA configuration has not been retrieved."""
    # Patch the LZA_CONFIG_BASE_PATH to a non-existent directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", tmp_path / "nonexistent")

    result = await read_lza_config_file(mock_ctx, "accounts-config.yaml")

    assert result["success"] is False
    assert result["error_code"] == "CONFIG_NOT_RETRIEVED"
    assert result["category"] == ErrorCategory.CONFIGURATION
    assert "getLzaConfiguration" in result["error"]
    assert "troubleshooting" in result


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_path_is_directory(mock_ctx, temp_lza_config, monkeypatch):
    """Test error when path points to a directory instead of a file."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = await read_lza_config_file(mock_ctx, "policies")

    assert result["success"] is False
    assert result["error_code"] == "NOT_A_FILE"
    assert result["category"] == ErrorCategory.FILE_OPERATION
    assert "not a file" in result["error"].lower()


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_accounts_config():
    """Test next_steps guidance for accounts-config.yaml."""
    next_steps = get_next_steps_for_file("accounts-config.yaml")

    assert "mandatory account emails" in next_steps
    assert "workloadAccounts" in next_steps
    assert "empty" in next_steps.lower()


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_global_config():
    """Test next_steps guidance for global-config.yaml."""
    next_steps = get_next_steps_for_file("global-config.yaml")

    assert "homeRegion" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_network_config():
    """Test next_steps guidance for network-config.yaml."""
    next_steps = get_next_steps_for_file("network-config.yaml")

    assert "minimal configuration" in next_steps
    assert "transitGateways" in next_steps
    assert "vpcs" in next_steps
    assert "endpointPolicies" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_iam_config():
    """Test next_steps guidance for iam-config.yaml."""
    next_steps = get_next_steps_for_file("iam-config.yaml")

    assert "minimal configuration" in next_steps
    assert "providers" in next_steps
    assert "policySets" in next_steps
    assert "roleSets" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_other_files():
    """Test next_steps guidance for other files."""
    next_steps = get_next_steps_for_file("some-other-file.yaml")

    assert "review" in next_steps.lower()
    assert len(next_steps) > 0


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_empty_file_path(mock_ctx, temp_lza_config, monkeypatch):
    """Test error when file path is empty."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = await read_lza_config_file(mock_ctx, "")

    assert result["success"] is False
    # Empty file path is treated as a file operation error, not security
    assert result["category"] in [ErrorCategory.SECURITY, ErrorCategory.FILE_OPERATION]


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.uc_merge
async def test_read_file_with_special_characters(
    mock_ctx, temp_lza_config, monkeypatch
):
    """Test reading a file with special characters in content."""
    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    # Create a file with special characters
    special_content = "key: value with émojis 🎉 and spëcial çhars"
    (temp_lza_config / "special.yaml").write_text(special_content, encoding="utf-8")

    result = await read_lza_config_file(mock_ctx, "special.yaml")

    assert result["success"] is True
    assert result["content"] == special_content
