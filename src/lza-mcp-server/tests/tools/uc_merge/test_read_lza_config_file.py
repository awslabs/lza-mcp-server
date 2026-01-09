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
from hypothesis import given, strategies as st, settings, HealthCheck

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
# Property-Based Tests
# ============================================================================


# Feature: uc-merge, Property 5: Path traversal rejection
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
)
@given(
    path_with_dots=st.one_of(
        st.just("../accounts-config.yaml"),
        st.just("../../etc/passwd"),
        st.just("subdir/../../../etc/passwd"),
        st.just("./../../config.yaml"),
        st.text(min_size=1).filter(lambda x: ".." in x),
    )
)
def test_property_path_traversal_rejection(
    mock_ctx, temp_lza_config, path_with_dots, monkeypatch
):
    """Property 5: Path traversal rejection.

    For any file path containing double-dot sequences (..), read_lza_config_file
    should reject the request and return a path traversal error.

    Validates: Requirements 3.2
    """
    import asyncio

    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = asyncio.run(read_lza_config_file(mock_ctx, path_with_dots))

    assert result["success"] is False
    assert result["error_code"] == "PATH_TRAVERSAL"
    assert result["category"] == ErrorCategory.SECURITY
    assert "path traversal" in result["error"].lower() or ".." in result["error"]


# Feature: uc-merge, Property 6: Directory boundary enforcement
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
)
@given(
    absolute_path=st.one_of(
        st.just("/etc/passwd"),
        st.just("/tmp/config.yaml"),
        st.just("/root/.ssh/id_rsa"),
        st.text(min_size=2).filter(
            lambda x: x.startswith("/") and not x.startswith("/app/lza-config")
        ),
    )
)
def test_property_directory_boundary_enforcement(
    mock_ctx, temp_lza_config, absolute_path, monkeypatch
):
    """Property 6: Directory boundary enforcement.

    For any file path that resolves outside the designated directory boundary,
    read_lza_config_file should reject the request and return a security error.

    Validates: Requirements 3.3
    """
    import asyncio

    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    result = asyncio.run(read_lza_config_file(mock_ctx, absolute_path))

    assert result["success"] is False
    assert result["error_code"] in ["BOUNDARY_VIOLATION", "PATH_TRAVERSAL"]
    assert result["category"] == ErrorCategory.SECURITY


# Feature: uc-merge, Property 8: Successful read response structure
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
)
@given(
    file_content=st.text(min_size=0, max_size=1000),
    file_name=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_."
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x[0].isalnum() and x[-1].isalnum()),
)
def test_property_successful_read_response_structure(
    mock_ctx, temp_lza_config, file_content, file_name, monkeypatch
):
    """Property 8: Successful read response structure.

    For any successfully read file, the response should contain file_path,
    content, size_bytes, and next_steps fields.

    Validates: Requirements 3.4
    """
    import asyncio

    # Patch the LZA_CONFIG_BASE_PATH to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_lza_config_file as module

    monkeypatch.setattr(module, "LZA_CONFIG_BASE_PATH", temp_lza_config.parent)

    # Create a random file with the generated content
    file_path = temp_lza_config / f"{file_name}.yaml"
    file_path.write_text(file_content, encoding="utf-8")

    # Read back the content to get the normalized version (handles line endings)
    expected_content = file_path.read_text(encoding="utf-8")

    result = asyncio.run(read_lza_config_file(mock_ctx, f"{file_name}.yaml"))

    # Verify response structure for successful reads
    if result["success"]:
        assert "file_path" in result
        assert "content" in result
        assert "size_bytes" in result
        assert "next_steps" in result
        assert result["content"] == expected_content
        assert result["size_bytes"] == len(expected_content.encode("utf-8"))


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
    assert "getConfigurationFromS3" in result["error"]
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
