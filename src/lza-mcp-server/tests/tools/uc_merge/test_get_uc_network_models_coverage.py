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

"""Additional coverage tests for get_uc_network_models tool."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_models import (
    tool_get_uc_network_models,
)


def patch_uc_base_path(uc_base):
    """Helper to patch UC base path using environment variable."""
    return patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)})


@pytest.mark.unit
@pytest.mark.uc_merge
class TestGetUCNetworkModelsCoverage:
    """Additional coverage tests for get_uc_network_models tool."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing."""
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_invalid_uc_release_string_validation(self, mock_context):
        """Test error when uc_release fails string validation.

        Covers lines 81-83: Invalid string validation error path
        """
        # Create a string that's too long (> 50 characters)
        invalid_release = "v" + "1" * 60

        result = await tool_get_uc_network_models(mock_context, invalid_release)

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "INVALID_UC_RELEASE"
        assert "troubleshooting" in result
        assert "next_steps" in result
        assert "get_uc_releases" in result["next_steps"]

    @pytest.mark.asyncio
    async def test_release_not_found_no_available_releases(
        self, mock_context, tmp_path
    ):
        """Test error when release not found and no releases available.

        Covers lines 103->108: Branch when available_releases is empty
        """
        # Create empty UC base directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        # Don't create any release directories

        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")

        # Verify error response
        assert result["success"] is False
        assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
        assert "troubleshooting" in result
        assert "No UC releases found" in str(result["troubleshooting"])
        assert "Contact administrator" in result["next_steps"]

    @pytest.mark.asyncio
    async def test_permission_error_accessing_release(self, mock_context, tmp_path):
        """Test error handling for permission denied.

        Covers lines 208-225: PermissionError exception handling
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()

        # Mock iterdir to raise PermissionError
        with patch_uc_base_path(uc_base):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = PermissionError("Access denied")

                result = await tool_get_uc_network_models(mock_context, "v1.0.0")

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "PERMISSION_DENIED"
        assert "Permission denied" in result["error"]
        assert "troubleshooting" in result
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_unexpected_error_during_discovery(self, mock_context, tmp_path):
        """Test error handling for unexpected exceptions.

        Covers lines 208-225: General exception handling
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()

        # Mock iterdir to raise unexpected exception
        with patch_uc_base_path(uc_base):
            with patch("pathlib.Path.iterdir") as mock_iterdir:
                mock_iterdir.side_effect = RuntimeError("Unexpected error")

                result = await tool_get_uc_network_models(mock_context, "v1.0.0")

        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "Unexpected error" in result["error"]
        assert "troubleshooting" in result
        assert "context" in result
        assert "error_type" in result["context"]
        assert result["context"]["error_type"] == "RuntimeError"
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_skips_special_directories(self, mock_context, tmp_path):
        """Test that special directories are skipped during model discovery.

        Verifies that docs, scripts, .git, .github directories are ignored
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()

        # Create model directories
        (release_dir / "hub-and-spoke").mkdir()
        (release_dir / "shared-vpc").mkdir()

        # Create special directories that should be skipped
        (release_dir / "docs").mkdir()
        (release_dir / "scripts").mkdir()
        (release_dir / ".git").mkdir()
        (release_dir / ".github").mkdir()

        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")

        # Verify only model directories are returned
        assert result["success"] is True
        assert len(result["available_models"]) == 2
        assert "hub-and-spoke" in result["available_models"]
        assert "shared-vpc" in result["available_models"]
        assert "docs" not in result["available_models"]
        assert "scripts" not in result["available_models"]
        assert ".git" not in result["available_models"]
        assert ".github" not in result["available_models"]
