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

"""Unit tests for ConfigurationManager configuration validation."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from awslabs.lza_mcp_server.orchestration.core.configuration_manager import (
    ConfigurationManager,
)
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError


class TestValidateConfigurationPath:
    """Test configuration path validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_configuration(self):
        """Test validation of valid LZA configuration."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "accounts-config.yaml").write_text("test")
            (config_dir / "organization-config.yaml").write_text("test")

            # Act
            result = await manager.validate_configuration_path(str(config_dir))

            # Assert
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_nonexistent_path(self):
        """Test validation of nonexistent path."""
        # Arrange
        manager = ConfigurationManager()
        config_path = "/nonexistent/path"

        # Act & Assert
        with pytest.raises(S3UploadError) as exc_info:
            await manager.validate_configuration_path(config_path)
        
        assert exc_info.value.error_code == "CONFIG_PATH_NOT_FOUND"
        assert "does not exist" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_path_is_file(self):
        """Test validation when path is a file, not directory."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            config_path = temp_file.name

        try:
            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(config_path)
            
            assert exc_info.value.error_code == "CONFIG_PATH_NOT_DIRECTORY"
            assert "not a directory" in exc_info.value.message
        finally:
            import os
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_validate_missing_accounts_config(self):
        """Test validation with missing accounts-config.yaml."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            # Only create organization-config.yaml
            (config_dir / "organization-config.yaml").write_text("test")

            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(str(config_dir))
            
            assert exc_info.value.error_code == "CONFIG_FILES_MISSING"
            assert "accounts-config.yaml" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_missing_organization_config(self):
        """Test validation with missing organization-config.yaml."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            # Only create accounts-config.yaml
            (config_dir / "accounts-config.yaml").write_text("test")

            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(str(config_dir))
            
            assert exc_info.value.error_code == "CONFIG_FILES_MISSING"
            assert "organization-config.yaml" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_missing_both_required_files(self):
        """Test validation with both required files missing."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            # Create some other files
            (config_dir / "other-file.yaml").write_text("test")

            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(str(config_dir))
            
            assert exc_info.value.error_code == "CONFIG_FILES_MISSING"
            assert "accounts-config.yaml" in exc_info.value.message
            assert "organization-config.yaml" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_with_extra_files(self):
        """Test validation succeeds with extra files present."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "accounts-config.yaml").write_text("test")
            (config_dir / "organization-config.yaml").write_text("test")
            (config_dir / "extra-file.yaml").write_text("extra")
            (config_dir / "README.md").write_text("readme")

            # Act
            result = await manager.validate_configuration_path(str(config_dir))

            # Assert
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_error_includes_context(self):
        """Test validation error includes context information."""
        # Arrange
        manager = ConfigurationManager()
        config_path = "/nonexistent/path"

        # Act & Assert
        with pytest.raises(S3UploadError) as exc_info:
            await manager.validate_configuration_path(config_path)
        
        error = exc_info.value
        assert error.context is not None
        assert error.context["config_path"] == config_path
        assert error.context["operation"] == "configuration_validation"

    @pytest.mark.asyncio
    async def test_validate_error_includes_troubleshooting(self):
        """Test validation error includes troubleshooting steps."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()

            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(str(config_dir))
            
            error = exc_info.value
            assert error.troubleshooting is not None
            assert len(error.troubleshooting) > 0

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_validate_handles_unexpected_error(self, mock_exists):
        """Test validation handles unexpected errors."""
        # Arrange
        manager = ConfigurationManager()
        config_path = "/some/path"
        mock_exists.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(S3UploadError) as exc_info:
            await manager.validate_configuration_path(config_path)
        
        error = exc_info.value
        assert "Unexpected error validating configuration" in error.message

    @pytest.mark.asyncio
    async def test_validate_case_sensitive_filenames(self):
        """Test validation is case-sensitive for filenames."""
        # Arrange
        manager = ConfigurationManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            # Create files with wrong case
            (config_dir / "Accounts-Config.yaml").write_text("test")
            (config_dir / "Organization-Config.yaml").write_text("test")

            # Act & Assert
            with pytest.raises(S3UploadError) as exc_info:
                await manager.validate_configuration_path(str(config_dir))
            
            assert exc_info.value.error_code == "CONFIG_FILES_MISSING"
