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
from unittest.mock import patch, mock_open, Mock

from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
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

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock WorkspaceManager that creates workspaces."""
        wm = Mock(spec=WorkspaceManager)
        wm.create_workspace.return_value = "abc123def456"
        wm.list_files.return_value = []
        wm.write_file.return_value = None
        return wm

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_all_configs(
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test getting all minimum configurations."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager
            )

        # Verify result structure
        assert isinstance(result, dict)
        assert "config_files" in result
        assert "instructions_for_assistant" in result
        assert "workspace_id" in result
        assert result["workspace_id"] == "abc123def456"
        assert result["workspace_created"] is True
        assert "files_written" in result

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
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test getting specific configuration type."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager, config_type="accounts"
            )

        # Verify result contains only accounts config
        assert "config_files" in result
        assert "accounts" in result["config_files"]
        assert len(result["config_files"]) == 1
        assert result["workspace_id"] == "abc123def456"
        assert result["workspace_created"] is True
        assert result["files_written"] == ["accounts-config.yaml"]

        # Verify accounts config structure
        accounts_config = result["config_files"]["accounts"]
        assert "mandatoryAccounts" in accounts_config
        assert len(accounts_config["mandatoryAccounts"]) == 3

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_invalid_type(
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test getting invalid configuration type."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager, config_type="invalid_type"
            )

        # Verify error response
        assert "error" in result
        assert "available_types" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_missing_directory(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test behavior when configuration directory is missing."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": "/nonexistent/path"}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager
            )

        # Verify error response
        assert "error" in result
        assert "message" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_with_existing_workspace(
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test writing configs into an existing workspace."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context,
                mock_workspace_manager,
                workspace_id="abc123def456",
            )

        # Verify workspace was reused, not created
        assert result["workspace_id"] == "abc123def456"
        assert result["workspace_created"] is False
        mock_workspace_manager.list_files.assert_called_once_with(
            "abc123def456", mock_mcp_context
        )
        mock_workspace_manager.create_workspace.assert_not_called()

        # Verify files were written
        assert len(result["files_written"]) == 2
        assert mock_workspace_manager.write_file.call_count == 2

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_workspace_not_found(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test error when provided workspace_id does not exist."""
        mock_workspace_manager.list_files.side_effect = WorkspaceNotFoundError(
            "Workspace 'bad123bad456' not found"
        )

        result = await tool_get_minimum_configuration(
            mock_mcp_context,
            mock_workspace_manager,
            workspace_id="bad123bad456",
        )

        assert "error" in result
        assert "not found" in result["error"].lower()
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_file_read_error(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test handling of file read errors."""
        with patch.dict(
            os.environ, {"LZA_MIN_CONFIG_DIR": "/app/lza-minimum-configuration"}
        ):
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    with patch(
                        "builtins.open",
                        side_effect=PermissionError("Access denied"),
                    ):
                        await tool_get_minimum_configuration(
                            mock_mcp_context, mock_workspace_manager
                        )

        # Should handle file read errors gracefully
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_yaml_parse_error(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test handling of YAML parsing errors."""
        with patch.dict(
            os.environ, {"LZA_MIN_CONFIG_DIR": "/app/lza-minimum-configuration"}
        ):
            with patch("os.path.isdir", return_value=True):
                with patch("os.path.isfile", return_value=True):
                    with patch(
                        "builtins.open",
                        mock_open(read_data="invalid: yaml: [unclosed"),
                    ):
                        await tool_get_minimum_configuration(
                            mock_mcp_context, mock_workspace_manager
                        )

        # Should handle YAML parsing errors gracefully
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_no_configs_found(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test behavior when no configuration files are found."""
        empty_dir = tempfile.mkdtemp()

        try:
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": empty_dir}):
                result = await tool_get_minimum_configuration(
                    mock_mcp_context, mock_workspace_manager
                )

            # Verify error response for no configs
            assert "error" in result
            assert "message" in result
            assert len(mock_mcp_context.error_messages) > 0

        finally:
            shutil.rmtree(empty_dir)

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_default_env_path(
        self, mock_mcp_context, mock_workspace_manager
    ):
        """Test using default environment path."""
        # Don't set LZA_MIN_CONFIG_DIR to test default
        with patch("os.path.isdir", return_value=False):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager
            )

        # Should use default path and handle missing directory
        assert "error" in result
        assert len(mock_mcp_context.error_messages) > 0

        # Verify the error message mentions the default path
        error_message = mock_mcp_context.error_messages[0]
        assert "/app/lza-minimum-configuration" in error_message

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_instructions_structure(
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test the structure of instructions for assistant."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            result = await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager
            )

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
    async def test_get_minimum_configuration_writes_to_workspace(
        self, mock_mcp_context, temp_config_dir, mock_workspace_manager
    ):
        """Test that config files are written to the workspace."""
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
            await tool_get_minimum_configuration(
                mock_mcp_context, mock_workspace_manager
            )

        # Verify write_file was called for each config
        assert mock_workspace_manager.write_file.call_count == 2
        written_files = [
            call.args[1] for call in mock_workspace_manager.write_file.call_args_list
        ]
        assert "accounts-config.yaml" in written_files
        assert "global-config.yaml" in written_files

        # Verify content is YAML bytes
        for call in mock_workspace_manager.write_file.call_args_list:
            content = call.args[2]
            assert isinstance(content, bytes)
            parsed = yaml.safe_load(content.decode())
            assert isinstance(parsed, dict)
