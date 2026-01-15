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
        session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
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
        "base_dir": tmp_path,
    }


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
        result = asyncio.run(
            update_uc_file(
                temp_session["session_id"],
                "replacements-config.yaml",
                {"HomeRegion": "us-west-2", "HomeRegionIngressCidr": "10.1.0.0/16"},
            )
        )

        assert result["success"] is True
        assert result["session_id"] == temp_session["session_id"]
        assert result["file_path"] == "replacements-config.yaml"
        assert "updates_applied" in result
        assert "HomeRegion" in result["updates_applied"]
        assert "HomeRegionIngressCidr" in result["updates_applied"]
        assert result["updates_applied"]["HomeRegion"]["new"] == "us-west-2"
        assert (
            result["updates_applied"]["HomeRegionIngressCidr"]["new"] == "10.1.0.0/16"
        )
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
        result = asyncio.run(
            update_uc_file("", "replacements-config.yaml", {"HomeRegion": "us-west-2"})
        )

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
        result = asyncio.run(
            update_uc_file(
                "nonexistent-session",
                "replacements-config.yaml",
                {"HomeRegion": "us-west-2"},
            )
        )

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
        result = asyncio.run(
            update_uc_file(temp_session["session_id"], "", {"HomeRegion": "us-west-2"})
        )

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
        result = asyncio.run(
            update_uc_file(temp_session["session_id"], "replacements-config.yaml", {})
        )

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

        result = asyncio.run(
            update_uc_file(
                temp_session["session_id"],
                "replacements-config.yaml",
                {"HomeRegionIngressCidr": "invalid-cidr", "TransitGatewayAsn": 99999},
            )
        )

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
        result = asyncio.run(
            update_uc_file(
                temp_session["session_id"],
                "replacements-config.yaml",
                {"HomeRegion": "us-west-2"},
            )
        )

        assert result["success"] is True
        assert "next_steps" in result
        assert (
            "additional changes" in result["next_steps"]
            or "copy_uc_to_lza_config" in result["next_steps"]
        )
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
        result = asyncio.run(
            update_uc_file(
                temp_session["session_id"],
                "replacements-config.yaml",
                {
                    "HomeRegion": "eu-north-1",
                    "BudgetsEmail": "new-budget@example.com",
                    "TransitGatewayASN": 65510,
                },
            )
        )

        assert result["success"] is True
        assert result["updates_applied"]["HomeRegion"]["old"] == "us-east-1"
        assert result["updates_applied"]["HomeRegion"]["new"] == "eu-north-1"
        assert result["updates_applied"]["BudgetsEmail"]["old"] == "budget@example.com"
        assert (
            result["updates_applied"]["BudgetsEmail"]["new"] == "new-budget@example.com"
        )

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
        assert (
            "HomeRegion" not in updated_content
            or updated_content.get("HomeRegion") == "eu-north-1"
        )
        assert (
            "BudgetsEmail" not in updated_content
            or updated_content.get("BudgetsEmail") == "new-budget@example.com"
        )

    finally:
        module.SessionManager = original_session_manager
