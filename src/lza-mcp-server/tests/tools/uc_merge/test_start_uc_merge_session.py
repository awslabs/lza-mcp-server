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

"""Unit tests for start_uc_merge_session tool (workspace-based API)."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.fixture
def mock_uc_structure(tmp_path):
    """Create a mock UC directory structure."""
    # Create UC base directory
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    # Create v1.0.0 release
    release_dir = uc_base / "v1.0.0"
    release_dir.mkdir()

    # Create network models
    hub_spoke_dir = release_dir / "hub-and-spoke"
    hub_spoke_dir.mkdir()

    shared_vpc_dir = release_dir / "shared-vpc"
    shared_vpc_dir.mkdir()

    # Create some sample files in hub-and-spoke
    (hub_spoke_dir / "accounts-config.yaml").write_text("test: config")
    (hub_spoke_dir / "network-config.yaml").write_text("network: config")

    # Create subdirectory with files
    policies_dir = hub_spoke_dir / "service-control-policies"
    policies_dir.mkdir()
    (policies_dir / "policy1.json").write_text('{"test": "policy"}')

    # Create some sample files in shared-vpc
    (shared_vpc_dir / "accounts-config.yaml").write_text("test: config")

    return uc_base


def _make_wm(workspace_id="uc-ws-test1234"):
    """Create a mock WorkspaceManager."""
    wm = MagicMock()
    wm.create_workspace.return_value = workspace_id
    written_files = {}

    def write_file(ws_id, path, content, context=None):
        written_files[path] = content

    wm.write_file = MagicMock(side_effect=write_file)
    wm._written_files = written_files
    return wm


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_with_valid_parameters(
    mock_ctx, mock_uc_structure, tmp_path
):
    """Test session creation with valid parameters."""
    wm = _make_wm(workspace_id="abcdef123456")

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v1.0.0",
            network_model="hub-and-spoke",
            workspace_manager=wm,
        )

    assert result["success"] is True
    assert result["workspace_id"] == "abcdef123456"
    assert result["uc_release"] == "v1.0.0"
    assert result["network_model"] == "hub-and-spoke"
    assert result["files_copied"] == 3
    assert "next_steps" in result
    assert "getLzaConfiguration" in result["next_steps"]

    # Verify workspace was created
    wm.create_workspace.assert_called_once()


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_missing_uc_release(mock_ctx):
    """Test error when uc_release parameter is missing."""
    wm = _make_wm()
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="",
        network_model="hub-and-spoke",
        workspace_manager=wm,
    )

    assert result["success"] is False
    assert result["error_code"] == "MISSING_PARAMETER"
    assert "uc_release" in result["error"]
    assert "get_uc_releases" in result["next_steps"]
    assert len(result["troubleshooting"]) > 0


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_missing_network_model(mock_ctx):
    """Test error when network_model parameter is missing."""
    wm = _make_wm()
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="v1.0.0",
        network_model="",
        workspace_manager=wm,
    )

    assert result["success"] is False
    assert result["error_code"] == "MISSING_PARAMETER"
    assert "network_model" in result["error"]
    assert "get_uc_network_models" in result["next_steps"]
    assert len(result["troubleshooting"]) > 0


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_invalid_uc_release_format(mock_ctx):
    """Test error when uc_release has invalid format."""
    wm = _make_wm()
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="1.0.0",  # Missing 'v' prefix
        network_model="hub-and-spoke",
        workspace_manager=wm,
    )

    assert result["success"] is False
    assert result["error_code"] == "INVALID_UC_RELEASE"
    assert "format" in result["error"].lower()
    assert "get_uc_releases" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_invalid_network_model_format(mock_ctx):
    """Test error when network_model has invalid format."""
    wm = _make_wm()
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="v1.0.0",
        network_model="Hub_And_Spoke",  # Invalid characters
        workspace_manager=wm,
    )

    assert result["success"] is False
    assert result["error_code"] == "INVALID_NETWORK_MODEL"
    assert "format" in result["error"].lower()
    assert "get_uc_network_models" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_uc_release_not_found(mock_ctx, tmp_path):
    """Test error when uc_release does not exist."""
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()
    v1_dir = uc_base / "v1.0.0"
    v1_dir.mkdir()

    wm = _make_wm()

    with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v2.0.0",
            network_model="hub-and-spoke",
            workspace_manager=wm,
        )

    assert result["success"] is False
    assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
    assert "does not exist" in result["error"]
    assert "available_releases" in result["context"]
    assert "v1.0.0" in result["context"]["available_releases"]
    assert "get_uc_releases" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_network_model_not_found(mock_ctx, mock_uc_structure):
    """Test error when network_model does not exist in the release."""
    wm = _make_wm()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        release_path = mock_uc_structure / "v1.0.0"
        mock_release_path.return_value = release_path
        mock_model_path.return_value = release_path / "non-existent-model"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v1.0.0",
            network_model="non-existent-model",
            workspace_manager=wm,
        )

    assert result["success"] is False
    assert result["error_code"] == "NETWORK_MODEL_NOT_FOUND"
    assert "does not exist" in result["error"]
    assert "available_models" in result["context"]
    assert "hub-and-spoke" in result["context"]["available_models"]
    assert "shared-vpc" in result["context"]["available_models"]
    assert "get_uc_network_models" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_file_copying(mock_ctx, mock_uc_structure, tmp_path):
    """Test that files are copied correctly to the workspace."""
    wm = _make_wm()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v1.0.0",
            network_model="hub-and-spoke",
            workspace_manager=wm,
        )

    assert result["success"] is True
    assert result["files_copied"] == 3

    # Verify files were written with correct paths
    written_paths = set(wm._written_files.keys())
    assert "accounts-config.yaml" in written_paths
    assert "network-config.yaml" in written_paths
    assert "service-control-policies/policy1.json" in written_paths


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_exception_handling(mock_ctx, mock_uc_structure):
    """Test error handling when workspace creation fails."""
    wm = MagicMock()
    wm.create_workspace.side_effect = OSError("Disk full")

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v1.0.0",
            network_model="hub-and-spoke",
            workspace_manager=wm,
        )

    assert result["success"] is False
    assert "OSError" in result["error"]
    assert "error_code" in result
    assert "troubleshooting" in result
    assert len(result["troubleshooting"]) > 0


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_uc_release_not_found_no_releases(mock_ctx, tmp_path):
    """Test error when uc_release not found and no releases exist at all."""
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    wm = _make_wm()

    with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v9.9.9",
            network_model="hub-and-spoke",
            workspace_manager=wm,
        )

    assert result["success"] is False
    assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
    assert result["context"]["available_releases"] == []


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_network_model_not_found_no_models(
    mock_ctx, mock_uc_structure
):
    """Test error when network_model not found and release has no model dirs."""
    empty_release = mock_uc_structure / "v2.0.0"
    empty_release.mkdir()

    wm = _make_wm()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        mock_release_path.return_value = empty_release
        mock_model_path.return_value = empty_release / "nonexistent"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx,
            uc_release="v2.0.0",
            network_model="nonexistent",
            workspace_manager=wm,
        )

    assert result["success"] is False
    assert result["error_code"] == "NETWORK_MODEL_NOT_FOUND"
    assert result["context"]["available_models"] == []
