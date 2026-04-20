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

"""Unit tests for get_uc_network_customization_guide tool.

Updated to use WorkspaceManager-based API (workspace_id instead of session_id).
"""

import json
import pytest
from unittest.mock import MagicMock

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    get_uc_network_customization_guide,
    _scan_configuration_files,
    _is_policy_directory,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceNotFoundError


@pytest.mark.unit
class TestGetUcNetworkCustomizationGuide:
    """Unit tests for get_uc_network_customization_guide."""

    def _make_mock_wm(self, metadata=None, file_list=None):
        """Create a mock WorkspaceManager."""
        wm = MagicMock()
        if metadata is not None:
            wm.read_file.return_value = json.dumps(metadata).encode("utf-8")
        if file_list is not None:
            wm.list_files.return_value = file_list
        return wm

    def test_with_valid_session(self):
        """Test with valid workspace containing session metadata and files."""
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
            "iam-policies/boundary.json",
            "service-control-policies/scp.json",
            "ssm-documents/doc.yaml",
        ]
        wm = self._make_mock_wm(metadata=metadata, file_list=file_list)

        result = get_uc_network_customization_guide("abc123def456", wm)

        assert result["success"] is True
        assert result["workspace_id"] == "abc123def456"
        assert result["network_model"] == "hub-and-spoke"
        assert "configuration_files" in result
        assert "next_steps" in result

        config_files = result["configuration_files"]
        assert "config_files" in config_files
        assert "policy_directories" in config_files
        assert "supporting_directories" in config_files

        assert "accounts-config.yaml" in config_files["config_files"]
        assert "global-config.yaml" in config_files["config_files"]
        assert "network-config.yaml" in config_files["config_files"]

        assert "iam-policies" in config_files["policy_directories"]
        assert "service-control-policies" in config_files["policy_directories"]

        assert "ssm-documents" in config_files["supporting_directories"]

    def test_error_when_session_id_missing(self):
        """Test error when workspace does not exist (empty ID)."""
        wm = MagicMock()
        wm.read_file.side_effect = WorkspaceNotFoundError("Workspace '' not found")

        result = get_uc_network_customization_guide("", wm)

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    def test_error_when_session_invalid(self):
        """Test error when workspace does not exist."""
        wm = MagicMock()
        wm.read_file.side_effect = WorkspaceNotFoundError(
            "Workspace 'abc123def456' not found"
        )

        result = get_uc_network_customization_guide("abc123def456", wm)

        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"
        assert "not found" in result["error"]

    def test_file_discovery(self):
        """Test file discovery and classification from workspace file list."""
        file_list = [
            "accounts-config.yaml",
            "global-config.yaml",
            "network-config.yaml",
            "iam-config.yaml",
            "organization-config.yaml",
            "security-config.yaml",
            "replacements-config.yaml",
            "backup-policies/policy1.json",
            "iam-policies/boundary.json",
            "service-control-policies/scp.json",
            "tagging-policies/tag.json",
            "ssm-documents/doc.yaml",
            "dynamic-partitioning/config.json",
        ]

        result = _scan_configuration_files(file_list)

        assert "config_files" in result
        assert "policy_directories" in result
        assert "supporting_directories" in result

        # Check config files
        assert len(result["config_files"]) == 7
        assert "accounts-config.yaml" in result["config_files"]
        assert "global-config.yaml" in result["config_files"]
        assert "network-config.yaml" in result["config_files"]
        assert "iam-config.yaml" in result["config_files"]
        assert "organization-config.yaml" in result["config_files"]
        assert "security-config.yaml" in result["config_files"]
        assert "replacements-config.yaml" in result["config_files"]

        # Check policy directories
        assert len(result["policy_directories"]) == 4
        assert "backup-policies" in result["policy_directories"]
        assert "iam-policies" in result["policy_directories"]
        assert "service-control-policies" in result["policy_directories"]
        assert "tagging-policies" in result["policy_directories"]

        # Check supporting directories
        assert len(result["supporting_directories"]) == 2
        assert "ssm-documents" in result["supporting_directories"]
        assert "dynamic-partitioning" in result["supporting_directories"]

    def test_is_policy_directory(self):
        """Test policy directory detection logic."""
        # Should be detected as policy directories
        assert _is_policy_directory("iam-policies") is True
        assert _is_policy_directory("service-control-policies") is True
        assert _is_policy_directory("backup-policies") is True
        assert _is_policy_directory("tagging-policies") is True
        assert _is_policy_directory("vpc-endpoint-policies") is True
        assert _is_policy_directory("firewall-rules") is True
        assert _is_policy_directory("rcp-policies") is True
        assert _is_policy_directory("custom-policy-dir") is True
        assert _is_policy_directory("MyFirewallRules") is True

        # Should NOT be detected as policy directories
        assert _is_policy_directory("ssm-documents") is False
        assert _is_policy_directory("dynamic-partitioning") is False
        assert _is_policy_directory("ssm-remediation-roles") is False
        assert _is_policy_directory("custom-configs") is False
        assert _is_policy_directory("templates") is False

    def test_shared_vpc_model_settings(self):
        """Test model-specific settings for shared-vpc."""
        metadata = {
            "network_model": "shared-vpc",
            "uc_release": "v1.0.0",
            "created_at": "2025-01-27T14:30:22",
        }
        file_list = [".session_metadata.json"]
        wm = self._make_mock_wm(metadata=metadata, file_list=file_list)

        result = get_uc_network_customization_guide("abc123def456", wm)

        assert result["success"] is True
        assert result["network_model"] == "shared-vpc"
        assert "configuration_files" in result
        assert "next_steps" in result

    def test_error_when_metadata_missing_network_model(self):
        """Test error when session metadata exists but lacks network_model key."""
        metadata = {"uc_release": "v1.0.0"}
        wm = self._make_mock_wm(metadata=metadata, file_list=[])

        result = get_uc_network_customization_guide("abc123def456", wm)

        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION_METADATA"

    def test_scan_configuration_files_empty_list(self):
        """_scan_configuration_files returns empty lists for empty input."""
        result = _scan_configuration_files([])
        assert result["config_files"] == []
        assert result["policy_directories"] == []
        assert result["supporting_directories"] == []
