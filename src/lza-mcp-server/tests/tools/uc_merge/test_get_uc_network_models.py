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

"""Unit tests for get_uc_network_models tool."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_models import (
    tool_get_uc_network_models,
)


def patch_uc_base_path(uc_base):
    """Helper to patch UC_BASE_PATH in the common module."""
    # We need to patch both UC_BASE_PATH and the function that uses it
    return patch.multiple(
        "awslabs.lza_mcp_server.tools.uc_merge.common",
        UC_BASE_PATH=uc_base,
        get_uc_release_path=lambda uc_release: uc_base / uc_release
    )


@pytest.mark.unit
@pytest.mark.uc_merge
class TestGetUCNetworkModels:
    """Test suite for get_uc_network_models tool."""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing."""
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()
        return ctx
    
    @pytest.mark.asyncio
    async def test_model_discovery_for_valid_release(self, mock_context, tmp_path):
        """Test model discovery for valid release.
        
        Requirements: 5.1, 5.4, 5.5
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Create release directory
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        
        # Create network model directories
        (release_dir / "hub-and-spoke").mkdir()
        (release_dir / "shared-vpc").mkdir()
        (release_dir / "hub-and-spoke-for-govcloud-us").mkdir()
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify success
        assert result["success"] is True
        assert "available_models" in result
        assert "uc_release" in result
        assert result["uc_release"] == "v1.0.0"
        
        # Verify all models are found
        assert len(result["available_models"]) == 3
        assert "hub-and-spoke" in result["available_models"]
        assert "shared-vpc" in result["available_models"]
        assert "hub-and-spoke-for-govcloud-us" in result["available_models"]
        
        # Verify models are sorted alphabetically
        assert result["available_models"] == sorted(result["available_models"])
    
    @pytest.mark.asyncio
    async def test_error_when_uc_release_missing(self, mock_context):
        """Test error when uc_release parameter is missing.
        
        Requirements: 5.2, 5.8
        """
        # Call with empty string
        result = await tool_get_uc_network_models(mock_context, "")
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "MISSING_UC_RELEASE"
        assert "troubleshooting" in result
        assert "next_steps" in result
        assert "get_uc_releases" in result["next_steps"]
    
    @pytest.mark.asyncio
    async def test_error_when_uc_release_invalid(self, mock_context, tmp_path):
        """Test error when uc_release is invalid.
        
        Requirements: 5.3
        """
        # Create test UC directory structure with some releases
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        (uc_base / "v1.0.0").mkdir()
        (uc_base / "v2.0.0").mkdir()
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v99.99.99")
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "UC_RELEASE_NOT_FOUND"
        assert "troubleshooting" in result
        assert "context" in result
        assert "available_releases" in result["context"]
        
        # Verify available releases are listed
        assert "v1.0.0" in result["context"]["available_releases"]
        assert "v2.0.0" in result["context"]["available_releases"]
    
    @pytest.mark.asyncio
    async def test_documentation_url_included(self, mock_context, tmp_path):
        """Test documentation URL is included in response.
        
        Requirements: 5.6
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        
        # Create model directories
        (release_dir / "hub-and-spoke").mkdir()
        (release_dir / "shared-vpc").mkdir()
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify success
        assert result["success"] is True
        
        # Verify documentation URL is included
        assert "documentation_url" in result
        assert result["documentation_url"] is not None
        assert "github.com/aws/lza-universal-configuration" in result["documentation_url"]
        assert "docs/index.adoc" in result["documentation_url"]
    
    @pytest.mark.asyncio
    async def test_empty_release_directory(self, mock_context, tmp_path):
        """Test handling of release directory with no models."""
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        # Don't create any model directories
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify success with empty models
        assert result["success"] is True
        assert result["available_models"] == []
        assert result["models"] == {}
        assert "next_steps" in result
        assert "No network models" in result["next_steps"]
    
    @pytest.mark.asyncio
    async def test_next_steps_guidance(self, mock_context, tmp_path):
        """Test next_steps guidance is included in response.
        
        Requirements: 5.10
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        (release_dir / "hub-and-spoke").mkdir()
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify next_steps is present and contains guidance
        assert result["success"] is True
        assert "next_steps" in result
        assert len(result["next_steps"]) > 0
        assert "start_uc_merge_session" in result["next_steps"]
        assert "Present" in result["next_steps"] or "present" in result["next_steps"]
    
    @pytest.mark.asyncio
    async def test_ignores_files_in_release_directory(self, mock_context, tmp_path):
        """Test that files in release directory are ignored, only directories are considered."""
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        
        # Create model directories
        (release_dir / "hub-and-spoke").mkdir()
        
        # Create files that should be ignored
        (release_dir / "README.md").write_text("readme")
        (release_dir / "config.yaml").write_text("config")
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify only directories are returned
        assert result["success"] is True
        assert len(result["available_models"]) == 1
        assert "hub-and-spoke" in result["available_models"]
        assert "README.md" not in result["available_models"]
        assert "config.yaml" not in result["available_models"]
    
    @pytest.mark.asyncio
    async def test_release_path_is_file_not_directory(self, mock_context, tmp_path):
        """Test error handling when release path is a file, not a directory."""
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Create a file instead of directory
        release_file = uc_base / "v1.0.0"
        release_file.write_text("not a directory")
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "UC_RELEASE_NOT_DIRECTORY"
    

    
    @pytest.mark.asyncio
    async def test_next_steps_includes_documentation_reference(self, mock_context, tmp_path):
        """Test next_steps includes reference to GitHub documentation."""
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        release_dir = uc_base / "v1.0.0"
        release_dir.mkdir()
        
        # Create model directories
        (release_dir / "hub-and-spoke").mkdir()
        (release_dir / "shared-vpc").mkdir()
        
        # Patch the UC_BASE_PATH
        with patch_uc_base_path(uc_base):
            result = await tool_get_uc_network_models(mock_context, "v1.0.0")
        
        # Verify success
        assert result["success"] is True
        assert len(result["available_models"]) == 2
        
        # Verify next_steps mentions documentation
        assert "next_steps" in result
        assert "github.com/aws/lza-universal-configuration" in result["next_steps"]
