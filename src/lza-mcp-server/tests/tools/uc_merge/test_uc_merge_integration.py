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

"""Integration tests for UC merge workflow.

These tests verify the complete end-to-end UC merge workflow including:
- Release discovery
- Network model selection
- Session creation (workspace-based)
- Customization guide
- Configuration copying (workspace-to-workspace)
- Error recovery paths

Requirements: All UC merge requirements (1.1-11.5)
"""

import pytest
import os
import tempfile
import shutil
import yaml
from pathlib import Path
from unittest.mock import patch

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
from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager


def _make_integration_wm(base_dir):
    """Create a real WorkspaceManager backed by a local adapter for integration tests."""
    adapter = LocalAdapter(base_dir=base_dir)
    return WorkspaceManager(storage=adapter)


@pytest.mark.integration
@pytest.mark.uc_merge
class TestUCMergeWorkflowIntegration:
    """Integration tests for complete UC merge workflow."""

    @pytest.fixture
    def mock_uc_repo(self):
        """Create a mock UC repository structure."""
        temp_dir = tempfile.mkdtemp()
        uc_repo = Path(temp_dir) / "lza-uc"

        # Create v1.0.0 release
        v1_dir = uc_repo / "v1.0.0"
        v1_dir.mkdir(parents=True)

        # Create network models
        for model in ["hub-and-spoke", "shared-vpc", "hub-and-spoke-for-govcloud-us"]:
            model_dir = v1_dir / model
            model_dir.mkdir()

            # Create sample config files
            (model_dir / "accounts-config.yaml").write_text(
                yaml.dump(
                    {
                        "mandatoryAccounts": [
                            {"name": "Management", "email": "management@example.com"},
                            {"name": "LogArchive", "email": "logarchive@example.com"},
                            {"name": "Audit", "email": "audit@example.com"},
                        ],
                        "workloadAccounts": [
                            {"name": "Network", "email": "network@example.com"},
                            {"name": "SharedServices", "email": "shared@example.com"},
                        ],
                    }
                )
            )

            (model_dir / "replacements-config.yaml").write_text(
                yaml.dump(
                    {
                        "globalReplacements": {
                            "HomeRegionIngressCidr": "10.0.0.0/24",
                            "HomeRegionEgressCidr": "10.0.1.0/24",
                        }
                    }
                )
            )

            (model_dir / "network-config.yaml").write_text(
                yaml.dump({"vpcs": [], "transitGateways": []})
            )

        yield str(uc_repo)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_lza_config(self):
        """Create a mock LZA configuration directory."""
        temp_dir = tempfile.mkdtemp()
        lza_config = Path(temp_dir) / "lza-config"
        lza_config.mkdir()

        # Create fresh LZA config files
        (lza_config / "accounts-config.yaml").write_text(
            yaml.dump(
                {
                    "mandatoryAccounts": [
                        {"name": "Management", "email": "mgmt@test.com"},
                        {"name": "LogArchive", "email": "log@test.com"},
                        {"name": "Audit", "email": "audit@test.com"},
                    ],
                    "workloadAccounts": [],
                }
            )
        )

        (lza_config / "global-config.yaml").write_text(
            yaml.dump({"homeRegion": "us-east-1"})
        )

        (lza_config / "network-config.yaml").write_text(
            yaml.dump(
                {
                    "vpcs": [],
                    "transitGateways": [],
                    "endpointPolicies": [],
                }
            )
        )

        (lza_config / "iam-config.yaml").write_text(
            yaml.dump(
                {
                    "providers": [],
                    "policySets": [],
                    "roleSets": [],
                    "groupSets": [],
                    "userSets": [],
                }
            )
        )

        yield str(lza_config)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_complete_uc_merge_workflow_hub_and_spoke(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test complete UC merge workflow with hub-and-spoke model.

        Requirements: All (1.1-11.5)
        """
        # Step 1: Discover available releases
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            releases_result = await tool_get_uc_releases(mock_mcp_context)

        assert releases_result["success"] is True
        assert len(releases_result["releases"]) > 0
        release_names = [r["name"] for r in releases_result["releases"]]
        assert "v1.0.0" in release_names
        assert "next_steps" in releases_result

        # Step 2: Get network models for selected release
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            models_result = await tool_get_uc_network_models(
                mock_mcp_context, uc_release="v1.0.0"
            )

        assert models_result["success"] is True
        assert "hub-and-spoke" in models_result["available_models"]
        assert "next_steps" in models_result

        # Step 3: Start merge session (creates workspace)
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            session_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="hub-and-spoke",
                workspace_manager=wm,
            )

        assert session_result["success"] is True
        uc_workspace_id = session_result["workspace_id"]

        # Step 4: Get customization guide (workspace-based)
        guide_result = get_uc_network_customization_guide(
            workspace_id=uc_workspace_id, workspace_manager=wm
        )
        assert guide_result["success"] is True
        assert guide_result["network_model"] == "hub-and-spoke"

        # Step 5: Copy UC to LZA config (workspace-to-workspace)
        lza_ws = wm.create_workspace()
        for cfg_name in [
            "accounts-config.yaml",
            "global-config.yaml",
            "network-config.yaml",
            "iam-config.yaml",
        ]:
            cfg_path = Path(mock_lza_config) / cfg_name
            if cfg_path.exists():
                wm.write_file(lza_ws, cfg_name, cfg_path.read_bytes())

        copy_result = await copy_uc_to_lza_config(
            mock_mcp_context, uc_workspace_id, lza_ws, wm
        )

        assert copy_result["success"] is True
        assert copy_result["files_copied"] > 0
        assert "next_steps" in copy_result
        assert "putLzaConfiguration" in copy_result["next_steps"]

        # Verify files were copied to LZA workspace
        lza_files = wm.list_files(lza_ws)
        assert "accounts-config.yaml" in lza_files

    @pytest.mark.asyncio
    async def test_complete_uc_merge_workflow_shared_vpc(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test complete UC merge workflow with shared-vpc model."""
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            models_result = await tool_get_uc_network_models(
                mock_mcp_context, uc_release="v1.0.0"
            )

        assert models_result["success"] is True
        assert "shared-vpc" in models_result["available_models"]

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            session_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="shared-vpc",
                workspace_manager=wm,
            )

        assert session_result["success"] is True
        assert session_result["network_model"] == "shared-vpc"

        uc_workspace_id = session_result["workspace_id"]

        guide_result = get_uc_network_customization_guide(
            workspace_id=uc_workspace_id, workspace_manager=wm
        )
        assert guide_result["success"] is True
        assert guide_result["network_model"] == "shared-vpc"

        lza_ws = wm.create_workspace()
        copy_result = await copy_uc_to_lza_config(
            mock_mcp_context, uc_workspace_id, lza_ws, wm
        )
        assert copy_result["success"] is True
        assert copy_result["files_copied"] > 0

    @pytest.mark.asyncio
    async def test_uc_merge_with_different_releases(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test UC merge workflow with multiple release versions."""
        v2_dir = Path(mock_uc_repo) / "v2.0.0"
        v2_dir.mkdir()
        model_dir = v2_dir / "hub-and-spoke"
        model_dir.mkdir()
        (model_dir / "accounts-config.yaml").write_text(
            yaml.dump({"mandatoryAccounts": []})
        )

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            releases_result = await tool_get_uc_releases(mock_mcp_context)

        assert releases_result["success"] is True
        assert len(releases_result["releases"]) == 2
        release_names = [r["name"] for r in releases_result["releases"]]
        assert "v1.0.0" in release_names
        assert "v2.0.0" in release_names
        assert releases_result["releases"][0]["name"] == "v2.0.0"

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            session_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v2.0.0",
                network_model="hub-and-spoke",
                workspace_manager=wm,
            )

        assert session_result["success"] is True
        assert session_result["uc_release"] == "v2.0.0"

    @pytest.mark.asyncio
    async def test_error_recovery_invalid_network_model(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test error recovery when invalid network model is selected."""
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="invalid-model",
                workspace_manager=wm,
            )

        assert result["success"] is False
        assert "error" in result
        assert "context" in result
        assert "available_models" in result["context"]
        assert "hub-and-spoke" in result["context"]["available_models"]

    @pytest.mark.asyncio
    async def test_error_recovery_missing_parameters(
        self, mock_mcp_context, mock_uc_repo
    ):
        """Test error recovery when required parameters are missing."""
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            result = await tool_get_uc_network_models(mock_mcp_context, uc_release=None)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_cleanup_on_new_session(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test that workspaces are independent (no cleanup on new session)."""
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            session1_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="hub-and-spoke",
                workspace_manager=wm,
            )

        assert session1_result["success"] is True
        workspace1_id = session1_result["workspace_id"]

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            session2_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="shared-vpc",
                workspace_manager=wm,
            )

        assert session2_result["success"] is True
        workspace2_id = session2_result["workspace_id"]

        assert workspace1_id != workspace2_id
        files1 = wm.list_files(workspace1_id)
        files2 = wm.list_files(workspace2_id)
        assert len(files1) > 0
        assert len(files2) > 0

    @pytest.mark.asyncio
    async def test_workflow_guidance_next_steps(
        self, mock_mcp_context, mock_uc_repo, mock_lza_config
    ):
        """Test that all tools provide next_steps guidance."""
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            releases_result = await tool_get_uc_releases(mock_mcp_context)
        assert "next_steps" in releases_result
        assert len(releases_result["next_steps"]) > 0

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            models_result = await tool_get_uc_network_models(
                mock_mcp_context, uc_release="v1.0.0"
            )
        assert "next_steps" in models_result
        assert "present" in models_result["next_steps"].lower()

        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": mock_uc_repo}):
            wm = _make_integration_wm(os.path.join(mock_lza_config, "workspaces"))
            session_result = await tool_start_uc_merge_session(
                mock_mcp_context,
                uc_release="v1.0.0",
                network_model="hub-and-spoke",
                workspace_manager=wm,
            )
        assert "next_steps" in session_result
        assert "getLzaConfiguration" in session_result["next_steps"]

        uc_workspace_id = session_result["workspace_id"]

        guide_result = get_uc_network_customization_guide(
            workspace_id=uc_workspace_id, workspace_manager=wm
        )
        assert "next_steps" in guide_result
        assert "readResource" in guide_result["next_steps"]

        lza_ws = wm.create_workspace()
        copy_result = await copy_uc_to_lza_config(
            mock_mcp_context, uc_workspace_id, lza_ws, wm
        )
        assert "next_steps" in copy_result
        assert "putLzaConfiguration" in copy_result["next_steps"]


@pytest.mark.integration
@pytest.mark.uc_merge
class TestUCMergeEdgeCases:
    """Integration tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_uc_repository(self, mock_mcp_context):
        """Test behavior with empty UC repository."""
        temp_dir = tempfile.mkdtemp()
        empty_repo = Path(temp_dir) / "lza-uc"
        empty_repo.mkdir()

        try:
            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(empty_repo)}):
                result = await tool_get_uc_releases(mock_mcp_context)

            assert result["success"] is True
            assert len(result["releases"]) == 0
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_special_characters_in_file_paths(self, mock_mcp_context):
        """Test handling of special characters in file paths."""
        temp_dir = tempfile.mkdtemp()
        uc_repo = Path(temp_dir) / "lza-uc"
        v1_dir = uc_repo / "v1.0.0"
        model_dir = v1_dir / "hub-and-spoke"
        model_dir.mkdir(parents=True)

        try:
            (model_dir / "config file.yaml").write_text(yaml.dump({"test": "value"}))

            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_repo)}):
                wm = _make_integration_wm(os.path.join(temp_dir, "workspaces"))
                session_result = await tool_start_uc_merge_session(
                    mock_mcp_context,
                    uc_release="v1.0.0",
                    network_model="hub-and-spoke",
                    workspace_manager=wm,
                )

            assert session_result["success"] is True

            # Verify file with space in name is in workspace
            files = wm.list_files(session_result["workspace_id"])
            assert "config file.yaml" in files
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, mock_mcp_context):
        """Test that session operations are isolated from each other."""
        temp_dir = tempfile.mkdtemp()
        uc_repo = Path(temp_dir) / "lza-uc"
        v1_dir = uc_repo / "v1.0.0"

        try:
            for model in ["hub-and-spoke", "shared-vpc"]:
                model_dir = v1_dir / model
                model_dir.mkdir(parents=True)
                (model_dir / "test.yaml").write_text(yaml.dump({"model": model}))

            wm = _make_integration_wm(os.path.join(temp_dir, "workspaces"))
            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_repo)}):
                session1 = await tool_start_uc_merge_session(
                    mock_mcp_context,
                    uc_release="v1.0.0",
                    network_model="hub-and-spoke",
                    workspace_manager=wm,
                )

            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_repo)}):
                session2 = await tool_start_uc_merge_session(
                    mock_mcp_context,
                    uc_release="v1.0.0",
                    network_model="shared-vpc",
                    workspace_manager=wm,
                )

            assert session1["success"] is True
            assert session2["success"] is True
            assert session1["workspace_id"] != session2["workspace_id"]

            files1 = wm.list_files(session1["workspace_id"])
            files2 = wm.list_files(session2["workspace_id"])
            assert len(files1) > 0
            assert len(files2) > 0
        finally:
            shutil.rmtree(temp_dir)


@pytest.mark.integration
@pytest.mark.uc_merge
class TestUCMergePerformance:
    """Integration tests for performance characteristics."""

    @pytest.mark.asyncio
    async def test_session_creation_performance(self, mock_mcp_context):
        """Test that session creation completes in reasonable time."""
        import time

        temp_dir = tempfile.mkdtemp()
        uc_repo = Path(temp_dir) / "lza-uc"
        v1_dir = uc_repo / "v1.0.0"
        model_dir = v1_dir / "hub-and-spoke"
        model_dir.mkdir(parents=True)

        try:
            for i in range(20):
                (model_dir / f"config-{i}.yaml").write_text(yaml.dump({"index": i}))

            start_time = time.time()

            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_repo)}):
                wm = _make_integration_wm(os.path.join(temp_dir, "workspaces"))
                result = await tool_start_uc_merge_session(
                    mock_mcp_context,
                    uc_release="v1.0.0",
                    network_model="hub-and-spoke",
                    workspace_manager=wm,
                )

            elapsed_time = time.time() - start_time

            assert result["success"] is True
            assert elapsed_time < 5.0
            assert result["files_copied"] == 20
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_copy_operation_performance(self, mock_mcp_context):
        """Test that copy operation completes in reasonable time."""
        import time

        temp_dir = tempfile.mkdtemp()
        uc_repo = Path(temp_dir) / "lza-uc"
        v1_dir = uc_repo / "v1.0.0"
        model_dir = v1_dir / "hub-and-spoke"
        model_dir.mkdir(parents=True)

        try:
            for i in range(10):
                (model_dir / f"config-{i}.yaml").write_text(yaml.dump({"index": i}))

            with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_repo)}):
                wm = _make_integration_wm(os.path.join(temp_dir, "workspaces"))
                session_result = await tool_start_uc_merge_session(
                    mock_mcp_context,
                    uc_release="v1.0.0",
                    network_model="hub-and-spoke",
                    workspace_manager=wm,
                )

            start_time = time.time()

            lza_ws = wm.create_workspace()
            result = await copy_uc_to_lza_config(
                mock_mcp_context, session_result["workspace_id"], lza_ws, wm
            )

            elapsed_time = time.time() - start_time

            assert result["success"] is True
            assert elapsed_time < 3.0
        finally:
            shutil.rmtree(temp_dir)
