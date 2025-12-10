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

"""Tests for read_uc_file tool."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from hypothesis import given, strategies as st, settings, HealthCheck

from awslabs.lza_mcp_server.tools.uc_merge.read_uc_file import (
    read_uc_file,
    get_next_steps_for_uc_file,
)
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager
from awslabs.lza_mcp_server.error_categories import ErrorCategory


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


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
    (session_path / "accounts-config.yaml").write_text(
        "mandatoryAccounts:\n"
        "  - email: management@example.com\n"
        "    name: Management\n"
        "workloadAccounts:\n"
        "  - email: network@example.com\n"
        "    name: Network\n"
    )
    
    (session_path / "replacements-config.yaml").write_text(
        "globalReplacements:\n"
        "  - key: HomeRegion\n"
        "    value: us-east-1\n"
    )
    
    (session_path / "global-config.yaml").write_text(
        "homeRegion: us-east-1\n"
        "enabledRegions:\n"
        "  - us-east-1\n"
    )
    
    (session_path / "network-config.yaml").write_text(
        "transitGateways:\n"
        "  - name: Network-Main\n"
        "vpcs:\n"
        "  - name: SharedServices\n"
    )
    
    # Create a subdirectory with files
    policies_dir = session_path / "service-control-policies"
    policies_dir.mkdir()
    (policies_dir / "guardrails.json").write_text('{"Version": "2012-10-17"}')
    
    return {
        "session_id": session_id,
        "session_path": session_path,
        "session_manager": session_manager,
        "base_dir": tmp_path
    }


# ============================================================================
# Property-Based Tests
# ============================================================================

# Feature: uc-merge, Property 7: Session validation for UC operations
@pytest.mark.property
@pytest.mark.uc_merge
@pytest.mark.unit
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    invalid_session_id=st.one_of(
        st.just(""),
        st.just("nonexistent-session"),
        st.just("invalid-session-12345"),
        st.just("uc-session-99999999-999999"),
        st.text(min_size=1, max_size=50).filter(lambda x: not x.startswith("uc-session-"))
    )
)
def test_property_session_validation(mock_ctx, temp_session, invalid_session_id):
    """Property 7: Session validation for UC operations.
    
    For any call to read_uc_file without a valid session_id, the tool should
    return an error indicating a session must be started first.
    
    Validates: Requirements 6.2
    """
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(mock_ctx, invalid_session_id, "accounts-config.yaml"))
        
        assert result["success"] is False
        assert result["error_code"] in ["MISSING_SESSION_ID", "INVALID_SESSION"]
        assert result["category"] == ErrorCategory.VALIDATION
        assert "session" in result["error"].lower()
    finally:
        # Restore original
        module.SessionManager = original_session_manager


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_valid_uc_file(mock_ctx, temp_session):
    """Test reading a valid UC configuration file."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "accounts-config.yaml"
        ))
        
        assert result["success"] is True
        assert result["session_id"] == temp_session["session_id"]
        assert result["file_path"] == "accounts-config.yaml"
        assert "mandatoryAccounts" in result["content"]
        assert "workloadAccounts" in result["content"]
        assert result["size_bytes"] > 0
        assert "next_steps" in result
        assert "workload account emails" in result["next_steps"]
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_in_subdirectory(mock_ctx, temp_session):
    """Test reading a UC file in a subdirectory."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "service-control-policies/guardrails.json"
        ))
        
        assert result["success"] is True
        assert result["file_path"] == "service-control-policies/guardrails.json"
        assert "Version" in result["content"]
        assert result["size_bytes"] > 0
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_missing_session_id(mock_ctx, temp_session):
    """Test error when session_id is missing."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(mock_ctx, "", "accounts-config.yaml"))
        
        assert result["success"] is False
        assert result["error_code"] == "MISSING_SESSION_ID"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "session" in result["error"].lower()
        assert "troubleshooting" in result
        assert "next_steps" in result
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_invalid_session(mock_ctx, temp_session):
    """Test error when session_id is invalid."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            "nonexistent-session",
            "accounts-config.yaml"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "session" in result["error"].lower()
        assert "troubleshooting" in result
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_not_found(mock_ctx, temp_session):
    """Test error when file does not exist."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "nonexistent-file.yaml"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert result["category"] == ErrorCategory.FILE_NOT_FOUND
        assert "not found" in result["error"].lower()
        assert "troubleshooting" in result
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_path_traversal(mock_ctx, temp_session):
    """Test security validation for path traversal."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "../../../etc/passwd"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "PATH_TRAVERSAL"
        assert result["category"] == ErrorCategory.SECURITY
        assert "path traversal" in result["error"].lower() or ".." in result["error"]
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_absolute_path(mock_ctx, temp_session):
    """Test security validation for absolute paths."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "/etc/passwd"
        ))
        
        assert result["success"] is False
        assert result["error_code"] in ["BOUNDARY_VIOLATION", "PATH_TRAVERSAL"]
        assert result["category"] == ErrorCategory.SECURITY
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_is_directory(mock_ctx, temp_session):
    """Test error when path points to a directory."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "service-control-policies"
        ))
        
        assert result["success"] is False
        assert result["error_code"] == "NOT_A_FILE"
        assert result["category"] == ErrorCategory.FILE_OPERATION
        assert "not a file" in result["error"].lower()
    finally:
        module.SessionManager = original_session_manager


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_accounts_config():
    """Test next_steps guidance for accounts-config.yaml."""
    next_steps = get_next_steps_for_uc_file("accounts-config.yaml")
    
    assert "workload account emails" in next_steps
    assert "mandatory account emails" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_replacements_config():
    """Test next_steps guidance for replacements-config.yaml."""
    next_steps = get_next_steps_for_uc_file("replacements-config.yaml")
    
    assert "network settings" in next_steps
    assert "replacements" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_global_config():
    """Test next_steps guidance for global-config.yaml."""
    next_steps = get_next_steps_for_uc_file("global-config.yaml")
    
    assert "global settings" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_network_config():
    """Test next_steps guidance for network-config.yaml."""
    next_steps = get_next_steps_for_uc_file("network-config.yaml")
    
    assert "network configuration" in next_steps
    assert "CIDR" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_iam_config():
    """Test next_steps guidance for iam-config.yaml."""
    next_steps = get_next_steps_for_uc_file("iam-config.yaml")
    
    assert "IAM configuration" in next_steps
    assert "roles" in next_steps.lower() or "policies" in next_steps.lower()


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_security_config():
    """Test next_steps guidance for security-config.yaml."""
    next_steps = get_next_steps_for_uc_file("security-config.yaml")
    
    assert "security" in next_steps.lower()


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_organization_config():
    """Test next_steps guidance for organization-config.yaml."""
    next_steps = get_next_steps_for_uc_file("organization-config.yaml")
    
    assert "organization" in next_steps.lower()


@pytest.mark.unit
@pytest.mark.uc_merge
def test_next_steps_for_other_files():
    """Test next_steps guidance for other files."""
    next_steps = get_next_steps_for_uc_file("some-other-file.yaml")
    
    assert "review" in next_steps.lower()
    assert "update_uc_file" in next_steps


@pytest.mark.unit
@pytest.mark.uc_merge
def test_read_uc_file_with_special_characters(mock_ctx, temp_session):
    """Test reading a file with special characters in content."""
    import asyncio
    
    # Patch the SessionManager to use our temp directory
    from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module
    original_session_manager = module.SessionManager
    
    def patched_session_manager():
        return temp_session["session_manager"]
    
    module.SessionManager = patched_session_manager
    
    try:
        # Create a file with special characters
        special_content = "key: value with émojis 🎉 and spëcial çhars"
        session_path = temp_session["session_path"]
        (session_path / "special.yaml").write_text(special_content, encoding="utf-8")
        
        result = asyncio.run(read_uc_file(
            mock_ctx,
            temp_session["session_id"],
            "special.yaml"
        ))
        
        assert result["success"] is True
        assert result["content"] == special_content
    finally:
        module.SessionManager = original_session_manager
