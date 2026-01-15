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

"""Unit tests for get_uc_network_customization_guide tool."""

import json
import pytest

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    get_uc_network_customization_guide,
    _scan_configuration_files,
    _is_policy_directory,
)


@pytest.mark.unit
class TestGetUcNetworkCustomizationGuide:
    """Unit tests for get_uc_network_customization_guide."""

    def test_with_valid_session(self, tmp_path):
        """Test with valid session."""
        # Create session directory
        session_id = "uc-session-20250127-143022"
        session_path = tmp_path / session_id
        session_path.mkdir(parents=True)

        # Create metadata file
        metadata = {
            "session_id": session_id,
            "network_model": "hub-and-spoke",
            "uc_release": "v1.0.0",
            "created_at": "2025-01-27T14:30:22",
        }
        metadata_file = session_path / ".session_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Create some config files
        (session_path / "accounts-config.yaml").write_text("test: data")
        (session_path / "global-config.yaml").write_text("test: data")
        (session_path / "network-config.yaml").write_text("test: data")

        # Create policy directories
        (session_path / "iam-policies").mkdir()
        (session_path / "service-control-policies").mkdir()

        # Create supporting directories
        (session_path / "ssm-documents").mkdir()

        # Patch SessionManager to use tmp_path
        from awslabs.lza_mcp_server.tools.uc_merge import (
            get_uc_network_customization_guide as guide_module,
        )

        original_session_manager = guide_module.SessionManager

        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path

            def get_session_path(self, session_id):
                return tmp_path / session_id

            def session_exists(self, session_id):
                return (tmp_path / session_id).exists()

            def validate_session(self, session_id):
                if not self.session_exists(session_id):
                    return False, f"Session '{session_id}' does not exist"
                metadata_file = (
                    self.get_session_path(session_id) / ".session_metadata.json"
                )
                if not metadata_file.exists():
                    return (
                        False,
                        f"Session '{session_id}' is invalid (missing metadata)",
                    )
                return True, ""

            def load_session_metadata(self, session_id):
                metadata_file = (
                    self.get_session_path(session_id) / ".session_metadata.json"
                )
                if not metadata_file.exists():
                    return None
                with open(metadata_file, "r") as f:
                    return json.load(f)

        guide_module.SessionManager = MockSessionManager

        try:
            result = get_uc_network_customization_guide(session_id)

            assert result["success"] is True
            assert result["session_id"] == session_id
            assert result["network_model"] == "hub-and-spoke"
            assert "configuration_files" in result
            assert "next_steps" in result

            # Check configuration files
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
        finally:
            guide_module.SessionManager = original_session_manager

    def test_error_when_session_id_missing(self, tmp_path):
        """Test error when session_id is missing."""
        # Patch SessionManager to use tmp_path
        from awslabs.lza_mcp_server.tools.uc_merge import (
            get_uc_network_customization_guide as guide_module,
        )

        original_session_manager = guide_module.SessionManager

        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path

            def validate_session(self, session_id):
                if not session_id:
                    return False, "Session ID cannot be empty"
                return (
                    False,
                    f"Session '{session_id}' does not exist. Start a session first with start_uc_merge_session()",
                )

        guide_module.SessionManager = MockSessionManager

        try:
            result = get_uc_network_customization_guide("")

            assert result["success"] is False
            assert result["error_code"] == "INVALID_SESSION"
            assert "Session ID cannot be empty" in result["error"]
        finally:
            guide_module.SessionManager = original_session_manager

    def test_error_when_session_invalid(self, tmp_path):
        """Test error when session is invalid."""
        session_id = "uc-session-invalid"

        # Patch SessionManager to use tmp_path
        from awslabs.lza_mcp_server.tools.uc_merge import (
            get_uc_network_customization_guide as guide_module,
        )

        original_session_manager = guide_module.SessionManager

        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path

            def validate_session(self, session_id):
                return (
                    False,
                    f"Session '{session_id}' does not exist. Start a session first with start_uc_merge_session()",
                )

        guide_module.SessionManager = MockSessionManager

        try:
            result = get_uc_network_customization_guide(session_id)

            assert result["success"] is False
            assert result["error_code"] == "INVALID_SESSION"
            assert "does not exist" in result["error"]
        finally:
            guide_module.SessionManager = original_session_manager

    def test_file_discovery(self, tmp_path):
        """Test file discovery in session directory."""
        session_path = tmp_path / "test-session"
        session_path.mkdir()

        # Create various files and directories
        (session_path / "accounts-config.yaml").write_text("test")
        (session_path / "global-config.yaml").write_text("test")
        (session_path / "network-config.yaml").write_text("test")
        (session_path / "iam-config.yaml").write_text("test")
        (session_path / "organization-config.yaml").write_text("test")
        (session_path / "security-config.yaml").write_text("test")
        (session_path / "replacements-config.yaml").write_text("test")

        # Create policy directories (will be detected by name patterns)
        (session_path / "backup-policies").mkdir()
        (session_path / "iam-policies").mkdir()
        (session_path / "service-control-policies").mkdir()
        (session_path / "tagging-policies").mkdir()

        # Create supporting directories (non-policy directories)
        (session_path / "ssm-documents").mkdir()
        (session_path / "dynamic-partitioning").mkdir()

        # Create hidden directory (should be ignored)
        (session_path / ".hidden").mkdir()

        result = _scan_configuration_files(session_path)

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

        # Check policy directories (dynamically detected by name patterns)
        assert len(result["policy_directories"]) == 4
        assert "backup-policies" in result["policy_directories"]
        assert "iam-policies" in result["policy_directories"]
        assert "service-control-policies" in result["policy_directories"]
        assert "tagging-policies" in result["policy_directories"]

        # Check supporting directories
        assert len(result["supporting_directories"]) == 2
        assert "ssm-documents" in result["supporting_directories"]
        assert "dynamic-partitioning" in result["supporting_directories"]

        # Verify hidden directory is not included
        assert ".hidden" not in result["policy_directories"]
        assert ".hidden" not in result["supporting_directories"]

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

    def test_shared_vpc_model_settings(self, tmp_path):
        """Test model-specific settings for shared-vpc."""
        # Create session directory
        session_id = "uc-session-20250127-143022"
        session_path = tmp_path / session_id
        session_path.mkdir(parents=True)

        # Create metadata file with shared-vpc model
        metadata = {
            "session_id": session_id,
            "network_model": "shared-vpc",
            "uc_release": "v1.0.0",
            "created_at": "2025-01-27T14:30:22",
        }
        metadata_file = session_path / ".session_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Patch SessionManager
        from awslabs.lza_mcp_server.tools.uc_merge import (
            get_uc_network_customization_guide as guide_module,
        )

        original_session_manager = guide_module.SessionManager

        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path

            def get_session_path(self, session_id):
                return tmp_path / session_id

            def session_exists(self, session_id):
                return (tmp_path / session_id).exists()

            def validate_session(self, session_id):
                if not self.session_exists(session_id):
                    return False, f"Session '{session_id}' does not exist"
                return True, ""

            def load_session_metadata(self, session_id):
                metadata_file = (
                    self.get_session_path(session_id) / ".session_metadata.json"
                )
                if not metadata_file.exists():
                    return None
                with open(metadata_file, "r") as f:
                    return json.load(f)

        guide_module.SessionManager = MockSessionManager

        try:
            result = get_uc_network_customization_guide(session_id)

            assert result["success"] is True
            assert result["network_model"] == "shared-vpc"
            assert "configuration_files" in result
            assert "next_steps" in result
        finally:
            guide_module.SessionManager = original_session_manager
