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

"""Unit tests for manage_config_tools module."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
    register_config_tools,
)


def _make_mock_server():
    server = Mock()
    registered_tools = {}

    def mock_tool_decorator(name=None, description=None):
        def decorator(func):
            registered_tools[name] = {
                "name": name,
                "description": description,
                "function": func,
            }
            return func

        return decorator

    server.tool = mock_tool_decorator
    server.get_registered_tools = lambda: registered_tools
    return server


class TestRegisterConfigTools:
    @pytest.fixture
    def mock_mcp_server(self):
        return _make_mock_server()

    def test_register_config_tools_success(self, mock_mcp_server):
        register_config_tools(mock_mcp_server)
        tools = mock_mcp_server.get_registered_tools()

        assert "getMinimumConfiguration" in tools
        assert "getLzaConfiguration" in tools
        assert "putLzaConfiguration" in tools

        assert (
            "minimal LZA configuration"
            in tools["getMinimumConfiguration"]["description"]
        )
        assert "qualifier" in tools["getLzaConfiguration"]["description"].lower()
        assert "qualifier" in tools["putLzaConfiguration"]["description"].lower()

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_wrapper(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)
        func = mock_mcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"config_files": {}}
            result = await func(mock_mcp_context)
            mock_tool.assert_called_once_with(mock_mcp_context, None, None)
            assert result == {"config_files": {}}

    @pytest.mark.asyncio
    async def test_get_minimum_configuration_with_params(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)
        func = mock_mcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"config_files": {"accounts": {}}}
            await func(mock_mcp_context, "accounts", "/save/path")
            mock_tool.assert_called_once_with(
                mock_mcp_context, "accounts", "/save/path"
            )

    @pytest.mark.asyncio
    async def test_get_lza_configuration_wrapper(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.LzaConfigRetrieval"
        ) as mock_cls:
            mock_instance = Mock()
            mock_instance.get_configuration = AsyncMock(
                return_value={"success": True, "file_count": 7}
            )
            mock_cls.return_value = mock_instance

            # Re-register so the patched class is used
            register_config_tools(mock_mcp_server)
            func = mock_mcp_server.get_registered_tools()["getLzaConfiguration"][
                "function"
            ]

            result = await func(mock_mcp_context, "container-dev-1", "my-bucket")
            mock_instance.get_configuration.assert_called_once_with(
                mock_mcp_context, "container-dev-1", "my-bucket"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_lza_configuration_default_params(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.LzaConfigRetrieval"
        ) as mock_cls:
            mock_instance = Mock()
            mock_instance.get_configuration = AsyncMock(return_value={"success": True})
            mock_cls.return_value = mock_instance

            register_config_tools(mock_mcp_server)
            func = mock_mcp_server.get_registered_tools()["getLzaConfiguration"][
                "function"
            ]

            result = await func(mock_mcp_context)
            mock_instance.get_configuration.assert_called_once_with(
                mock_mcp_context, None, None
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_put_lza_configuration_wrapper(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)
        func = mock_mcp_server.get_registered_tools()["putLzaConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_put_lza_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"success": True}
            result = await func(
                mock_mcp_context, "container-dev-1", "./config", "my-bucket", False
            )
            mock_tool.assert_called_once_with(
                mock_mcp_context, "container-dev-1", "./config", "my-bucket", False
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_put_lza_configuration_default_params(
        self, mock_mcp_server, mock_mcp_context
    ):
        register_config_tools(mock_mcp_server)
        func = mock_mcp_server.get_registered_tools()["putLzaConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_put_lza_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"success": True}
            await func(mock_mcp_context)
            mock_tool.assert_called_once_with(mock_mcp_context, None, None, None, True)
