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
from pathlib import Path
from hypothesis import given, strategies as st, settings

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
        from awslabs.lza_mcp_server.tools.uc_merge import get_uc_network_customization_guide as guide_module
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
                metadata_file = self.get_session_path(session_id) / ".session_metadata.json"
                if not metadata_file.exists():
                    return False, f"Session '{session_id}' is invalid (missing metadata)"
                return True, ""
            
            def load_session_metadata(self, session_id):
                metadata_file = self.get_session_path(session_id) / ".session_metadata.json"
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
        from awslabs.lza_mcp_server.tools.uc_merge import get_uc_network_customization_guide as guide_module
        original_session_manager = guide_module.SessionManager
        
        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path
            
            def validate_session(self, session_id):
                if not session_id:
                    return False, "Session ID cannot be empty"
                return False, f"Session '{session_id}' does not exist. Start a session first with start_uc_merge_session()"
        
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
        from awslabs.lza_mcp_server.tools.uc_merge import get_uc_network_customization_guide as guide_module
        original_session_manager = guide_module.SessionManager
        
        class MockSessionManager:
            def __init__(self):
                self.base_session_dir = tmp_path
            
            def validate_session(self, session_id):
                return False, f"Session '{session_id}' does not exist. Start a session first with start_uc_merge_session()"
        
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
        from awslabs.lza_mcp_server.tools.uc_merge import get_uc_network_customization_guide as guide_module
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
                metadata_file = self.get_session_path(session_id) / ".session_metadata.json"
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


@pytest.mark.property
class TestGetUcNetworkCustomizationGuideProperties:
    """Property-based tests for get_uc_network_customization_guide."""
    
    @settings(max_examples=100)
    @given(session_id=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=1,
        max_size=100
    ))
    def test_property_15_customization_guide_completeness(self, session_id):
        """Property 15: Customization guide completeness.
        
        Feature: uc-merge, Property 15: Customization guide completeness
        Validates: Requirements 7.2, 7.3, 7.4, 7.5
        
        For any valid network model, get_uc_network_customization_guide should return
        session_id, network_model, configuration_files, and next_steps fields.
        """
        import tempfile
        import shutil
        tmp_path = Path(tempfile.mkdtemp())
        
        try:
            # Create a valid session
            session_path = tmp_path / session_id
            session_path.mkdir(parents=True, exist_ok=True)
            
            # Create metadata with a valid network model
            metadata = {
                "session_id": session_id,
                "network_model": "hub-and-spoke",
                "uc_release": "v1.0.0",
                "created_at": "2025-01-27T14:30:22",
            }
            metadata_file = session_path / ".session_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f)
            
            # Patch SessionManager
            from awslabs.lza_mcp_server.tools.uc_merge import get_uc_network_customization_guide as guide_module
            original_session_manager = guide_module.SessionManager
            
            class MockSessionManager:
                def __init__(self):
                    self.base_session_dir = tmp_path
                
                def get_session_path(self, sid):
                    return tmp_path / sid
                
                def session_exists(self, sid):
                    return (tmp_path / sid).exists()
                
                def validate_session(self, sid):
                    if not self.session_exists(sid):
                        return False, f"Session '{sid}' does not exist"
                    metadata_file = self.get_session_path(sid) / ".session_metadata.json"
                    if not metadata_file.exists():
                        return False, f"Session '{sid}' is invalid (missing metadata)"
                    return True, ""
                
                def load_session_metadata(self, sid):
                    metadata_file = self.get_session_path(sid) / ".session_metadata.json"
                    if not metadata_file.exists():
                        return None
                    with open(metadata_file, "r") as f:
                        return json.load(f)
            
            guide_module.SessionManager = MockSessionManager
            
            try:
                result = get_uc_network_customization_guide(session_id)
                
                # If successful, verify all required fields are present
                if result.get("success"):
                    assert "session_id" in result
                    assert "network_model" in result
                    assert "configuration_files" in result
                    assert "next_steps" in result
                    
                    # Verify session_id is a string
                    assert isinstance(result["session_id"], str)
                    
                    # Verify network_model is a string
                    assert isinstance(result["network_model"], str)
                    
                    # Verify configuration_files has required structure
                    assert isinstance(result["configuration_files"], dict)
                    assert "config_files" in result["configuration_files"]
                    assert "policy_directories" in result["configuration_files"]
                    assert "supporting_directories" in result["configuration_files"]
                    
                    # Verify next_steps is a non-empty string
                    assert isinstance(result["next_steps"], str)
                    assert len(result["next_steps"]) > 0
            finally:
                guide_module.SessionManager = original_session_manager
        finally:
            # Cleanup temp directory
            shutil.rmtree(tmp_path, ignore_errors=True)
    
    @settings(max_examples=100)
    @given(
        num_config_files=st.integers(min_value=0, max_value=20),
        num_policy_dirs=st.integers(min_value=0, max_value=15),
        num_supporting_dirs=st.integers(min_value=0, max_value=10),
    )
    def test_property_16_configuration_file_list_organization(
        self, num_config_files, num_policy_dirs, num_supporting_dirs
    ):
        """Property 16: Configuration file list organization.
        
        Feature: uc-merge, Property 16: Configuration file list organization
        Validates: Requirements 7.7, 7.8
        
        For any session directory, files should be organized by type:
        config_files, policy_directories, and supporting_directories.
        """
        import tempfile
        import shutil
        tmp_path = Path(tempfile.mkdtemp())
        
        try:
            session_path = tmp_path / "test-session"
            session_path.mkdir(parents=True, exist_ok=True)
            
            # Create config files
            for i in range(num_config_files):
                (session_path / f"config-{i}.yaml").write_text("test")
            
            # Create policy directories (use known names)
            policy_names = [
                "backup-policies", "iam-policies", "service-control-policies",
                "tagging-policies", "vpc-endpoint-policies", "rcp-policies",
                "declarative-policies", "event-bus-policies", "firewall-rules"
            ]
            for i in range(min(num_policy_dirs, len(policy_names))):
                (session_path / policy_names[i]).mkdir()
            
            # Create supporting directories (use known names)
            supporting_names = [
                "ssm-documents", "dynamic-partitioning", "ssm-remediation-roles"
            ]
            for i in range(min(num_supporting_dirs, len(supporting_names))):
                (session_path / supporting_names[i]).mkdir()
            
            result = _scan_configuration_files(session_path)
            
            # Verify structure
            assert "config_files" in result
            assert "policy_directories" in result
            assert "supporting_directories" in result
            
            # Verify types
            assert isinstance(result["config_files"], list)
            assert isinstance(result["policy_directories"], list)
            assert isinstance(result["supporting_directories"], list)
            
            # Verify counts
            assert len(result["config_files"]) == num_config_files
            assert len(result["policy_directories"]) == min(num_policy_dirs, len(policy_names))
            assert len(result["supporting_directories"]) == min(num_supporting_dirs, len(supporting_names))
            
            # Verify all items are strings
            for item in result["config_files"]:
                assert isinstance(item, str)
            for item in result["policy_directories"]:
                assert isinstance(item, str)
            for item in result["supporting_directories"]:
                assert isinstance(item, str)
        finally:
            # Cleanup temp directory
            shutil.rmtree(tmp_path, ignore_errors=True)
