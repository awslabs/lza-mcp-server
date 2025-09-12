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

"""Unit tests for get_minimum_configuration module."""

import pytest
import os
import yaml
import tempfile
import shutil
from unittest.mock import patch, mock_open

from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
)


class TestGetMinimumConfiguration:
    """Test cases for tool_get_minimum_configuration function."""

    @pytest.fixture
    def sample_config_data(self):
        """Sample configuration data for testing."""
        return {
            "accounts": {
                "mandatoryAccounts": [
                    {
                        "name": "Management",
                        "description": "Management account",
                        "email": "management-account@example.com",
                        "organizationalUnit": "Root",
                        "warm": False,
                    },
                    {
                        "name": "LogArchive",
                        "description": "Log Archive account",
                        "email": "log-archive@example.com",
                        "organizationalUnit": "Security",
                        "warm": False,
                    },
                    {
                        "name": "Audit",
                        "description": "Audit account",
                        "email": "audit@example.com",
                        "organizationalUnit": "Security",
                        "warm": False,
                    },
                ],
                "workloadAccounts": [],
            },
            "global": {
                "homeRegion": "us-east-1",
                "enabledRegions": ["us-east-1"],
                "managementAccountAccessRole": "AWSControlTowerExecution",
                "terminationProtection": True,
            },
        }

    @pytest.fixture
    def temp_config_dir(self, sample_config_data):
        """Create temporary directory with sample config files."""
        temp_dir = tempfile.mkdtemp()

        # Create config files
        for config_type, content in sample_config_data.items():
            file_path = os.path.join(temp_dir, f"{config_type}-config.yaml")
            with open(file_path, "w") as f:
                yaml.dump(content, f, default_flow_style=False)

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_all_configs(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test getting all minimum configurations."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(mock_mcp_context)

        # Verify result structure
        assert isinstance(result, dict)
        assert "config_files" in result
        assert "instructions_for_assistant" in result

        # Verify config files are present
        config_files = result["config_files"]
        assert "accounts" in config_files
        assert "global" in config_files

        # Verify instructions
        instructions = result["instructions_for_assistant"]
        assert "message" in instructions
        assert "critical_customizations" in instructions
        assert isinstance(instructions["critical_customizations"], list)

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_specific_type(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test getting specific configuration type."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, config_type="accounts"
            )

        # Verify result contains only accounts config
        assert "config_files" in result
        assert "accounts" in result["config_files"]
        assert len(result["config_files"]) == 1

        # Verify accounts config structure
        accounts_config = result["config_files"]["accounts"]
        assert "mandatoryAccounts" in accounts_config
        assert len(accounts_config["mandatoryAccounts"]) == 3

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_invalid_type(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test getting invalid configuration type."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, config_type="invalid_type"
            )

        # Verify error response
        assert "error" in result
        assert "available_types" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_missing_directory(self, mock_mcp_context):
        """Test behavior when configuration directory is missing."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": "/nonexistent/path"}):
            result = await tool_get_minimum_configuration(mock_mcp_context)

        # Verify error response
        assert "error" in result
        assert "message" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_save_to_directory(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test saving configurations to specified directory."""
        save_dir = tempfile.mkdtemp()

        try:
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
                result = await tool_get_minimum_configuration(
                    mock_mcp_context, save_to_directory=save_dir
                )

            # Verify save operation
            assert "saved_to_directory" in result
            assert "saved_files" in result
            assert result["saved_to_directory"] == save_dir

            # Verify files were actually saved
            saved_files = result["saved_files"]
            for file_path in saved_files:
                assert os.path.exists(file_path)

        finally:
            shutil.rmtree(save_dir)

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_save_error(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test error handling during save operation."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            with patch("os.makedirs", side_effect=OSError("Permission denied")):
                result = await tool_get_minimum_configuration(
                    mock_mcp_context, save_to_directory="/invalid/path"
                )

        # Verify error handling
        assert "error" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_file_read_error(self, mock_mcp_context):
        """Test handling of file read errors."""
        with patch.dict(
            os.environ, {"LZA_MIN_CONFIG_DIR": "/app/lza-minimum-configuration"}
        ):
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    with patch(
                        "builtins.open", side_effect=PermissionError("Access denied")
                    ):
                        await tool_get_minimum_configuration(mock_mcp_context)

        # Should handle file read errors gracefully
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_yaml_parse_error(self, mock_mcp_context):
        """Test handling of YAML parsing errors."""
        with patch.dict(
            os.environ, {"LZA_MIN_CONFIG_DIR": "/app/lza-minimum-configuration"}
        ):
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    with patch(
                        "builtins.open", mock_open(read_data="invalid: yaml: [unclosed")
                    ):
                        await tool_get_minimum_configuration(mock_mcp_context)

        # Should handle YAML parsing errors gracefully
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_no_configs_found(self, mock_mcp_context):
        """Test behavior when no configuration files are found."""
        empty_dir = tempfile.mkdtemp()

        try:
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": empty_dir}):
                result = await tool_get_minimum_configuration(mock_mcp_context)

            # Verify error response for no configs
            assert "error" in result
            assert "message" in result
            assert len(mock_mcp_context.error_messages) > 0

        finally:
            shutil.rmtree(empty_dir)

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_default_env_path(self, mock_mcp_context):
        """Test using default environment path."""
        # Don't set LZA_MIN_CONFIG_DIR to test default
        with patch("os.path.isdir", return_value=False):
            result = await tool_get_minimum_configuration(mock_mcp_context)

        # Should use default path and handle missing directory
        assert "error" in result
        assert len(mock_mcp_context.error_messages) > 0

        # Verify the error message mentions the default path
        error_message = mock_mcp_context.error_messages[0]
        assert "/app/lza-minimum-configuration" in error_message

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_instructions_structure(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test the structure of instructions for assistant."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(mock_mcp_context)

        instructions = result["instructions_for_assistant"]

        # Verify all required instruction fields are present
        required_fields = [
            "message",
            "file_naming",
            "required_action",
            "critical_customizations",
            "user_guidance",
            "explain_to_user",
        ]

        for field in required_fields:
            assert field in instructions

        # Verify critical customizations is a list with expected content
        customizations = instructions["critical_customizations"]
        assert isinstance(customizations, list)
        assert len(customizations) >= 4

        # Check for key customization points
        customization_text = " ".join(customizations)
        assert "email addresses" in customization_text.lower()
        assert "region" in customization_text.lower()

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_save_updates_instructions(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test that saving files updates the instructions."""
        save_dir = tempfile.mkdtemp()

        try:
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
                result = await tool_get_minimum_configuration(
                    mock_mcp_context, save_to_directory=save_dir
                )

            instructions = result["instructions_for_assistant"]

            # Verify instructions are updated for saved files
            assert "files_saved" in instructions
            assert instructions["files_saved"] is True
            assert save_dir in instructions["message"]

        finally:
            shutil.rmtree(save_dir)
