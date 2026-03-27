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

    def test_register_uc_merge_tools_basic(self, mock_mcp):
        """Test basic tool registration."""
        register_uc_merge_tools(mock_mcp)

        # Verify tool decorator was called for each tool (8 tools total)
        assert mock_mcp.tool.call_count == 8

    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.logger")
    def test_register_uc_merge_tools_logging(self, mock_logger, mock_mcp):
        """Test that registration logs success message."""
        register_uc_merge_tools(mock_mcp)

        # Verify success logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "UC merge tools registered successfully" in log_message


class TestToolFunctionWrappers:
    """Test the tool function wrappers created during registration."""

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
    async def test_validate_lza_for_uc_merge_wrapper(self, mock_validate, mock_mcp):
        """Test validateLzaForUcMerge wrapper function."""
        register_uc_merge_tools(mock_mcp)

        validate_func = mock_mcp.registered_tools["validateLzaForUcMerge"]
        mock_validate.return_value = {"success": True, "is_fresh": True}

        mock_ctx = Mock()
        result = await validate_func(mock_ctx)

        mock_validate.assert_called_once_with(mock_ctx)
        assert result == {"success": True, "is_fresh": True}

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.tool_get_uc_releases"
    )
    async def test_get_uc_releases_wrapper(self, mock_get_releases, mock_mcp):
        """Test get_uc_releases wrapper function."""
        register_uc_merge_tools(mock_mcp)

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
    async def test_get_uc_network_models_wrapper(self, mock_get_models, mock_mcp):
        """Test get_uc_network_models wrapper function."""
        register_uc_merge_tools(mock_mcp)

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
    async def test_start_uc_merge_session_wrapper(self, mock_start_session, mock_mcp):
        """Test start_uc_merge_session wrapper function."""
        register_uc_merge_tools(mock_mcp)

        session_func = mock_mcp.registered_tools["start_uc_merge_session"]
        mock_start_session.return_value = {
            "success": True,
            "session_id": "uc-session-123",
        }

        mock_ctx = Mock()
        result = await session_func(mock_ctx, "v1.0.0", "hub-and-spoke")

        mock_start_session.assert_called_once_with(mock_ctx, "v1.0.0", "hub-and-spoke")
        assert result["session_id"] == "uc-session-123"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.read_uc_file")
    async def test_read_uc_file_wrapper(self, mock_read_uc, mock_mcp):
        """Test readUcFile wrapper function."""
        register_uc_merge_tools(mock_mcp)

        read_func = mock_mcp.registered_tools["readUcFile"]
        mock_read_uc.return_value = {
            "success": True,
            "content": "replacements: {}",
        }

        mock_ctx = Mock()
        result = await read_func(mock_ctx, "uc-session-123", "replacements-config.yaml")

        mock_read_uc.assert_called_once_with(
            mock_ctx, "uc-session-123", "replacements-config.yaml"
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.get_uc_network_customization_guide"
    )
    async def test_get_uc_network_customization_guide_wrapper(
        self, mock_get_guide, mock_mcp
    ):
        """Test getUcNetworkCustomizationGuide wrapper function."""
        register_uc_merge_tools(mock_mcp)

        guide_func = mock_mcp.registered_tools["getUcNetworkCustomizationGuide"]
        mock_get_guide.return_value = {
            "success": True,
            "network_model": "hub-and-spoke",
        }

        mock_ctx = Mock()
        result = await guide_func(mock_ctx, "uc-session-123")

        mock_get_guide.assert_called_once_with("uc-session-123")
        assert result["network_model"] == "hub-and-spoke"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.update_uc_file")
    async def test_update_uc_file_wrapper(self, mock_update, mock_mcp):
        """Test updateUcFile wrapper function."""
        register_uc_merge_tools(mock_mcp)

        update_func = mock_mcp.registered_tools["updateUcFile"]
        mock_update.return_value = {
            "success": True,
            "updates_applied": {"HomeRegionIngressCidr": "10.0.0.0/16"},
        }

        mock_ctx = Mock()
        updates = {"HomeRegionIngressCidr": "10.0.0.0/16"}
        result = await update_func(
            mock_ctx, "uc-session-123", "replacements-config.yaml", updates
        )

        mock_update.assert_called_once_with(
            "uc-session-123", "replacements-config.yaml", updates
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.copy_uc_to_lza_config"
    )
    async def test_copy_uc_to_lza_config_wrapper(self, mock_copy, mock_mcp):
        """Test copyUcToLzaConfig wrapper function."""
        register_uc_merge_tools(mock_mcp)

        copy_func = mock_mcp.registered_tools["copyUcToLzaConfig"]
        mock_copy.return_value = {
            "success": True,
            "files_copied": 15,
        }

        mock_ctx = Mock()
        result = await copy_func(mock_ctx, "uc-session-123")

        mock_copy.assert_called_once_with(mock_ctx, "uc-session-123")
        assert result["files_copied"] == 15


class TestToolRegistrationEdgeCases:
    """Test edge cases in tool registration."""

    def test_register_uc_merge_tools_multiple_times(self):
        """Test registering tools multiple times."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=lambda **kwargs: lambda func: func)

        register_uc_merge_tools(mock_mcp)
        first_call_count = mock_mcp.tool.call_count

        register_uc_merge_tools(mock_mcp)
        second_call_count = mock_mcp.tool.call_count

        # Should register tools both times (8 tools each)
        assert first_call_count == 8
        assert second_call_count == 16

    def test_register_uc_merge_tools_with_none_mcp(self):
        """Test registering tools with None MCP instance."""
        with pytest.raises(AttributeError):
            register_uc_merge_tools(None)

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

        register_uc_merge_tools(mock_mcp)

        # Verify all expected function names are preserved
        expected_tools = [
            "validateLzaForUcMerge",
            "get_uc_releases",
            "get_uc_network_models",
            "start_uc_merge_session",
            "readUcFile",
            "getUcNetworkCustomizationGuide",
            "updateUcFile",
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
        register_uc_merge_tools(mock_mcp_with_tracking)

        # Verify all expected tools are registered
        expected_tools = [
            "validateLzaForUcMerge",
            "get_uc_releases",
            "get_uc_network_models",
            "start_uc_merge_session",
            "readUcFile",
            "getUcNetworkCustomizationGuide",
            "updateUcFile",
            "copyUcToLzaConfig",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_with_tracking.tools
            tool_info = mock_mcp_with_tracking.tools[tool_name]
            assert tool_info["name"] == tool_name
            assert callable(tool_info["function"])

    def test_tool_registration_count(self, mock_mcp_with_tracking):
        """Test that correct number of tools are registered."""
        register_uc_merge_tools(mock_mcp_with_tracking)

        # Should have exactly 8 tools
        assert len(mock_mcp_with_tracking.tools) == 8
        assert mock_mcp_with_tracking.tool_call_count == 8

    @patch("awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools.logger")
    def test_registration_error_handling(self, mock_logger):
        """Test error handling during registration."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=Exception("Registration failed"))

        # Registration should raise the exception
        with pytest.raises(Exception) as exc_info:
            register_uc_merge_tools(mock_mcp)

        assert "Registration failed" in str(exc_info.value)
