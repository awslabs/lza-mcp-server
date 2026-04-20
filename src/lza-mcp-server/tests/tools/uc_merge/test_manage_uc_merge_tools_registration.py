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

"""Unit tests for manage_uc_merge_tools tool registration."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools import (
    register_uc_merge_tools,
)


class TestToolRegistration:
    """Test tool registration functionality."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server instance."""
        mcp = Mock()
        mcp.tool = Mock(side_effect=lambda **kwargs: lambda func: func)
        return mcp

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock WorkspaceManager instance."""
        return Mock()

    def test_register_uc_merge_tools_basic(self, mock_mcp, mock_workspace_manager):
        """Test basic tool registration."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        # Verify tool decorator was called for each tool (6 tools total)
        assert mock_mcp.tool.call_count == 6

    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.logger")
    def test_register_uc_merge_tools_logging(
        self, mock_logger, mock_mcp, mock_workspace_manager
    ):
        """Test that registration logs success message."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        # Verify success logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "UC merge tools registered successfully" in log_message


class TestToolFunctionWrappers:
    """Test the tool function wrappers created during registration."""

    @pytest.fixture
    def mock_workspace_manager(self):
        """Create a mock WorkspaceManager instance."""
        return Mock()

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server that captures registered functions."""
        registered_tools = {}

        def tool_decorator(**kwargs):
            def wrapper(func):
                # Extract function name from the decorated function
                registered_tools[func.__name__] = func
                return func

            return wrapper

        mcp = Mock()
        mcp.tool = tool_decorator
        mcp.registered_tools = registered_tools
        return mcp

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.validate_lza_for_uc_merge"
    )
    async def test_validate_lza_for_uc_merge_wrapper(
        self, mock_validate, mock_mcp, mock_workspace_manager
    ):
        """Test validateLzaForUcMerge wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        validate_func = mock_mcp.registered_tools["validateLzaForUcMerge"]
        mock_validate.return_value = {"success": True, "is_fresh": True}

        mock_ctx = Mock()
        result = await validate_func(
            mock_ctx, workspace_id="abc123abc123", path="config"
        )

        mock_validate.assert_called_once_with(
            mock_ctx, "abc123abc123", "config", mock_workspace_manager
        )
        assert result == {"success": True, "is_fresh": True}

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.tool_get_uc_releases"
    )
    async def test_get_uc_releases_wrapper(
        self, mock_get_releases, mock_mcp, mock_workspace_manager
    ):
        """Test get_uc_releases wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        releases_func = mock_mcp.registered_tools["get_uc_releases"]
        mock_get_releases.return_value = {
            "success": True,
            "releases": ["v1.0.0", "v0.9.0"],
        }

        mock_ctx = Mock()
        result = await releases_func(mock_ctx)

        mock_get_releases.assert_called_once_with(mock_ctx)
        assert result["success"] is True
        assert len(result["releases"]) == 2

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.tool_get_uc_network_models"
    )
    async def test_get_uc_network_models_wrapper(
        self, mock_get_models, mock_mcp, mock_workspace_manager
    ):
        """Test get_uc_network_models wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        models_func = mock_mcp.registered_tools["get_uc_network_models"]
        mock_get_models.return_value = {
            "success": True,
            "models": ["hub-and-spoke", "shared-vpc"],
        }

        mock_ctx = Mock()
        result = await models_func(mock_ctx, "v1.0.0")

        mock_get_models.assert_called_once_with(mock_ctx, "v1.0.0")
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.tool_start_uc_merge_session"
    )
    async def test_start_uc_merge_session_wrapper(
        self, mock_start_session, mock_mcp, mock_workspace_manager
    ):
        """Test start_uc_merge_session wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        session_func = mock_mcp.registered_tools["start_uc_merge_session"]
        mock_start_session.return_value = {
            "success": True,
            "workspace_id": "abcdef123456",
        }

        mock_ctx = Mock()
        result = await session_func(mock_ctx, "v1.0.0", "hub-and-spoke")

        mock_start_session.assert_called_once_with(
            mock_ctx, "v1.0.0", "hub-and-spoke", mock_workspace_manager
        )
        assert result["workspace_id"] == "abcdef123456"

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.get_uc_network_customization_guide"
    )
    async def test_get_uc_network_customization_guide_wrapper(
        self, mock_get_guide, mock_mcp, mock_workspace_manager
    ):
        """Test getUcNetworkCustomizationGuide wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        guide_func = mock_mcp.registered_tools["getUcNetworkCustomizationGuide"]
        mock_get_guide.return_value = {
            "success": True,
            "network_model": "hub-and-spoke",
        }

        mock_ctx = Mock()
        result = await guide_func(mock_ctx, "uc-session-123")

        mock_get_guide.assert_called_once_with("uc-session-123", mock_workspace_manager)
        assert result["network_model"] == "hub-and-spoke"

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.copy_uc_to_lza_config"
    )
    async def test_copy_uc_to_lza_config_wrapper(
        self, mock_copy, mock_mcp, mock_workspace_manager
    ):
        """Test copyUcToLzaConfig wrapper function."""
        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        copy_func = mock_mcp.registered_tools["copyUcToLzaConfig"]
        mock_copy.return_value = {
            "success": True,
            "files_copied": 15,
        }

        mock_ctx = Mock()
        result = await copy_func(mock_ctx, "uc-workspace-123", "lza-workspace-456")

        mock_copy.assert_called_once_with(
            mock_ctx,
            "uc-workspace-123",
            "lza-workspace-456",
            mock_workspace_manager,
            "",
        )
        assert result["files_copied"] == 15


class TestToolRegistrationEdgeCases:
    """Test edge cases in tool registration."""

    def test_register_uc_merge_tools_multiple_times(self):
        """Test registering tools multiple times."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=lambda **kwargs: lambda func: func)
        mock_workspace_manager = Mock()

        register_uc_merge_tools(mock_mcp, mock_workspace_manager)
        first_call_count = mock_mcp.tool.call_count

        register_uc_merge_tools(mock_mcp, mock_workspace_manager)
        second_call_count = mock_mcp.tool.call_count

        # Should register tools both times (6 tools each)
        assert first_call_count == 6
        assert second_call_count == 12

    def test_register_uc_merge_tools_with_none_mcp(self):
        """Test registering tools with None MCP instance."""
        mock_workspace_manager = Mock()
        with pytest.raises(AttributeError):
            register_uc_merge_tools(None, mock_workspace_manager)

    def test_register_uc_merge_tools_preserves_function_names(self):
        """Test that registered functions preserve their names."""
        registered_tools = {}

        def tool_decorator(**kwargs):
            def wrapper(func):
                registered_tools[func.__name__] = func
                return func

            return wrapper

        mock_mcp = Mock()
        mock_mcp.tool = tool_decorator
        mock_workspace_manager = Mock()

        register_uc_merge_tools(mock_mcp, mock_workspace_manager)

        # Verify all expected function names are preserved
        expected_tools = [
            "validateLzaForUcMerge",
            "get_uc_releases",
            "get_uc_network_models",
            "start_uc_merge_session",
            "getUcNetworkCustomizationGuide",
            "copyUcToLzaConfig",
        ]

        for tool_name in expected_tools:
            assert tool_name in registered_tools
            assert callable(registered_tools[tool_name])


class TestToolRegistrationIntegration:
    """Test tool registration integration scenarios."""

    @pytest.fixture
    def mock_mcp_with_tracking(self):
        """Create a mock MCP that tracks all registered tools."""

        class MockMCP:
            def __init__(self):
                self.tools = {}
                self.tool_call_count = 0

            def tool(self, **kwargs):
                self.tool_call_count += 1

                def decorator(func):
                    self.tools[func.__name__] = {
                        "function": func,
                        "name": func.__name__,
                    }
                    return func

                return decorator

        return MockMCP()

    def test_all_tools_registered_correctly(self, mock_mcp_with_tracking):
        """Test that all tools are registered with correct metadata."""
        mock_workspace_manager = Mock()
        register_uc_merge_tools(mock_mcp_with_tracking, mock_workspace_manager)

        # Verify all expected tools are registered
        expected_tools = [
            "validateLzaForUcMerge",
            "get_uc_releases",
            "get_uc_network_models",
            "start_uc_merge_session",
            "getUcNetworkCustomizationGuide",
            "copyUcToLzaConfig",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_with_tracking.tools
            tool_info = mock_mcp_with_tracking.tools[tool_name]
            assert tool_info["name"] == tool_name
            assert callable(tool_info["function"])

    def test_tool_registration_count(self, mock_mcp_with_tracking):
        """Test that correct number of tools are registered."""
        mock_workspace_manager = Mock()
        register_uc_merge_tools(mock_mcp_with_tracking, mock_workspace_manager)

        # Should have exactly 6 tools
        assert len(mock_mcp_with_tracking.tools) == 6
        assert mock_mcp_with_tracking.tool_call_count == 6

    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.logger")
    def test_registration_error_handling(self, mock_logger):
        """Test error handling during registration."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=Exception("Registration failed"))

        # Registration should raise the exception
        with pytest.raises(Exception) as exc_info:
            register_uc_merge_tools(mock_mcp, Mock())

        assert "Registration failed" in str(exc_info.value)
