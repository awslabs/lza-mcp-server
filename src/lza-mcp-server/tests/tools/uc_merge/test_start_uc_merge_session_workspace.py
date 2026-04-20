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

"""Unit tests for reworked start_uc_merge_session using WorkspaceManager.

Tests cover: workspace creation, file copying, metadata storage,
invalid parameters, missing UC release/model, workspace errors.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import json
import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session import (
    tool_start_uc_merge_session,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
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
def mock_uc_structure(tmp_path):
    """Create a mock UC directory structure."""
    uc_base = tmp_path / "lza-uc"
    uc_base.mkdir()

    release_dir = uc_base / "v1.0.0"
    release_dir.mkdir()

    hub_spoke_dir = release_dir / "hub-and-spoke"
    hub_spoke_dir.mkdir()

    shared_vpc_dir = release_dir / "shared-vpc"
    shared_vpc_dir.mkdir()

    # Create sample files in hub-and-spoke
    (hub_spoke_dir / "accounts-config.yaml").write_text("test: config")
    (hub_spoke_dir / "network-config.yaml").write_text("network: config")

    # Create subdirectory with files
    policies_dir = hub_spoke_dir / "service-control-policies"
    policies_dir.mkdir()
    (policies_dir / "policy1.json").write_text('{"test": "policy"}')

    # Create sample files in shared-vpc
    (shared_vpc_dir / "accounts-config.yaml").write_text("test: config")

    return uc_base


def _make_wm(workspace_id="abcdef123456"):
    """Create a mock WorkspaceManager that tracks written files."""
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
class TestStartSessionWorkspaceSuccess:
    """Tests for successful session creation with workspace."""

    @pytest.mark.asyncio
    async def test_creates_workspace_and_copies_files(
        self, mock_ctx, mock_uc_structure
    ):
        """Req 7.1, 7.2: Creates workspace and copies all UC files."""
        # Arrange
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
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            # Act
            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        # Assert
        assert result["success"] is True
        assert result["workspace_id"] == "abcdef123456"
        assert result["uc_release"] == "v1.0.0"
        assert result["network_model"] == "hub-and-spoke"
        assert result["files_copied"] == 3  # 2 yaml + 1 json in subdirectory
        assert "next_steps" in result
        assert "getLzaConfiguration" in result["next_steps"]

        # Verify workspace was created
        wm.create_workspace.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_workspace_id_not_session_id(
        self, mock_ctx, mock_uc_structure
    ):
        """Req 7.4: Returns workspace_id instead of session_id."""
        wm = _make_wm(workspace_id="fedcba654321")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
            ) as mock_release_path,
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
            ) as mock_model_path,
        ):
            mock_release_path.return_value = mock_uc_structure / "v1.0.0"
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is True
        assert "workspace_id" in result
        assert result["workspace_id"] == "fedcba654321"
        assert "session_id" not in result

    @pytest.mark.asyncio
    async def test_stores_session_metadata(self, mock_ctx, mock_uc_structure):
        """Req 7.3: Stores session metadata as .session_metadata.json."""
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
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is True

        # Verify metadata was written
        assert ".session_metadata.json" in wm._written_files
        metadata = json.loads(wm._written_files[".session_metadata.json"].decode())
        assert metadata["network_model"] == "hub-and-spoke"
        assert metadata["uc_release"] == "v1.0.0"
        assert "created_at" in metadata

    @pytest.mark.asyncio
    async def test_preserves_directory_structure(self, mock_ctx, mock_uc_structure):
        """Req 7.2: Preserves directory structure when copying files."""
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
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is True

        # Check that subdirectory files have correct relative paths
        written_paths = set(wm._written_files.keys())
        assert "accounts-config.yaml" in written_paths
        assert "network-config.yaml" in written_paths
        assert "service-control-policies/policy1.json" in written_paths
        assert ".session_metadata.json" in written_paths

    @pytest.mark.asyncio
    async def test_no_cleanup_of_previous_sessions(self, mock_ctx, mock_uc_structure):
        """Req 7.1: No cleanup call — workspaces are independent."""
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
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            await tool_start_uc_merge_session(mock_ctx, "v1.0.0", "hub-and-spoke", wm)

        # Verify no cleanup/delete methods were called
        wm.delete_workspace.assert_not_called()


@pytest.mark.unit
@pytest.mark.uc_merge
class TestStartSessionWorkspaceValidation:
    """Tests for parameter validation."""

    @pytest.mark.asyncio
    async def test_missing_uc_release(self, mock_ctx):
        """Req 7.5: Returns error when uc_release is empty."""
        wm = _make_wm()
        result = await tool_start_uc_merge_session(mock_ctx, "", "hub-and-spoke", wm)

        assert result["success"] is False
        assert result["error_code"] == "MISSING_PARAMETER"
        assert "uc_release" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_network_model(self, mock_ctx):
        """Req 7.5: Returns error when network_model is empty."""
        wm = _make_wm()
        result = await tool_start_uc_merge_session(mock_ctx, "v1.0.0", "", wm)

        assert result["success"] is False
        assert result["error_code"] == "MISSING_PARAMETER"
        assert "network_model" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_uc_release_format(self, mock_ctx):
        """Req 7.5: Returns error for invalid uc_release format."""
        wm = _make_wm()
        result = await tool_start_uc_merge_session(
            mock_ctx, "1.0.0", "hub-and-spoke", wm
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_UC_RELEASE"

    @pytest.mark.asyncio
    async def test_invalid_network_model_format(self, mock_ctx):
        """Req 7.5: Returns error for invalid network_model format."""
        wm = _make_wm()
        result = await tool_start_uc_merge_session(
            mock_ctx, "v1.0.0", "Hub_And_Spoke", wm
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_NETWORK_MODEL"


@pytest.mark.unit
@pytest.mark.uc_merge
class TestStartSessionWorkspaceNotFound:
    """Tests for missing UC release/model."""

    @pytest.mark.asyncio
    async def test_uc_release_not_found(self, mock_ctx, tmp_path):
        """Req 7.6: Returns error when UC release doesn't exist."""
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        v1_dir = uc_base / "v1.0.0"
        v1_dir.mkdir()

        wm = _make_wm()

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_start_uc_merge_session(
                mock_ctx, "v2.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
        assert "v1.0.0" in result["context"]["available_releases"]

    @pytest.mark.asyncio
    async def test_network_model_not_found(self, mock_ctx, mock_uc_structure):
        """Req 7.6: Returns error when network model doesn't exist."""
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
                mock_ctx, "v1.0.0", "non-existent-model", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "NETWORK_MODEL_NOT_FOUND"
        assert "hub-and-spoke" in result["context"]["available_models"]
        assert "shared-vpc" in result["context"]["available_models"]

    @pytest.mark.asyncio
    async def test_uc_release_not_found_no_releases(self, mock_ctx, tmp_path):
        """Req 7.6: Returns error when no releases exist at all."""
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()

        wm = _make_wm()

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_start_uc_merge_session(
                mock_ctx, "v9.9.9", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
        assert result["context"]["available_releases"] == []


@pytest.mark.unit
@pytest.mark.uc_merge
class TestStartSessionWorkspaceErrors:
    """Tests for workspace error handling."""

    @pytest.mark.asyncio
    async def test_workspace_storage_error(self, mock_ctx, mock_uc_structure):
        """Returns WORKSPACE_STORAGE_ERROR when storage fails."""
        wm = MagicMock()
        wm.create_workspace.side_effect = WorkspaceStorageError("Disk full")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
            ) as mock_release_path,
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
            ) as mock_model_path,
        ):
            mock_release_path.return_value = mock_uc_structure / "v1.0.0"
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_STORAGE_ERROR"

    @pytest.mark.asyncio
    async def test_workspace_validation_error(self, mock_ctx, mock_uc_structure):
        """Returns WORKSPACE_VALIDATION_ERROR for validation failures."""
        wm = MagicMock()
        wm.create_workspace.side_effect = WorkspaceValidationError("Invalid")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
            ) as mock_release_path,
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
            ) as mock_model_path,
        ):
            mock_release_path.return_value = mock_uc_structure / "v1.0.0"
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_unexpected_exception(self, mock_ctx, mock_uc_structure):
        """Returns categorized error for unexpected exceptions."""
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
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert "OSError" in result["error"]
        assert "error_code" in result
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_write_file_error_during_copy(self, mock_ctx, mock_uc_structure):
        """Returns error when write_file fails during file copy."""
        wm = MagicMock()
        wm.create_workspace.return_value = "abcdef123456"
        wm.write_file.side_effect = WorkspaceStorageError("Write failed")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_release_path"
            ) as mock_release_path,
            patch(
                "awslabs.lza_mcp_server.tools.uc_merge.start_uc_merge_session.get_uc_network_model_path"
            ) as mock_model_path,
        ):
            mock_release_path.return_value = mock_uc_structure / "v1.0.0"
            mock_model_path.return_value = (
                mock_uc_structure / "v1.0.0" / "hub-and-spoke"
            )

            result = await tool_start_uc_merge_session(
                mock_ctx, "v1.0.0", "hub-and-spoke", wm
            )

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_STORAGE_ERROR"
