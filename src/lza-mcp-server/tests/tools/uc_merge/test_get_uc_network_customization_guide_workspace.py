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

"""Unit tests for reworked getUcNetworkCustomizationGuide using WorkspaceManager.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import json
import pytest
from unittest.mock import MagicMock

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    get_uc_network_customization_guide,
    _scan_configuration_files,
    _is_policy_directory,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceNotFoundError,
)


@pytest.mark.unit
@pytest.mark.uc_merge
class TestGetUcNetworkCustomizationGuideWorkspace:
    """Unit tests for workspace-based getUcNetworkCustomizationGuide."""

    def _make_mock_wm(self, metadata=None, file_list=None):
        """Create a mock WorkspaceManager with configurable behavior."""
        wm = MagicMock()
        if metadata is not None:
            wm.read_file.return_value = json.dumps(metadata).encode("utf-8")
        if file_list is not None:
            wm.list_files.return_value = file_list
        return wm

    def test_success_with_valid_workspace(self):
        """Test successful guide retrieval with valid workspace.

        Requirements: 8.1, 8.2
        """
        # Arrange
        metadata = {
            "network_model": "hub-and-spoke",
            "uc_release": "v1.0.0",
            "created_at": "2025-01-27T14:30:22",
        }
        file_list = [
            ".session_metadata.json",
            "accounts-config.yaml",
            "global-config.yaml",
            "network-config.yaml",
            "replacements-config.yaml",
            "iam-policies/boundary-policy.json",
            "service-control-policies/scp.json",
            "ssm-documents/doc.yaml",
        ]
        wm = self._make_mock_wm(metadata=metadata, file_list=file_list)

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is True
        assert result["workspace_id"] == "abc123def456"
        assert result["network_model"] == "hub-and-spoke"

        config_files = result["configuration_files"]
        assert "accounts-config.yaml" in config_files["config_files"]
        assert "global-config.yaml" in config_files["config_files"]
        assert "network-config.yaml" in config_files["config_files"]
        assert "replacements-config.yaml" in config_files["config_files"]
        assert "iam-policies" in config_files["policy_directories"]
        assert "service-control-policies" in config_files["policy_directories"]
        assert "ssm-documents" in config_files["supporting_directories"]

    def test_next_steps_reference_workspace_tools(self):
        """Test that next_steps references readResource and writeWorkspaceFile.

        Requirements: 8.5
        """
        # Arrange
        metadata = {"network_model": "hub-and-spoke", "uc_release": "v1.0.0"}
        wm = self._make_mock_wm(metadata=metadata, file_list=[".session_metadata.json"])

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is True
        assert "readResource" in result["next_steps"]
        assert "writeWorkspaceFile" in result["next_steps"]
        # Should NOT reference old tools
        assert "readUcFile" not in result["next_steps"]
        assert "updateUcFile" not in result["next_steps"]
        assert "readLzaConfigFile" not in result["next_steps"]

    def test_workspace_not_found(self):
        """Test error when workspace does not exist.

        Requirements: 8.3
        """
        # Arrange
        wm = MagicMock()
        wm.read_file.side_effect = WorkspaceNotFoundError(
            "Workspace 'abc123def456' not found"
        )

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"
        assert "not found" in result["error"]

    def test_missing_metadata_file(self):
        """Test error when .session_metadata.json is missing from workspace.

        Requirements: 8.4
        """
        # Arrange
        wm = MagicMock()
        wm.read_file.side_effect = WorkspaceNotFoundError(
            "File '.session_metadata.json' not found in workspace 'abc123def456'"
        )

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION_METADATA"

    def test_missing_network_model_in_metadata(self):
        """Test error when metadata exists but lacks network_model.

        Requirements: 8.4
        """
        # Arrange
        metadata = {"uc_release": "v1.0.0", "created_at": "2025-01-27T14:30:22"}
        wm = self._make_mock_wm(metadata=metadata, file_list=[])

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION_METADATA"
        assert "network_model" in result["error"]

    def test_corrupted_metadata_json(self):
        """Test error when metadata is not valid JSON.

        Requirements: 8.4
        """
        # Arrange
        wm = MagicMock()
        wm.read_file.return_value = b"not valid json {{"

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION_METADATA"

    def test_shared_vpc_model(self):
        """Test with shared-vpc network model.

        Requirements: 8.1
        """
        # Arrange
        metadata = {"network_model": "shared-vpc", "uc_release": "v1.0.0"}
        file_list = [
            ".session_metadata.json",
            "accounts-config.yaml",
            "network-config.yaml",
        ]
        wm = self._make_mock_wm(metadata=metadata, file_list=file_list)

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is True
        assert result["network_model"] == "shared-vpc"

    def test_empty_workspace_no_files(self):
        """Test with workspace that has only metadata and no other files.

        Requirements: 8.2
        """
        # Arrange
        metadata = {"network_model": "hub-and-spoke", "uc_release": "v1.0.0"}
        file_list = [".session_metadata.json"]
        wm = self._make_mock_wm(metadata=metadata, file_list=file_list)

        # Act
        result = get_uc_network_customization_guide("abc123def456", wm)

        # Assert
        assert result["success"] is True
        assert result["configuration_files"]["config_files"] == []
        assert result["configuration_files"]["policy_directories"] == []
        assert result["configuration_files"]["supporting_directories"] == []


@pytest.mark.unit
@pytest.mark.uc_merge
class TestScanConfigurationFilesWorkspace:
    """Unit tests for _scan_configuration_files with workspace file lists."""

    def test_classifies_root_yaml_files(self):
        """Root-level .yaml/.yml files go to config_files."""
        file_list = [
            "accounts-config.yaml",
            "network-config.yml",
            "readme.txt",
        ]
        result = _scan_configuration_files(file_list)
        assert result["config_files"] == ["accounts-config.yaml", "network-config.yml"]

    def test_classifies_policy_directories(self):
        """Directories with policy keywords go to policy_directories."""
        file_list = [
            "iam-policies/boundary.json",
            "firewall-rules/rule1.json",
            "rcp-configs/config.yaml",
        ]
        result = _scan_configuration_files(file_list)
        assert "iam-policies" in result["policy_directories"]
        assert "firewall-rules" in result["policy_directories"]
        assert "rcp-configs" in result["policy_directories"]

    def test_classifies_supporting_directories(self):
        """Non-policy directories go to supporting_directories."""
        file_list = [
            "ssm-documents/doc.yaml",
            "dynamic-partitioning/config.json",
        ]
        result = _scan_configuration_files(file_list)
        assert "ssm-documents" in result["supporting_directories"]
        assert "dynamic-partitioning" in result["supporting_directories"]

    def test_excludes_hidden_files(self):
        """Hidden files (starting with .) are excluded."""
        file_list = [
            ".session_metadata.json",
            ".hidden-dir/file.yaml",
            "accounts-config.yaml",
        ]
        result = _scan_configuration_files(file_list)
        assert ".session_metadata.json" not in result["config_files"]
        assert result["config_files"] == ["accounts-config.yaml"]
        assert ".hidden-dir" not in result["policy_directories"]
        assert ".hidden-dir" not in result["supporting_directories"]

    def test_empty_file_list(self):
        """Empty file list returns empty categories."""
        result = _scan_configuration_files([])
        assert result["config_files"] == []
        assert result["policy_directories"] == []
        assert result["supporting_directories"] == []

    def test_nested_files_classify_top_dir_only(self):
        """Deeply nested files classify only the top-level directory."""
        file_list = [
            "iam-policies/sub/deep/file.json",
            "ssm-documents/sub/file.yaml",
        ]
        result = _scan_configuration_files(file_list)
        assert "iam-policies" in result["policy_directories"]
        assert "ssm-documents" in result["supporting_directories"]

    def test_sorted_output(self):
        """Output lists are sorted alphabetically."""
        file_list = [
            "z-config.yaml",
            "a-config.yaml",
            "m-config.yaml",
        ]
        result = _scan_configuration_files(file_list)
        assert result["config_files"] == [
            "a-config.yaml",
            "m-config.yaml",
            "z-config.yaml",
        ]

    def test_deduplicates_directories(self):
        """Multiple files in same directory produce single directory entry."""
        file_list = [
            "iam-policies/file1.json",
            "iam-policies/file2.json",
            "iam-policies/sub/file3.json",
        ]
        result = _scan_configuration_files(file_list)
        assert result["policy_directories"].count("iam-policies") == 1


@pytest.mark.unit
@pytest.mark.uc_merge
class TestIsPolicyDirectory:
    """Unit tests for _is_policy_directory."""

    def test_policy_keywords_detected(self):
        """Directories with policy keywords are detected."""
        assert _is_policy_directory("iam-policies") is True
        assert _is_policy_directory("service-control-policies") is True
        assert _is_policy_directory("firewall-rules") is True
        assert _is_policy_directory("rcp-policies") is True
        assert _is_policy_directory("custom-policy-dir") is True

    def test_non_policy_directories(self):
        """Directories without policy keywords are not detected."""
        assert _is_policy_directory("ssm-documents") is False
        assert _is_policy_directory("dynamic-partitioning") is False
        assert _is_policy_directory("templates") is False

    def test_case_insensitive(self):
        """Detection is case-insensitive."""
        assert _is_policy_directory("IAM-POLICIES") is True
        assert _is_policy_directory("MyFirewallRules") is True
