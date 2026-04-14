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

"""Unit tests for update_uc_file validation."""

import pytest

from awslabs.lza_mcp_server.tools.uc_merge.update_uc_file import update_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager
from awslabs.lza_mcp_server.error_categories import ErrorCategory


@pytest.fixture
def temp_session(tmp_path):
    """Create a temporary UC session directory structure."""
    session_manager = SessionManager(base_session_dir=tmp_path)
    session_id = session_manager.generate_session_id()
    session_path = session_manager.create_session_directory(session_id)
    session_manager.save_session_metadata(
        session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
    )

    # Create sample configuration file
    (session_path / "test-config.yaml").write_text(
        "HomeRegion: us-east-1\n"
        "HomeRegionIngressCidr: 10.0.0.0/16\n"
        "DevVpcMaskLength: 24\n"
        "TransitGatewayAsn: 64512\n"
        "SubnetMaskLength: 26\n"
    )

    return {
        "session_id": session_id,
        "session_path": session_path,
        "session_manager": session_manager,
    }


class TestInputValidation:
    """Test input parameter validation."""

    @pytest.mark.asyncio
    async def test_missing_session_id(self, temp_session, monkeypatch):
        """Test error when session_id is missing."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            "", "test-config.yaml", {"HomeRegion": "us-west-2"}
        )

        assert result["success"] is False
        assert result["error_code"] == "MISSING_SESSION_ID"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "troubleshooting" in result
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_invalid_session(self, temp_session, monkeypatch):
        """Test error when session_id is invalid."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            "nonexistent-session", "test-config.yaml", {"HomeRegion": "us-west-2"}
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_SESSION"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "context" not in result

    @pytest.mark.asyncio
    async def test_missing_file_path(self, temp_session, monkeypatch):
        """Test error when file_path is missing."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"], "", {"HomeRegion": "us-west-2"}
        )

        assert result["success"] is False
        assert result["error_code"] == "MISSING_FILE_PATH"
        assert result["category"] == ErrorCategory.VALIDATION

    @pytest.mark.asyncio
    async def test_empty_updates_dict(self, temp_session, monkeypatch):
        """Test error when updates parameter is empty."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"], "test-config.yaml", {}
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_UPDATES"
        assert result["category"] == ErrorCategory.VALIDATION

    @pytest.mark.asyncio
    async def test_non_dict_updates(self, temp_session, monkeypatch):
        """Test error when updates parameter is not a dictionary."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"], "test-config.yaml", None
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_UPDATES"
        assert result["category"] == ErrorCategory.VALIDATION


class TestValueValidation:
    """Test value validation for different field types."""

    @pytest.mark.asyncio
    async def test_invalid_cidr_format(self, temp_session, monkeypatch):
        """Test validation error for invalid CIDR format."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {"HomeRegionIngressCidr": "invalid-cidr"},
        )

        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert result["category"] == ErrorCategory.VALIDATION
        assert "validation_errors" in result["context"]
        assert len(result["context"]["validation_errors"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_asn_range(self, temp_session, monkeypatch):
        """Test validation error for ASN out of range."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {"TransitGatewayAsn": 99999},
        )

        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert "validation_errors" in result["context"]

    @pytest.mark.asyncio
    async def test_invalid_vpc_mask_length(self, temp_session, monkeypatch):
        """Test validation error for VPC mask length out of range."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {"DevVpcMaskLength": 30},
        )

        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert "validation_errors" in result["context"]

    @pytest.mark.asyncio
    async def test_invalid_subnet_mask_length(self, temp_session, monkeypatch):
        """Test validation error for subnet mask length out of range."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {"SubnetMaskLength": 10},
        )

        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert "validation_errors" in result["context"]

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self, temp_session, monkeypatch):
        """Test multiple validation errors are collected."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {
                "HomeRegionIngressCidr": "invalid",
                "TransitGatewayAsn": 99999,
                "DevVpcMaskLength": 30,
            },
        )

        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert len(result["context"]["validation_errors"]) >= 2

    @pytest.mark.asyncio
    async def test_file_not_modified_on_validation_error(
        self, temp_session, monkeypatch
    ):
        """Test file is not modified when validation fails."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Read original content
        session_path = temp_session["session_path"]
        original_content = (session_path / "test-config.yaml").read_text()

        result = await update_uc_file(
            temp_session["session_id"],
            "test-config.yaml",
            {"HomeRegionIngressCidr": "invalid-cidr"},
        )

        assert result["success"] is False

        # Verify file was not modified
        current_content = (session_path / "test-config.yaml").read_text()
        assert current_content == original_content
