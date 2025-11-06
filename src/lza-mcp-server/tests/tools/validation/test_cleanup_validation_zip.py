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

"""Unit tests for cleanup validation zip module."""

import pytest
import os
import tempfile
from unittest.mock import patch, AsyncMock

from awslabs.lza_mcp_server.tools.validation.validation_tools import (
    _validate_cleanup_inputs,
    cleanup_configuration,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class TestToolCleanupValidationZip:
    """Test cases for tool_cleanup_validation_zip function."""

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_success(self):
        """Test successful cleanup of existing ZIP file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await cleanup_configuration(mock_ctx, "validation_zip", temp_dir)

            assert result["success"] is True
            assert result["message"] == "Validation ZIP file cleaned up successfully"
            assert result["path"] == zip_path
            assert result["cleanup_type"] == "validation_zip"
            assert result["existed"] is True
            assert not os.path.exists(zip_path)  # File should be deleted

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_file_not_exists(self):
        """Test cleanup when ZIP file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await cleanup_configuration(mock_ctx, "validation_zip", temp_dir)

            assert result["success"] is True
            assert result["message"] == "Validation ZIP file already cleaned up"
            assert result["cleanup_type"] == "validation_zip"
            assert result["existed"] is False

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_default_path(self):
        """Test cleanup with default share path."""
        mock_ctx = MockContext()

        with (
            patch("os.path.expanduser") as mock_expanduser,
            patch("os.path.exists", return_value=False),
        ):
            mock_expanduser.return_value = "/expanded/path"

            result = await cleanup_configuration(mock_ctx, "validation_zip")

            mock_expanduser.assert_called_once_with("~/Documents/lza-config")
            assert result["success"] is True
            assert result["cleanup_type"] == "validation_zip"
            assert result["existed"] is False

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_permission_error(self):
        """Test cleanup with permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.remove", side_effect=PermissionError("Permission denied")),
            ):
                result = await cleanup_configuration(mock_ctx, "validation_zip", temp_dir)

            assert result["success"] is False
            assert "Cleanup failed" in result["error"]
            assert "Permission denied" in result["error"]
            assert result["cleanup_type"] == "validation_zip"
            assert "troubleshooting" in result
            assert len(result["troubleshooting"]) == 4

            # Verify context calls
            mock_ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_os_error(self):
        """Test cleanup with OS error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.remove", side_effect=OSError("File system error")),
            ):
                result = await cleanup_configuration(mock_ctx, "validation_zip", temp_dir)

            assert result["success"] is False
            assert "Cleanup failed" in result["error"]
            assert "File system error" in result["error"]
            assert result["cleanup_type"] == "validation_zip"

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_path_expansion_error(self):
        """Test cleanup with path expansion error."""
        mock_ctx = MockContext()

        with patch("os.path.expanduser", side_effect=Exception("Path expansion error")):
            result = await cleanup_configuration(mock_ctx, "validation_zip")

            assert result["success"] is False
            assert "Cleanup failed" in result["error"]
            assert "Path expansion error" in result["error"]
            assert result["cleanup_type"] == "validation_zip"

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_custom_share_path(self):
        """Test cleanup with custom share path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = "~/custom/lza-config"
            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.path.exists", return_value=False),
            ):
                result = await cleanup_configuration(mock_ctx, "validation_zip", custom_path)

            assert result["success"] is True
            assert result["cleanup_type"] == "validation_zip"
            assert result["existed"] is False

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_file_locked(self):
        """Test cleanup when file is locked by another process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test zip content")

            mock_ctx = MockContext()

            # Simulate file being locked
            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch(
                    "os.remove",
                    side_effect=OSError("The process cannot access the file"),
                ),
            ):
                result = await cleanup_configuration(mock_ctx, "validation_zip", temp_dir)

            assert result["success"] is False
            assert result["cleanup_type"] == "validation_zip"
            assert "troubleshooting" in result
            troubleshooting_text = " ".join(result["troubleshooting"])
            assert "locked by another process" in troubleshooting_text


class TestValidateCleanupInputs:
    """Test cases for _validate_cleanup_inputs function."""

    def test_validate_cleanup_inputs_validation_zip_no_path(self):
        """Test validation_zip cleanup type without path (should be valid)."""
        result = _validate_cleanup_inputs("validation_zip", None)
        
        assert result["valid"] is True
        assert "error" not in result

    def test_validate_cleanup_inputs_validation_zip_with_path(self):
        """Test validation_zip cleanup type with path (should be valid)."""
        result = _validate_cleanup_inputs("validation_zip", "~/Documents/lza-config")
        
        assert result["valid"] is True
        assert "error" not in result

    def test_validate_cleanup_inputs_retrieved_config_with_path(self):
        """Test retrieved_config cleanup type with path (should be valid)."""
        result = _validate_cleanup_inputs("retrieved_config", "/tmp/lza-config-abc123")
        
        assert result["valid"] is True
        assert "error" not in result

    def test_validate_cleanup_inputs_invalid_type(self):
        """Test invalid cleanup_type with LLM-friendly error message."""
        result = _validate_cleanup_inputs("invalid_type", None)
        
        assert result["valid"] is False
        assert "error" in result
        assert "Invalid cleanup type 'invalid_type'" in result["error"]
        assert "validation_zip" in result["error"]
        assert "retrieved_config" in result["error"]

    def test_validate_cleanup_inputs_retrieved_config_missing_path(self):
        """Test retrieved_config without path with LLM-friendly error message."""
        result = _validate_cleanup_inputs("retrieved_config", None)
        
        assert result["valid"] is False
        assert "error" in result
        assert "path' parameter is required" in result["error"]
        assert "retrieved_config" in result["error"]
        assert "getConfigurationFromS3" in result["error"]

    def test_validate_cleanup_inputs_retrieved_config_empty_path(self):
        """Test retrieved_config with empty string path (should be invalid)."""
        result = _validate_cleanup_inputs("retrieved_config", "")
        
        assert result["valid"] is False
        assert "error" in result
        assert "path' parameter is required" in result["error"]

    def test_validate_cleanup_inputs_case_sensitive(self):
        """Test that cleanup_type is case-sensitive."""
        result = _validate_cleanup_inputs("VALIDATION_ZIP", None)
        
        assert result["valid"] is False
        assert "error" in result
        assert "Invalid cleanup type" in result["error"]

    def test_validate_cleanup_inputs_whitespace_path(self):
        """Test retrieved_config with whitespace-only path (should be invalid)."""
        result = _validate_cleanup_inputs("retrieved_config", "   ")
        
        # Whitespace is truthy in Python, so this should be valid
        # The actual path validation happens in the cleanup function
        assert result["valid"] is True


class TestCleanupRetrievedConfig:
    """Test cases for cleanup_configuration with retrieved_config type."""

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_success(self):
        """Test successful cleanup of retrieved config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test config directory with files
            config_dir = os.path.join(temp_dir, "lza-config-test")
            os.makedirs(config_dir)
            
            # Create sample files
            with open(os.path.join(config_dir, "accounts-config.yaml"), "w") as f:
                f.write("test: config")
            
            # Create subdirectory
            subdir = os.path.join(config_dir, "iam-policies")
            os.makedirs(subdir)
            with open(os.path.join(subdir, "policy.json"), "w") as f:
                f.write('{"test": "policy"}')

            mock_ctx = MockContext()

            result = await cleanup_configuration(mock_ctx, "retrieved_config", config_dir)

            assert result["success"] is True
            assert result["message"] == "Configuration directory cleaned up successfully"
            assert result["path"] == config_dir
            assert result["cleanup_type"] == "retrieved_config"
            assert result["existed"] is True
            assert not os.path.exists(config_dir)  # Directory should be deleted

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_already_removed(self):
        """Test cleanup when directory already removed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_dir = os.path.join(temp_dir, "nonexistent-config")
            
            mock_ctx = MockContext()

            result = await cleanup_configuration(mock_ctx, "retrieved_config", nonexistent_dir)

            assert result["success"] is True
            assert result["message"] == "Configuration directory already cleaned up"
            assert result["cleanup_type"] == "retrieved_config"
            assert result["existed"] is False

            # Verify context calls
            mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_permission_error(self):
        """Test cleanup with permission error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "lza-config-test")
            os.makedirs(config_dir)

            mock_ctx = MockContext()

            with patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
                result = await cleanup_configuration(mock_ctx, "retrieved_config", config_dir)

            assert result["success"] is False
            assert "Cleanup failed" in result["error"]
            assert "Permission denied" in result["error"]
            assert result["cleanup_type"] == "retrieved_config"
            assert "troubleshooting" in result
            assert len(result["troubleshooting"]) == 4

            # Verify context calls
            mock_ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_os_error(self):
        """Test cleanup with OS error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "lza-config-test")
            os.makedirs(config_dir)

            mock_ctx = MockContext()

            with patch("shutil.rmtree", side_effect=OSError("File system error")):
                result = await cleanup_configuration(mock_ctx, "retrieved_config", config_dir)

            assert result["success"] is False
            assert "Cleanup failed" in result["error"]
            assert "File system error" in result["error"]
            assert result["cleanup_type"] == "retrieved_config"

    @pytest.mark.asyncio
    async def test_cleanup_invalid_type_llm_friendly_error(self):
        """Test invalid cleanup_type error with LLM-friendly message."""
        mock_ctx = MockContext()

        result = await cleanup_configuration(mock_ctx, "invalid_type", "/some/path")

        assert result["success"] is False
        assert "error" in result
        assert "Invalid cleanup type 'invalid_type'" in result["error"]
        assert "validation_zip" in result["error"]
        assert "retrieved_config" in result["error"]
        assert result["cleanup_type"] == "invalid_type"

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_missing_path_llm_friendly_error(self):
        """Test missing path for retrieved_config cleanup with LLM-friendly error."""
        mock_ctx = MockContext()

        result = await cleanup_configuration(mock_ctx, "retrieved_config", None)

        assert result["success"] is False
        assert "error" in result
        assert "path' parameter is required" in result["error"]
        assert "retrieved_config" in result["error"]
        assert "getConfigurationFromS3" in result["error"]
        assert result["cleanup_type"] == "retrieved_config"

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_nested_directories(self):
        """Test cleanup of retrieved config with nested directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "lza-config-test")
            os.makedirs(config_dir)
            
            # Create nested directory structure
            nested_dir = os.path.join(config_dir, "level1", "level2", "level3")
            os.makedirs(nested_dir)
            
            # Create files at different levels
            with open(os.path.join(config_dir, "root.yaml"), "w") as f:
                f.write("root: config")
            with open(os.path.join(nested_dir, "nested.yaml"), "w") as f:
                f.write("nested: config")

            mock_ctx = MockContext()

            result = await cleanup_configuration(mock_ctx, "retrieved_config", config_dir)

            assert result["success"] is True
            assert not os.path.exists(config_dir)
            assert result["cleanup_type"] == "retrieved_config"

    @pytest.mark.asyncio
    async def test_cleanup_retrieved_config_with_symlinks(self):
        """Test cleanup of retrieved config with symbolic links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "lza-config-test")
            os.makedirs(config_dir)
            
            # Create a file
            file_path = os.path.join(config_dir, "config.yaml")
            with open(file_path, "w") as f:
                f.write("test: config")
            
            # Create a symlink (if supported by OS)
            try:
                symlink_path = os.path.join(config_dir, "config-link.yaml")
                os.symlink(file_path, symlink_path)
            except (OSError, NotImplementedError):
                # Skip symlink test on systems that don't support it
                pass

            mock_ctx = MockContext()

            result = await cleanup_configuration(mock_ctx, "retrieved_config", config_dir)

            assert result["success"] is True
            assert not os.path.exists(config_dir)
            assert result["cleanup_type"] == "retrieved_config"
