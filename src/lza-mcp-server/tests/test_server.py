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

"""Unit tests for main server module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.server import (
    create_mcp_server,
    main,
    runserver,
)


class TestCreateMcpServer:
    """Test MCP server creation."""

    @patch("awslabs.lza_mcp_server.server.FastMCP")
    @patch("awslabs.lza_mcp_server.server.build_instructions")
    def test_creates_server_with_instructions(
        self, mock_build_instructions, mock_fastmcp
    ):
        """Test creates server with built instructions."""
        mock_build_instructions.return_value = "Test instructions"
        mock_server = Mock()
        mock_fastmcp.return_value = mock_server

        result = create_mcp_server()

        mock_build_instructions.assert_called_once()
        mock_fastmcp.assert_called_once_with(
            "awslabs.lza-mcp-server",
            instructions="Test instructions",
            dependencies=["pydantic", "PyYAML", "boto3"],
        )
        assert result == mock_server

    @patch("awslabs.lza_mcp_server.server.FastMCP")
    @patch("awslabs.lza_mcp_server.server.build_instructions")
    def test_uses_correct_server_name(self, mock_build_instructions, mock_fastmcp):
        """Test uses correct server name."""
        mock_build_instructions.return_value = "Instructions"

        create_mcp_server()

        call_args = mock_fastmcp.call_args
        assert call_args[0][0] == "awslabs.lza-mcp-server"

    @patch("awslabs.lza_mcp_server.server.FastMCP")
    @patch("awslabs.lza_mcp_server.server.build_instructions")
    def test_includes_required_dependencies(
        self, mock_build_instructions, mock_fastmcp
    ):
        """Test includes all required dependencies."""
        mock_build_instructions.return_value = "Instructions"

        create_mcp_server()

        call_args = mock_fastmcp.call_args
        dependencies = call_args[1]["dependencies"]
        assert "pydantic" in dependencies
        assert "PyYAML" in dependencies
        assert "boto3" in dependencies


class TestMain:
    """Test main server entry point."""

    @patch("awslabs.lza_mcp_server.server.register_all_components")
    @patch("awslabs.lza_mcp_server.server.is_uc_merge_enabled")
    @patch("awslabs.lza_mcp_server.server.create_mcp_server")
    @patch("awslabs.lza_mcp_server.server.validate_schema_integrity")
    @patch("awslabs.lza_mcp_server.server.get_schema_directory")
    @patch("awslabs.lza_mcp_server.server.configure_logging")
    @patch("awslabs.lza_mcp_server.server.logger")
    def test_main_success_flow(
        self,
        mock_logger,
        mock_configure_logging,
        mock_get_schema_dir,
        mock_validate_schema,
        mock_create_server,
        mock_is_uc_enabled,
        mock_register_components,
    ):
        """Test successful main execution flow."""
        mock_schema_dir = Path("/test/schemas")
        mock_get_schema_dir.return_value = mock_schema_dir
        mock_is_uc_enabled.return_value = False
        mock_server = Mock()
        mock_create_server.return_value = mock_server

        main()

        # Verify execution order
        mock_configure_logging.assert_called_once()
        mock_logger.info.assert_any_call("Starting LZA MCP Server")
        mock_get_schema_dir.assert_called_once()
        mock_validate_schema.assert_called_once_with(
            schema_dir=mock_schema_dir, fail_on_error=True
        )
        mock_create_server.assert_called_once()
        mock_is_uc_enabled.assert_called_once()
        mock_register_components.assert_called_once_with(mock_server, False)
        mock_server.run.assert_called_once()

    @patch("awslabs.lza_mcp_server.server.register_all_components")
    @patch("awslabs.lza_mcp_server.server.is_uc_merge_enabled")
    @patch("awslabs.lza_mcp_server.server.create_mcp_server")
    @patch("awslabs.lza_mcp_server.server.validate_schema_integrity")
    @patch("awslabs.lza_mcp_server.server.get_schema_directory")
    @patch("awslabs.lza_mcp_server.server.configure_logging")
    def test_main_with_uc_merge_enabled(
        self,
        mock_configure_logging,
        mock_get_schema_dir,
        mock_validate_schema,
        mock_create_server,
        mock_is_uc_enabled,
        mock_register_components,
    ):
        """Test main with UC Merge enabled."""
        mock_get_schema_dir.return_value = Path("/test/schemas")
        mock_is_uc_enabled.return_value = True
        mock_server = Mock()
        mock_create_server.return_value = mock_server

        main()

        mock_register_components.assert_called_once_with(mock_server, True)

    @patch("awslabs.lza_mcp_server.server.logger")
    @patch("awslabs.lza_mcp_server.server.validate_schema_integrity")
    @patch("awslabs.lza_mcp_server.server.get_schema_directory")
    @patch("awslabs.lza_mcp_server.server.configure_logging")
    def test_main_handles_import_error(
        self,
        mock_configure_logging,
        mock_get_schema_dir,
        mock_validate_schema,
        mock_logger,
    ):
        """Test main handles ImportError from schema validation."""
        mock_get_schema_dir.return_value = Path("/test/schemas")
        mock_validate_schema.side_effect = ImportError("Module not found")

        # Mock the server creation and registration to prevent actual server run
        with patch(
            "awslabs.lza_mcp_server.server.create_mcp_server"
        ) as mock_create_server:
            with patch(
                "awslabs.lza_mcp_server.server.is_uc_merge_enabled"
            ) as mock_is_uc_enabled:
                with patch("awslabs.lza_mcp_server.server.register_all_components"):
                    mock_server = Mock()
                    mock_create_server.return_value = mock_server
                    mock_is_uc_enabled.return_value = False

                    # Should log warning but not raise
                    main()

        mock_logger.warning.assert_called_once_with(
            "Schema integrity validation module not available"
        )

    @patch("awslabs.lza_mcp_server.server.logger")
    @patch("awslabs.lza_mcp_server.server.validate_schema_integrity")
    @patch("awslabs.lza_mcp_server.server.get_schema_directory")
    @patch("awslabs.lza_mcp_server.server.configure_logging")
    def test_main_raises_on_validation_error(
        self,
        mock_configure_logging,
        mock_get_schema_dir,
        mock_validate_schema,
        mock_logger,
    ):
        """Test main raises exception on schema validation error."""
        mock_get_schema_dir.return_value = Path("/test/schemas")
        mock_validate_schema.side_effect = ValueError("Checksum mismatch")

        with pytest.raises(ValueError, match="Checksum mismatch"):
            main()

        mock_logger.error.assert_called_once()
        assert "Schema integrity validation failed" in str(mock_logger.error.call_args)

    @patch("awslabs.lza_mcp_server.server.register_all_components")
    @patch("awslabs.lza_mcp_server.server.is_uc_merge_enabled")
    @patch("awslabs.lza_mcp_server.server.create_mcp_server")
    @patch("awslabs.lza_mcp_server.server.validate_schema_integrity")
    @patch("awslabs.lza_mcp_server.server.get_schema_directory")
    @patch("awslabs.lza_mcp_server.server.configure_logging")
    def test_main_execution_order(
        self,
        mock_configure_logging,
        mock_get_schema_dir,
        mock_validate_schema,
        mock_create_server,
        mock_is_uc_enabled,
        mock_register_components,
    ):
        """Test main executes steps in correct order."""
        call_order = []

        mock_configure_logging.side_effect = lambda *args, **kwargs: call_order.append(
            "configure_logging"
        )
        mock_get_schema_dir.side_effect = lambda: (
            call_order.append("get_schema_dir"),
            Path("/test"),
        )[1]
        mock_validate_schema.side_effect = lambda *args, **kwargs: call_order.append(
            "validate_schema"
        )
        mock_create_server.side_effect = lambda: (
            call_order.append("create_server"),
            Mock(),
        )[1]
        mock_is_uc_enabled.side_effect = lambda: (
            call_order.append("is_uc_enabled"),
            False,
        )[1]
        mock_register_components.side_effect = lambda *args, **kwargs: (
            call_order.append("register_components")
        )

        main()

        expected_order = [
            "configure_logging",
            "get_schema_dir",
            "validate_schema",
            "create_server",
            "is_uc_enabled",
            "register_components",
        ]
        assert call_order == expected_order


class TestRunserver:
    """Test runserver entry point."""

    @patch("awslabs.lza_mcp_server.server.main")
    def test_runserver_calls_main(self, mock_main):
        """Test runserver calls main function."""
        runserver()

        mock_main.assert_called_once()

    @patch("awslabs.lza_mcp_server.server.main")
    def test_runserver_propagates_exception(self, mock_main):
        """Test runserver propagates exceptions from main."""
        mock_main.side_effect = RuntimeError("Server error")

        with pytest.raises(RuntimeError, match="Server error"):
            runserver()
