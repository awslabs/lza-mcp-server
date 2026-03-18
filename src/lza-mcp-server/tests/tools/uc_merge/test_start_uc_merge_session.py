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

"""Unit tests for start_uc_merge_session tool."""

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


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_with_valid_parameters(
    mock_ctx, mock_uc_structure, tmp_path
):
    """Test session creation with valid parameters."""
    # Setup
    session_base = tmp_path / "lza-config"
    session_base.mkdir()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.SessionManager"
        ) as mock_session_manager_class,
    ):
        # Configure mocks
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        # Mock SessionManager instance
        mock_session_manager = MagicMock()
        mock_session_manager_class.return_value = mock_session_manager

        mock_session_manager.generate_session_id.return_value = (
            "uc-session-20250127-143022"
        )
        mock_session_manager.create_session_directory.return_value = (
            session_base / "uc-session-20250127-143022"
        )
        mock_session_manager.copy_files_to_session.return_value = 3
        mock_session_manager.cleanup_previous_sessions.return_value = 0

        # Execute
        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v1.0.0", network_model="hub-and-spoke"
        )

        # Verify
        assert result["success"] is True
        assert result["session_id"] == "uc-session-20250127-143022"
        assert result["uc_release"] == "v1.0.0"
        assert result["network_model"] == "hub-and-spoke"
        assert result["files_copied"] == 3
        assert "next_steps" in result
        assert "getLzaConfiguration" in result["next_steps"]

        # Verify session manager was called correctly
        mock_session_manager.generate_session_id.assert_called_once()
        mock_session_manager.create_session_directory.assert_called_once_with(
            "uc-session-20250127-143022"
        )
        mock_session_manager.copy_files_to_session.assert_called_once()
        mock_session_manager.save_session_metadata.assert_called_once_with(
            session_id="uc-session-20250127-143022",
            network_model="hub-and-spoke",
            uc_release="v1.0.0",
        )
        mock_session_manager.cleanup_previous_sessions.assert_called_once_with(
            keep_session_id="uc-session-20250127-143022"
        )


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_missing_uc_release(mock_ctx):
    """Test error when uc_release parameter is missing."""
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx, uc_release="", network_model="hub-and-spoke"
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
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx, uc_release="v1.0.0", network_model=""
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
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="1.0.0",  # Missing 'v' prefix
        network_model="hub-and-spoke",
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
    result = await tool_start_uc_merge_session(
        ctx=mock_ctx,
        uc_release="v1.0.0",
        network_model="Hub_And_Spoke",  # Invalid characters
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
    # Create empty UC base directory
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    # Create v1.0.0 but we'll request v2.0.0
    v1_dir = uc_base / "v1.0.0"
    v1_dir.mkdir()

    # Use environment variable to point to our test directory
    with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v2.0.0", network_model="hub-and-spoke"
        )

        assert result["success"] is False
        assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
        assert "v2.0.0" in result["error"]
        assert "available_releases" in result["context"]
        assert "v1.0.0" in result["context"]["available_releases"]
        assert "get_uc_releases" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_network_model_not_found(mock_ctx, mock_uc_structure):
    """Test error when network_model does not exist in the release."""
    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
    ):
        # Configure mocks - release exists but model doesn't
        release_path = mock_uc_structure / "v1.0.0"
        mock_release_path.return_value = release_path
        mock_model_path.return_value = release_path / "non-existent-model"

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v1.0.0", network_model="non-existent-model"
        )

        assert result["success"] is False
        assert result["error_code"] == "NETWORK_MODEL_NOT_FOUND"
        assert "non-existent-model" in result["error"]
        assert "available_models" in result["context"]
        assert "hub-and-spoke" in result["context"]["available_models"]
        assert "shared-vpc" in result["context"]["available_models"]
        assert "get_uc_network_models" in result["next_steps"]


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_file_copying(mock_ctx, mock_uc_structure, tmp_path):
    """Test that files are copied correctly to the session."""
    session_base = tmp_path / "lza-config"
    session_base.mkdir()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.SessionManager"
        ) as mock_session_manager_class,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        mock_session_manager = MagicMock()
        mock_session_manager_class.return_value = mock_session_manager

        mock_session_manager.generate_session_id.return_value = "uc-session-test"
        mock_session_manager.create_session_directory.return_value = (
            session_base / "uc-session-test"
        )
        mock_session_manager.copy_files_to_session.return_value = 3
        mock_session_manager.cleanup_previous_sessions.return_value = 0

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v1.0.0", network_model="hub-and-spoke"
        )

        assert result["success"] is True
        assert result["files_copied"] == 3

        # Verify copy was called with correct parameters
        call_args = mock_session_manager.copy_files_to_session.call_args
        assert call_args[1]["session_id"] == "uc-session-test"
        assert call_args[1]["preserve_structure"] is True


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_cleanup_previous_sessions(
    mock_ctx, mock_uc_structure, tmp_path
):
    """Test that previous sessions are cleaned up."""
    session_base = tmp_path / "lza-config"
    session_base.mkdir()

    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.SessionManager"
        ) as mock_session_manager_class,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        mock_session_manager = MagicMock()
        mock_session_manager_class.return_value = mock_session_manager

        mock_session_manager.generate_session_id.return_value = "uc-session-new"
        mock_session_manager.create_session_directory.return_value = (
            session_base / "uc-session-new"
        )
        mock_session_manager.copy_files_to_session.return_value = 3
        mock_session_manager.cleanup_previous_sessions.return_value = (
            2  # 2 old sessions cleaned
        )

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v1.0.0", network_model="hub-and-spoke"
        )

        assert result["success"] is True

        # Verify cleanup was called with the new session ID to keep
        mock_session_manager.cleanup_previous_sessions.assert_called_once_with(
            keep_session_id="uc-session-new"
        )


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_exception_handling(mock_ctx, mock_uc_structure):
    """Test error handling when session creation fails."""
    with (
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
        ) as mock_release_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
        ) as mock_model_path,
        patch(
            "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.SessionManager"
        ) as mock_session_manager_class,
    ):
        mock_release_path.return_value = mock_uc_structure / "v1.0.0"
        mock_model_path.return_value = mock_uc_structure / "v1.0.0" / "hub-and-spoke"

        # Make SessionManager raise an exception
        mock_session_manager_class.side_effect = OSError("Disk full")

        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v1.0.0", network_model="hub-and-spoke"
        )

        assert result["success"] is False
        assert "Disk full" in result["error"]
        assert "error_code" in result
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0


@pytest.mark.unit
@pytest.mark.uc_merge
@pytest.mark.asyncio
async def test_start_session_uc_release_not_found_no_releases(mock_ctx, tmp_path):
    """Test error when uc_release not found and no releases exist at all.

    Covers branch 122->129: available_releases is empty.
    """
    # Create empty UC base directory (no releases)
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
        result = await tool_start_uc_merge_session(
            ctx=mock_ctx, uc_release="v9.9.9", network_model="hub-and-spoke"
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
    """Test error when network_model not found and release has no model dirs.

    Covers branch 152->159: available_models is empty.
    """
    # Create a release with no model subdirectories
    empty_release = mock_uc_structure / "v2.0.0"
    empty_release.mkdir()

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
            ctx=mock_ctx, uc_release="v2.0.0", network_model="nonexistent"
        )

        assert result["success"] is False
        assert result["error_code"] == "NETWORK_MODEL_NOT_FOUND"
        assert result["context"]["available_models"] == []
