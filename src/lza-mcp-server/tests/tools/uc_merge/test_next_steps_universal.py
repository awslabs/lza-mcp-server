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

"""Universal next_steps inclusion tests for UC merge tools.

Feature: uc-merge, Property 30: Universal next_steps inclusion
Validates: Requirements 10.1

This test file verifies that ALL UC merge tools include a next_steps field
in their responses, regardless of success or failure. This ensures consistent
workflow guidance for agents using these tools.
"""

import pytest
import os
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_releases import tool_get_uc_releases
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_models import (
    tool_get_uc_network_models,
)
from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    get_uc_network_customization_guide,
)
from awslabs.lza_mcp_server.tools.uc_merge.copy_uc_to_lza_config import (
    copy_uc_to_lza_config,
)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.fixture
def temp_uc_structure(tmp_path):
    """Create a temporary UC repository structure."""
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    # Create a release directory
    release_dir = uc_base / "v1.0.0"
    release_dir.mkdir()

    # Create network model directories
    hub_spoke = release_dir / "hub-and-spoke"
    hub_spoke.mkdir()

    shared_vpc = release_dir / "shared-vpc"
    shared_vpc.mkdir()

    # Create some config files
    (hub_spoke / "accounts-config.yaml").write_text("test: config")
    (hub_spoke / "replacements-config.yaml").write_text("test: replacements")

    return uc_base


# Feature: uc-merge, Property 30: Universal next_steps inclusion
# Validates: Requirements 10.1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_uc_releases_success_includes_next_steps(mock_ctx, temp_uc_structure):
    """Verify get_uc_releases includes next_steps on success."""
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        result = await tool_get_uc_releases(mock_ctx)
        assert "next_steps" in result
        assert isinstance(result["next_steps"], str)
        assert len(result["next_steps"]) > 0
    finally:
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_uc_network_models_success_includes_next_steps(
    mock_ctx, temp_uc_structure
):
    """Verify get_uc_network_models includes next_steps on success."""
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        result = await tool_get_uc_network_models(mock_ctx, "v1.0.0")
        assert "next_steps" in result
        assert isinstance(result["next_steps"], str)
        assert len(result["next_steps"]) > 0
    finally:
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_uc_network_models_error_includes_next_steps(mock_ctx):
    """Verify get_uc_network_models includes next_steps on error (missing parameter)."""
    result = await tool_get_uc_network_models(mock_ctx, "")
    assert "next_steps" in result
    assert isinstance(result["next_steps"], str)
    assert len(result["next_steps"]) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_uc_merge_session_error_includes_next_steps(mock_ctx):
    """Verify start_uc_merge_session includes next_steps on error (missing parameters)."""
    from unittest.mock import MagicMock

    wm = MagicMock()
    result = await tool_start_uc_merge_session(mock_ctx, "", "", workspace_manager=wm)
    assert "next_steps" in result
    assert isinstance(result["next_steps"], str)
    assert len(result["next_steps"]) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_uc_network_customization_guide_error_includes_next_steps(tmp_path):
    """Verify get_uc_network_customization_guide includes next_steps on error (missing workspace)."""
    from unittest.mock import MagicMock
    from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceNotFoundError

    mock_wm = MagicMock()
    mock_wm.read_file.side_effect = WorkspaceNotFoundError("Workspace '' not found")

    result = get_uc_network_customization_guide("", mock_wm)
    assert "next_steps" in result
    assert isinstance(result["next_steps"], str)
    assert len(result["next_steps"]) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_copy_uc_to_lza_config_error_includes_next_steps(mock_ctx):
    """Verify copy_uc_to_lza_config includes next_steps on error (missing workspace_id)."""
    from unittest.mock import MagicMock

    mock_wm = MagicMock()
    result = await copy_uc_to_lza_config(mock_ctx, "", "lza-ws-id", mock_wm)
    assert "next_steps" in result
    assert isinstance(result["next_steps"], str)
    assert len(result["next_steps"]) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_next_steps_contains_actionable_guidance(mock_ctx, temp_uc_structure):
    """Verify that next_steps contains actionable guidance, not just placeholder text."""
    original_env = os.environ.get("LZA_UC_BASE_PATH")
    os.environ["LZA_UC_BASE_PATH"] = str(temp_uc_structure)

    try:
        result = await tool_get_uc_releases(mock_ctx)
        next_steps = result["next_steps"]

        # Check for meaningful content
        assert len(next_steps) > 20, "next_steps should contain substantial guidance"

        # Should mention what to do next
        assert any(
            word in next_steps.lower()
            for word in ["call", "present", "select", "retry", "contact"]
        ), "next_steps should contain actionable verbs"
    finally:
        if original_env is not None:
            os.environ["LZA_UC_BASE_PATH"] = original_env
        elif "LZA_UC_BASE_PATH" in os.environ:
            del os.environ["LZA_UC_BASE_PATH"]
