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

"""Unit tests for get_uc_releases tool."""

import pytest
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from awslabs.lza_mcp_server.tools.uc_merge.get_uc_releases import (
    tool_get_uc_releases,
    _parse_version
)


@pytest.mark.unit
@pytest.mark.uc_merge
class TestGetUCReleases:
    """Test suite for get_uc_releases tool."""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context for testing."""
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()
        return ctx
    
    @pytest.mark.asyncio
    async def test_release_discovery_from_filesystem(self, mock_context, tmp_path):
        """Test release discovery from filesystem.
        
        Requirements: 1.1, 1.2, 1.3
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Create release directories
        (uc_base / "v1.0.0").mkdir()
        (uc_base / "v1.1.0").mkdir()
        (uc_base / "v2.0.0").mkdir()
        
        # Test with temporary directory
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify success
        assert result["success"] is True
        assert "releases" in result
        assert len(result["releases"]) == 3
        
        # Verify all releases are found
        release_names = [r["name"] for r in result["releases"]]
        assert "v1.0.0" in release_names
        assert "v1.1.0" in release_names
        assert "v2.0.0" in release_names
        
        # Verify paths are included
        for release in result["releases"]:
            assert "name" in release
            assert "path" in release
            assert Path(release["path"]).exists()
    
    @pytest.mark.asyncio
    async def test_version_ordering(self, mock_context, tmp_path):
        """Test releases are returned in descending version order (newest first).
        
        Requirements: 1.5
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Create releases in random order
        (uc_base / "v1.0.0").mkdir()
        (uc_base / "v2.1.0").mkdir()
        (uc_base / "v1.5.0").mkdir()
        (uc_base / "v2.0.0").mkdir()
        
        # Test with temporary directory
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify success
        assert result["success"] is True
        
        # Verify descending order (newest first)
        release_names = [r["name"] for r in result["releases"]]
        assert release_names == ["v2.1.0", "v2.0.0", "v1.5.0", "v1.0.0"]
    
    @pytest.mark.asyncio
    async def test_empty_directory_handling(self, mock_context, tmp_path):
        """Test handling of empty UC directory.
        
        Requirements: 1.1, 1.2
        """
        # Create empty UC directory
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Test with empty directory
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify success with empty releases
        assert result["success"] is True
        assert result["releases"] == []
        assert "next_steps" in result
        assert "No UC releases" in result["next_steps"]
    
    @pytest.mark.asyncio
    async def test_next_steps_guidance(self, mock_context, tmp_path):
        """Test next_steps guidance is included in response.
        
        Requirements: 1.4
        """
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        (uc_base / "v1.0.0").mkdir()
        
        # Test with temporary directory
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify next_steps is present and contains guidance
        assert result["success"] is True
        assert "next_steps" in result
        assert len(result["next_steps"]) > 0
        assert "get_uc_network_models" in result["next_steps"]
        assert "Present" in result["next_steps"] or "present" in result["next_steps"]
    
    @pytest.mark.asyncio
    async def test_directory_not_found(self, mock_context, tmp_path):
        """Test error handling when UC directory doesn't exist."""
        # Use non-existent directory
        non_existent = tmp_path / "does-not-exist"
        
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(non_existent)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "UC_DIRECTORY_NOT_FOUND"
        assert "troubleshooting" in result
        assert "next_steps" in result
    
    @pytest.mark.asyncio
    async def test_path_is_file_not_directory(self, mock_context, tmp_path):
        """Test error handling when UC path is a file, not a directory."""
        # Create a file instead of directory
        uc_file = tmp_path / "lza-uc"
        uc_file.write_text("not a directory")
        
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_file)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert result["error_code"] == "UC_PATH_NOT_DIRECTORY"
    
    @pytest.mark.asyncio
    async def test_default_path_used(self, mock_context):
        """Test that default path is used when environment variable not set."""
        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                result = await tool_get_uc_releases(mock_context)
        
        # Should attempt to use default path
        assert result["success"] is False
        assert "/app/lza-uc" in result["error"]
    
    @pytest.mark.asyncio
    async def test_ignores_files_in_uc_directory(self, mock_context, tmp_path):
        """Test that files in UC directory are ignored, only directories are considered."""
        # Create test UC directory structure
        uc_base = tmp_path / "lza-uc"
        uc_base.mkdir()
        
        # Create release directories
        (uc_base / "v1.0.0").mkdir()
        (uc_base / "v2.0.0").mkdir()
        
        # Create files that should be ignored
        (uc_base / "README.md").write_text("readme")
        (uc_base / "config.yaml").write_text("config")
        
        # Test with temporary directory
        with patch.dict(os.environ, {"LZA_UC_BASE_PATH": str(uc_base)}):
            result = await tool_get_uc_releases(mock_context)
        
        # Verify only directories are returned
        assert result["success"] is True
        assert len(result["releases"]) == 2
        release_names = [r["name"] for r in result["releases"]]
        assert "README.md" not in release_names
        assert "config.yaml" not in release_names


@pytest.mark.unit
class TestParseVersion:
    """Test suite for version parsing utility."""
    
    def test_parse_version_with_v_prefix(self):
        """Test parsing version with 'v' prefix."""
        assert _parse_version("v1.0.0") == (1, 0, 0)
        assert _parse_version("v2.1.3") == (2, 1, 3)
    
    def test_parse_version_without_v_prefix(self):
        """Test parsing version without 'v' prefix."""
        assert _parse_version("1.0.0") == (1, 0, 0)
        assert _parse_version("2.1.3") == (2, 1, 3)
    
    def test_parse_version_comparison(self):
        """Test version comparison for sorting."""
        v1 = _parse_version("v1.0.0")
        v2 = _parse_version("v2.0.0")
        v1_5 = _parse_version("v1.5.0")
        
        assert v2 > v1_5 > v1
    
    def test_parse_version_invalid_format(self):
        """Test parsing invalid version format returns fallback."""
        result = _parse_version("invalid")
        assert result == (0, 0, 0)
        
        result = _parse_version("v1.x.0")
        assert result == (0, 0, 0)
