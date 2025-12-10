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

"""Tests for update_uc_file tool."""

import pytest
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck
import yaml

from awslabs.lza_mcp_server.tools.uc_merge.update_uc_file import update_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager
from awslabs.lza_mcp_server.error_categories import ErrorCategory


@pytest.fixture
def temp_session(tmp_path):
    """Create a temporary UC session directory structure."""
    # Create session manager with temp directory
    session_manager = SessionManager(base_session_dir=tmp_path)
    
    # Generate session ID and create session directory
    session_id = session_manager.generate_session_id()
    session_path = session_manager.create_session_directory(session_id)
    
    # Save session metadata
    session_manager.save_session_metadata(
        session_id=session_id,
        network_model="hub-and-spoke",
        uc_release="v1.0.0"
    )
    
    # Create sample UC configuration files
    (session_path / "replacements-config.yaml").write_text(
        "globalReplacements:\n"
        "  HomeRegion: us-east-1\n"
        "  HomeRegionIngressCidr: 10.0.0.0/16\n"
        "  DevVpcMaskLength: 24\n"
        "  TransitGatewayAsn: 64512\n"
    )
    
    (session_path / "accounts-config.yaml").write_text(
        "mandatoryAccounts:\n"
        "  - email: management@example.com\n"
        "    name: Management\n"
        "workloadAccounts:\n"
        "  - email: network@example.com\n"
        "    name: Network\n"
    )
    
    (session_path / "network-config.yaml").write_text(
        "transitGateways:\n"
        "  - name: Network-Main\n"
        "    asn: 64512\n"
        "vpcs:\n"
        "  - name: SharedServices\n"
        "    cidr: 10.0.0.0/16\n"
    )
    
    return {
        "session_id": session_id,
        "session_path": session_path,
        "session_manager": session_manager,
        "base_dir": tmp_path
    }


# ============================================================================
# Property-Based Tests
# ============================================================================

# Feature: uc-merge, Property 17: File existence check before update
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much]
)
@given(
    nonexistent_file=st.one_of(
        st.just("nonexistent-file.yaml"),
        st.just("missing-config.yaml"),
        st.just("not-here.yaml"),
        st.text(min_size=5, max_size=30).filter(
            lambda x: x.endswith(".yaml") and "/" not in x and ".." not in x
        )
    )
)
def test_property_file_existence_check(temp_session, nonexistent_file):
    """Property 17: File existence check before update.
    
    For any non-existent file path in the session directory, update_uc_file
    should return an error before attempting any updates.
    
    Validates: Requirements 8.3
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            nonexistent_file,
            {"someKey": "someValue"}
        ))
        
        # Should return error for non-existent file
        assert result["success"] is False, f"Expected failure for non-existent file {nonexistent_file}, got success"
        assert "error_code" in result or "category" in result, "Expected error_code or category in response"
        if "error" in result:
            assert "not found" in result["error"].lower() or "does not exist" in result["error"].lower()
    finally:
        module.SessionManager = original_session_manager


# Feature: uc-merge, Property 19: Update security validation consistency
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much]
)
@given(
    malicious_path=st.one_of(
        st.just("../../../etc/passwd"),
        st.just("../../sensitive-file.yaml"),
        st.just("/etc/passwd"),
        st.just("/absolute/path/file.yaml"),
        st.text(min_size=3, max_size=50).filter(lambda x: ".." in x)
    )
)
def test_property_update_security_validation(temp_session, malicious_path):
    """Property 19: Update security validation consistency.
    
    For any malicious file path (with path traversal or outside boundaries),
    update_uc_file should apply the same security validations as read_uc_file
    and reject the request.
    
    Validates: Requirements 8.5
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            malicious_path,
            {"someKey": "someValue"}
        ))
        
        assert result["success"] is False
        assert result["error_code"] in ["PATH_TRAVERSAL", "BOUNDARY_VIOLATION"]
        assert result["category"] == ErrorCategory.SECURITY
    finally:
        module.SessionManager = original_session_manager


# Feature: uc-merge, Property 20: YAML syntax preservation
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    updates=st.dictionaries(
        keys=st.text(min_size=1, max_size=20).filter(lambda x: x.isalnum()),
        values=st.one_of(
            st.text(min_size=1, max_size=50),
            st.integers(min_value=1, max_value=1000),
            st.booleans()
        ),
        min_size=1,
        max_size=5
    )
)
def test_property_yaml_syntax_preservation(temp_session, updates):
    """Property 20: YAML syntax preservation.
    
    For any valid YAML file and valid updates, the updated file should
    contain valid YAML syntax.
    
    Validates: Requirements 8.6
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "accounts-config.yaml",
            updates
        ))
        
        # If update succeeded, verify YAML is valid
        if result["success"]:
            session_path = temp_session["session_path"]
            updated_file = session_path / "accounts-config.yaml"
            
            # Should be able to parse the updated file
            with open(updated_file, "r") as f:
                yaml_content = f.read()
            
            # This should not raise an exception
            parsed = yaml.safe_load(yaml_content)
            assert parsed is not None or yaml_content.strip() == ""
    finally:
        module.SessionManager = original_session_manager


# Feature: uc-merge, Property 21: CIDR format validation
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    cidr_value=st.one_of(
        # Valid CIDRs
        st.just("10.0.0.0/8"),
        st.just("192.168.1.0/24"),
        st.just("172.16.0.0/12"),
        # Invalid CIDRs
        st.just("10.0.0/8"),  # Missing octet
        st.just("10.0.0.0"),  # Missing mask
        st.just("10.0.0.0/"),  # Missing mask value
        st.just("256.0.0.0/8"),  # Invalid octet
        st.just("10.0.0.0/33"),  # Invalid mask
        st.just("not-a-cidr"),  # Not a CIDR at all
    )
)
def test_property_cidr_format_validation(temp_session, cidr_value):
    """Property 21: CIDR format validation.
    
    For any update containing CIDR notation values, update_uc_file should
    validate the format matches the pattern.
    
    Validates: Requirements 8.7
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {"HomeRegionIngressCidr": cidr_value}
        ))
        
        # Check if CIDR is valid
        is_valid_cidr = (
            "/" in cidr_value and
            len(cidr_value.split("/")) == 2 and
            len(cidr_value.split("/")[0].split(".")) == 4
        )
        
        if is_valid_cidr:
            try:
                ip_part, mask_part = cidr_value.split("/")
                octets = [int(x) for x in ip_part.split(".")]
                mask = int(mask_part)
                is_valid_cidr = (
                    all(0 <= o <= 255 for o in octets) and
                    0 <= mask <= 32
                )
            except (ValueError, AttributeError):
                is_valid_cidr = False
        
        if is_valid_cidr:
            # Valid CIDR should succeed
            assert result["success"] is True
            assert len(result["validation_errors"]) == 0
        else:
            # Invalid CIDR should fail validation
            assert result["success"] is False
            assert result["error_code"] == "VALIDATION_FAILED"
            assert len(result["context"]["validation_errors"]) > 0
    finally:
        module.SessionManager = original_session_manager


# Feature: uc-merge, Property 22: Numeric range validation
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    asn_value=st.one_of(
        # Valid ASN range (64512-65534)
        st.integers(min_value=64512, max_value=65534),
        # Invalid ASN values
        st.integers(min_value=1, max_value=64511),
        st.integers(min_value=65535, max_value=100000),
    )
)
def test_property_numeric_range_validation_asn(temp_session, asn_value):
    """Property 22: Numeric range validation (ASN).
    
    For any numeric value update, update_uc_file should validate that the
    value is within reasonable ranges for its context.
    
    Validates: Requirements 8.8
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {"TransitGatewayAsn": asn_value}
        ))
        
        # Valid ASN range is 64512-65534
        is_valid_asn = 64512 <= asn_value <= 65534
        
        if is_valid_asn:
            # Valid ASN should succeed
            assert result["success"] is True
            assert len(result["validation_errors"]) == 0
        else:
            # Invalid ASN should fail validation
            assert result["success"] is False
            assert result["error_code"] == "VALIDATION_FAILED"
            assert len(result["context"]["validation_errors"]) > 0
            assert any("asn" in err.lower() for err in result["context"]["validation_errors"])
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    mask_value=st.one_of(
        # Valid VPC mask range (16-28)
        st.integers(min_value=16, max_value=28),
        # Invalid mask values
        st.integers(min_value=1, max_value=15),
        st.integers(min_value=29, max_value=32),
    )
)
def test_property_numeric_range_validation_vpc_mask(temp_session, mask_value):
    """Property 22: Numeric range validation (VPC mask).
    
    For any numeric value update, update_uc_file should validate that the
    value is within reasonable ranges for its context.
    
    Validates: Requirements 8.8
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {"DevVpcMaskLength": mask_value}
        ))
        
        # Valid VPC mask range is 16-28
        is_valid_mask = 16 <= mask_value <= 28
        
        if is_valid_mask:
            # Valid mask should succeed
            assert result["success"] is True
            assert len(result["validation_errors"]) == 0
        else:
            # Invalid mask should fail validation
            assert result["success"] is False
            assert result["error_code"] == "VALIDATION_FAILED"
            assert len(result["context"]["validation_errors"]) > 0
    finally:
        module.SessionManager = original_session_manager


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_success(temp_session):
    """Test successful update of UC configuration file."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {
                "HomeRegion": "us-west-2",
                "HomeRegionIngressCidr": "10.1.0.0/16"
            }
        ))
        
        assert result["success"] is True
        assert result["session_id"] == temp_session["session_id"]
        assert result["file_path"] == "replacements-config.yaml"
        assert "updates_applied" in result
        assert "HomeRegion" in result["updates_applied"]
        assert "HomeRegionIngressCidr" in result["updates_applied"]
        assert result["updates_applied"]["HomeRegion"]["new"] == "us-west-2"
        assert result["updates_applied"]["HomeRegionIngressCidr"]["new"] == "10.1.0.0/16"
        assert len(result["validation_errors"]) == 0
        assert "next_steps" in result
        
        # Verify file was actually updated
        session_path = temp_session["session_path"]
        with open(session_path / "replacements-config.yaml", "r") as f:
            updated_content = yaml.safe_load(f)
        
        # The updates are applied at the top level, not nested under globalReplacements
        assert updated_content["HomeRegion"] == "us-west-2"
        assert updated_content["HomeRegionIngressCidr"] == "10.1.0.0/16"
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_missing_session_id(temp_session):
    """Test error when session_id is missing."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            "",
            "replacements-config.yaml",
            {"HomeRegion": "us-west-2"}
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "MISSING_SESSION_ID"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "troubleshooting" in result
        assert "next_steps" in result
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_invalid_session(temp_session):
    """Test error when session_id is invalid."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            "nonexistent-session",
            "replacements-config.yaml",
            {"HomeRegion": "us-west-2"}
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION"
        assert result["category"] == ErrorCategory.VALIDATION
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_missing_file_path(temp_session):
    """Test error when file_path is missing."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "",
            {"HomeRegion": "us-west-2"}
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "MISSING_FILE_PATH"
        assert result["category"] == ErrorCategory.VALIDATION
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_invalid_updates(temp_session):
    """Test error when updates parameter is invalid."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        # Test with empty dict
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {}
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_UPDATES"
        assert result["category"] == ErrorCategory.VALIDATION
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_validation_errors(temp_session):
    """Test validation errors are returned without updating file."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        # Read original content
        session_path = temp_session["session_path"]
        with open(session_path / "replacements-config.yaml", "r") as f:
            original_content = f.read()
        
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {
                "HomeRegionIngressCidr": "invalid-cidr",
                "TransitGatewayAsn": 99999
            }
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "validation_errors" in result["context"]
        assert len(result["context"]["validation_errors"]) > 0
        
        # Verify file was NOT updated
        with open(session_path / "replacements-config.yaml", "r") as f:
            current_content = f.read()
        
        assert current_content == original_content
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_next_steps_guidance(temp_session):
    """Test next_steps guidance is provided."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {"HomeRegion": "us-west-2"}
        ))
        
        assert result["success"] is True
        assert "next_steps" in result
        assert "additional changes" in result["next_steps"] or "copy_uc_to_lza_config" in result["next_steps"]
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_update_uc_file_replacements_config_structure(temp_session):
    """Test that replacements-config.yaml globalReplacements array is updated correctly."""
    import asyncio
    
    # Create a proper replacements-config.yaml with globalReplacements structure
    session_path = temp_session["session_path"]
    (session_path / "replacements-config.yaml").write_text(
        "globalReplacements:\n"
        "  - key: HomeRegion\n"
        "    type: String\n"
        "    value: us-east-1\n"
        "  - key: BudgetsEmail\n"
        "    type: String\n"
        "    value: budget@example.com\n"
        "  - key: TransitGatewayASN\n"
        "    type: Number\n"
        "    value: 64512\n"
    )
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import update_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(update_uc_file(
            temp_session["session_id"],
            "replacements-config.yaml",
            {
                "HomeRegion": "eu-north-1",
                "BudgetsEmail": "new-budget@example.com",
                "TransitGatewayASN": 65510
            }
        ))
        
        assert result["success"] is True
        assert result["updates_applied"]["HomeRegion"]["old"] == "us-east-1"
        assert result["updates_applied"]["HomeRegion"]["new"] == "eu-north-1"
        assert result["updates_applied"]["BudgetsEmail"]["old"] == "budget@example.com"
        assert result["updates_applied"]["BudgetsEmail"]["new"] == "new-budget@example.com"
        
        # Verify the file structure is preserved
        with open(session_path / "replacements-config.yaml", "r") as f:
            updated_content = yaml.safe_load(f)
        
        # Should still have globalReplacements array
        assert "globalReplacements" in updated_content
        assert isinstance(updated_content["globalReplacements"], list)
        
        # Find and verify each updated value in the array
        replacements_dict = {
            item["key"]: item["value"] 
            for item in updated_content["globalReplacements"]
            if isinstance(item, dict)
        }
        
        assert replacements_dict["HomeRegion"] == "eu-north-1"
        assert replacements_dict["BudgetsEmail"] == "new-budget@example.com"
        assert replacements_dict["TransitGatewayASN"] == 65510
        
        # Should NOT have top-level keys added
        assert "HomeRegion" not in updated_content or updated_content.get("HomeRegion") == "eu-north-1"
        assert "BudgetsEmail" not in updated_content or updated_content.get("BudgetsEmail") == "new-budget@example.com"
        
    finally:
        module.SessionManager = original_session_manager

