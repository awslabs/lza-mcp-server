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

"""Tests for MCP-specific functionality in config tools."""

import inspect
import json
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
    register_config_tools,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestMCPToolRegistration:
    @pytest.fixture
    def mock_fastmcp_server(self):
        return _make_mock_server()

    def test_config_tools_registration_with_fastmcp(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        assert len(registered_tools) == 6
        assert "getMinimumConfiguration" in registered_tools
        assert "getLzaConfiguration" in registered_tools
        assert "putLzaConfiguration" in registered_tools
        assert "readLzaConfigFile" in registered_tools
        assert "updateLzaConfigFile" in registered_tools
        assert "createLzaConfigFile" in registered_tools

        get_min = registered_tools["getMinimumConfiguration"]
        assert callable(get_min["function"])
        assert "minimal LZA configuration" in get_min["description"]

        get_lza = registered_tools["getLzaConfiguration"]
        assert callable(get_lza["function"])
        assert "qualifier" in get_lza["description"].lower()

        put_lza = registered_tools["putLzaConfiguration"]
        assert callable(put_lza["function"])
        assert "qualifier" in put_lza["description"].lower()

    @pytest.mark.asyncio
    async def test_mcp_context_integration(self, mock_fastmcp_server, mock_mcp_context):
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()
        func = registered_tools["getMinimumConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "config_files": {"accounts": {}},
                "instructions_for_assistant": {"message": "Test"},
            }
            result = await func(mock_mcp_context)
            mock_tool.assert_called_once()
            assert call_args_ctx(mock_tool) == mock_mcp_context
            assert "config_files" in result

    @pytest.mark.asyncio
    async def test_mcp_context_logging(self, mock_fastmcp_server, mock_mcp_context):
        register_config_tools(mock_fastmcp_server)
        func = mock_fastmcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:

            async def side_effect(ctx, *a, **kw):
                await ctx.info("Test info message")
                await ctx.error("Test error message")
                return {"config_files": {}}

            mock_tool.side_effect = side_effect

            await func(mock_mcp_context)
            assert "Test info message" in mock_mcp_context.info_messages
            assert "Test error message" in mock_mcp_context.error_messages

    @pytest.mark.asyncio
    async def test_concurrent_mcp_tool_execution(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()
        get_min_func = tools["getMinimumConfiguration"]["function"]
        put_func = tools["putLzaConfiguration"]["function"]

        contexts = [Mock(info=AsyncMock(), error=AsyncMock()) for _ in range(3)]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_get:
            with patch(
                "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_put_lza_configuration"
            ) as mock_put:
                mock_get.return_value = {"config_files": {}}
                mock_put.return_value = {"success": True}

                results = await asyncio.gather(
                    get_min_func(contexts[0]),
                    put_func(contexts[1]),
                    get_min_func(contexts[2]),
                )
                assert len(results) == 3
                assert mock_get.call_count == 2
                assert mock_put.call_count == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestMCPErrorHandling:
    @pytest.fixture
    def mock_fastmcp_server(self):
        return _make_mock_server()

    @pytest.mark.asyncio
    async def test_mcp_context_error_propagation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        func = mock_fastmcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.side_effect = Exception("Test exception")
            with pytest.raises(Exception):
                await func(mock_mcp_context)

    @pytest.mark.asyncio
    async def test_mcp_context_error_logging(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        func = mock_fastmcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"error": "Not found", "message": "Check path"}
            result = await func(mock_mcp_context)
            assert result["error"] == "Not found"

    @pytest.mark.asyncio
    async def test_mcp_tool_parameter_validation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()
        get_min_func = tools["getMinimumConfiguration"]["function"]
        put_func = tools["putLzaConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_get:
            with patch(
                "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_put_lza_configuration"
            ) as mock_put:
                mock_get.return_value = {"config_files": {}}
                mock_put.return_value = {"success": True}

                await get_min_func(mock_mcp_context)
                await get_min_func(mock_mcp_context, "accounts")
                await get_min_func(mock_mcp_context, "accounts", "/save/path")
                assert mock_get.call_count == 3

                await put_func(mock_mcp_context)
                await put_func(mock_mcp_context, "my-qualifier")
                await put_func(mock_mcp_context, None, "./config")
                assert mock_put.call_count == 3


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMCPToolMetadata:
    @pytest.fixture
    def mock_fastmcp_server(self):
        return _make_mock_server()

    def test_tool_descriptions_are_comprehensive(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()

        get_min = tools["getMinimumConfiguration"]
        assert "minimal" in get_min["description"].lower()
        assert "lza" in get_min["description"].lower()

        put_lza = tools["putLzaConfiguration"]
        assert "upload" in put_lza["description"].lower()
        assert "lza" in put_lza["description"].lower()
        assert "s3" in put_lza["description"].lower()

    def test_tool_names_follow_convention(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        for name in mock_fastmcp_server.get_registered_tools():
            assert name[0].islower()
            assert "_" not in name
            assert "-" not in name

    @pytest.mark.asyncio
    async def test_tool_function_signatures(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()

        # getMinimumConfiguration
        sig = inspect.signature(tools["getMinimumConfiguration"]["function"])
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"
        assert "config_type" in params
        assert "save_to_directory" in params

        # putLzaConfiguration
        sig = inspect.signature(tools["putLzaConfiguration"]["function"])
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"
        assert "qualifier" in params
        assert "config_path" in params
        assert "bucket_name" in params

        # getLzaConfiguration
        sig = inspect.signature(tools["getLzaConfiguration"]["function"])
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"
        assert "qualifier" in params
        assert "bucket_name" in params


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


class TestMCPToolCompatibility:
    @pytest.fixture
    def mock_fastmcp_server(self):
        return _make_mock_server()

    @pytest.mark.asyncio
    async def test_tool_return_value_serialization(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        func = mock_fastmcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "config_files": {"accounts": {"mandatoryAccounts": [{"name": "Mgmt"}]}},
                "instructions_for_assistant": {"message": "Test"},
            }
            result = await func(mock_mcp_context)
            assert json.loads(json.dumps(result)) == result

    @pytest.mark.asyncio
    async def test_tool_async_compatibility(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        for name, info in mock_fastmcp_server.get_registered_tools().items():
            assert inspect.iscoroutinefunction(info["function"]), (
                f"{name} should be async"
            )

    @pytest.mark.asyncio
    async def test_tool_context_requirement(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        for name, info in mock_fastmcp_server.get_registered_tools().items():
            with pytest.raises(TypeError):
                await info["function"]()

    @pytest.mark.asyncio
    async def test_tool_graceful_degradation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        func = mock_fastmcp_server.get_registered_tools()["getMinimumConfiguration"][
            "function"
        ]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"error": "Not found", "message": "Contact admin"}
            result = await func(mock_mcp_context)
            assert "error" in result
            assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def call_args_ctx(mock_obj):
    """Extract the first positional arg (ctx) from the mock call."""
    return mock_obj.call_args[0][0]
