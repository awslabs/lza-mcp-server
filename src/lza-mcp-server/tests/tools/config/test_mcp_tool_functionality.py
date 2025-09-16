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

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
    register_config_tools,
)


class TestMCPToolRegistration:
    """Test MCP tool registration and functionality."""

    @pytest.fixture
    def mock_fastmcp_server(self):
        """Mock FastMCP server for tool registration."""
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

    def test_config_tools_registration_with_fastmcp(self, mock_fastmcp_server):
        """Test that config tools register properly with FastMCP server."""
        register_config_tools(mock_fastmcp_server)

        registered_tools = mock_fastmcp_server.get_registered_tools()

        # Verify both tools are registered
        assert len(registered_tools) == 2
        assert "getMinimumConfiguration" in registered_tools
        assert "uploadConfigurationToS3" in registered_tools

        # Verify tool metadata
        get_min_config = registered_tools["getMinimumConfiguration"]
        assert callable(get_min_config["function"])
        assert "minimal LZA configuration" in get_min_config["description"]

        upload_config = registered_tools["uploadConfigurationToS3"]
        assert callable(upload_config["function"])
        assert "Upload LZA configuration" in upload_config["description"]

    @pytest.mark.asyncio
    async def test_mcp_context_integration(self, mock_fastmcp_server, mock_mcp_context):
        """Test MCP context integration with config tools."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        # Mock the underlying tool function
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "config_files": {"accounts": {}},
                "instructions_for_assistant": {"message": "Test message"},
            }

            result = await get_min_config_func(mock_mcp_context)

            # Verify context was passed correctly
            mock_tool.assert_called_once()
            call_args = mock_tool.call_args[0]
            assert call_args[0] == mock_mcp_context

            # Verify result structure
            assert "config_files" in result
            assert "instructions_for_assistant" in result

    @pytest.mark.asyncio
    async def test_mcp_context_logging(self, mock_fastmcp_server, mock_mcp_context):
        """Test MCP context logging functionality."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        # Mock the underlying tool to trigger context logging
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:

            async def mock_tool_func(ctx, *args, **kwargs):
                await ctx.info("Test info message")
                await ctx.error("Test error message")
                return {"config_files": {}}

            mock_tool.side_effect = mock_tool_func

            await get_min_config_func(mock_mcp_context)

            # Verify context logging was called
            assert len(mock_mcp_context.info_messages) > 0
            assert len(mock_mcp_context.error_messages) > 0
            assert "Test info message" in mock_mcp_context.info_messages
            assert "Test error message" in mock_mcp_context.error_messages

    @pytest.mark.asyncio
    async def test_concurrent_mcp_tool_execution(self, mock_fastmcp_server):
        """Test concurrent execution of MCP tools."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]
        upload_config_func = registered_tools["uploadConfigurationToS3"]["function"]

        # Create multiple mock contexts
        contexts = [Mock() for _ in range(3)]
        for ctx in contexts:
            ctx.info = AsyncMock()
            ctx.error = AsyncMock()

        # Mock the underlying tools
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_get_tool:
            with patch(
                "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_upload_configuration_to_s3"
            ) as mock_upload_tool:
                mock_get_tool.return_value = {"config_files": {}}
                mock_upload_tool.return_value = {"status": "success"}

                # Execute tools concurrently
                tasks = [
                    get_min_config_func(contexts[0]),
                    upload_config_func(contexts[1]),
                    get_min_config_func(contexts[2]),
                ]

                results = await asyncio.gather(*tasks)

                # Verify all executions completed
                assert len(results) == 3
                assert all(isinstance(result, dict) for result in results)

                # Verify tools were called with correct contexts
                assert mock_get_tool.call_count == 2
                assert mock_upload_tool.call_count == 1


class TestMCPErrorHandling:
    """Test MCP-specific error handling."""

    @pytest.fixture
    def mock_fastmcp_server(self):
        """Mock FastMCP server for error testing."""
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

    @pytest.mark.asyncio
    async def test_mcp_context_error_propagation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test that errors are properly propagated through MCP context."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        # Mock the underlying tool to raise an exception
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.side_effect = Exception("Test exception")

            # Tool should handle exception gracefully
            with pytest.raises(Exception):
                await get_min_config_func(mock_mcp_context)

    @pytest.mark.asyncio
    async def test_mcp_context_error_logging(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test MCP context error logging."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        # Mock the underlying tool to return error response
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "error": "Configuration directory not found",
                "message": "Please check the configuration path",
            }

            result = await get_min_config_func(mock_mcp_context)

            # Verify error response structure
            assert "error" in result
            assert "message" in result
            assert result["error"] == "Configuration directory not found"

    @pytest.mark.asyncio
    async def test_mcp_tool_parameter_validation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test MCP tool parameter validation."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]
        upload_config_func = registered_tools["uploadConfigurationToS3"]["function"]

        # Test with various parameter combinations
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_get_tool:
            with patch(
                "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_upload_configuration_to_s3"
            ) as mock_upload_tool:
                mock_get_tool.return_value = {"config_files": {}}
                mock_upload_tool.return_value = {"status": "success"}

                # Test getMinimumConfiguration with different parameters
                await get_min_config_func(mock_mcp_context)  # No parameters
                await get_min_config_func(
                    mock_mcp_context, "accounts"
                )  # config_type only
                await get_min_config_func(
                    mock_mcp_context, "accounts", "/save/path"
                )  # Both parameters

                # Test uploadConfigurationToS3 with different parameters
                await upload_config_func(mock_mcp_context)  # No parameters
                await upload_config_func(
                    mock_mcp_context, "/config/path"
                )  # config_path only
                await upload_config_func(
                    mock_mcp_context, "/config/path", "bucket-name"
                )  # Multiple parameters
                await upload_config_func(
                    mock_mcp_context, "/config/path", "bucket-name", False
                )  # All parameters

                # Verify tools were called with correct parameter combinations
                assert mock_get_tool.call_count == 3
                assert mock_upload_tool.call_count == 4


class TestMCPToolMetadata:
    """Test MCP tool metadata and documentation."""

    @pytest.fixture
    def mock_fastmcp_server(self):
        """Mock FastMCP server for tool registration."""
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

    def test_tool_descriptions_are_comprehensive(self, mock_fastmcp_server):
        """Test that tool descriptions are comprehensive and helpful."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config = registered_tools["getMinimumConfiguration"]
        upload_config = registered_tools["uploadConfigurationToS3"]

        # Verify descriptions contain key information
        assert "minimal" in get_min_config["description"].lower()
        assert "lza" in get_min_config["description"].lower()
        assert "configuration" in get_min_config["description"].lower()

        assert "upload" in upload_config["description"].lower()
        assert "lza" in upload_config["description"].lower()
        assert "s3" in upload_config["description"].lower()

    def test_tool_names_follow_convention(self, mock_fastmcp_server):
        """Test that tool names follow MCP naming conventions."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        # Verify tool names use camelCase
        for tool_name in registered_tools.keys():
            assert tool_name[0].islower()  # First character should be lowercase
            assert "_" not in tool_name  # Should not contain underscores
            assert "-" not in tool_name  # Should not contain hyphens

    @pytest.mark.asyncio
    async def test_tool_function_signatures(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test that tool function signatures are correct."""
        import inspect

        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        # Test getMinimumConfiguration signature
        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]
        sig = inspect.signature(get_min_config_func)

        # Should have ctx as first parameter
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"

        # Should have optional parameters with defaults
        assert "config_type" in params
        assert "save_to_directory" in params

        # Test uploadConfigurationToS3 signature
        upload_config_func = registered_tools["uploadConfigurationToS3"]["function"]
        sig = inspect.signature(upload_config_func)

        params = list(sig.parameters.keys())
        assert params[0] == "ctx"
        assert "config_path" in params
        assert "bucket_name" in params
        assert "offer_pipeline_release" in params


class TestMCPToolCompatibility:
    """Test MCP tool compatibility and integration."""

    @pytest.fixture
    def mock_fastmcp_server(self):
        """Mock FastMCP server for tool registration."""
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

    @pytest.mark.asyncio
    async def test_tool_return_value_serialization(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test that tool return values are JSON serializable."""
        import json

        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "config_files": {
                    "accounts": {
                        "mandatoryAccounts": [
                            {"name": "Management", "email": "test@example.com"}
                        ]
                    }
                },
                "instructions_for_assistant": {
                    "message": "Test message",
                    "critical_customizations": ["Item 1", "Item 2"],
                },
            }

            result = await get_min_config_func(mock_mcp_context)

            # Should be JSON serializable
            json_str = json.dumps(result)
            assert isinstance(json_str, str)

            # Should be deserializable back to original structure
            deserialized = json.loads(json_str)
            assert deserialized == result

    @pytest.mark.asyncio
    async def test_tool_async_compatibility(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test that tools are properly async and compatible with MCP."""
        import inspect

        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        # All tool functions should be coroutines
        for tool_name, tool_info in registered_tools.items():
            func = tool_info["function"]
            assert inspect.iscoroutinefunction(func), (
                f"Tool {tool_name} should be async"
            )

    @pytest.mark.asyncio
    async def test_tool_context_requirement(self, mock_fastmcp_server):
        """Test that tools require MCP context as first parameter."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        # All tools should require context as first parameter
        for tool_name, tool_info in registered_tools.items():
            func = tool_info["function"]

            # Should raise TypeError if called without context
            with pytest.raises(TypeError):
                await func()  # No arguments provided

    @pytest.mark.asyncio
    async def test_tool_graceful_degradation(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        """Test that tools degrade gracefully when dependencies are missing."""
        register_config_tools(mock_fastmcp_server)
        registered_tools = mock_fastmcp_server.get_registered_tools()

        get_min_config_func = registered_tools["getMinimumConfiguration"]["function"]

        # Mock missing dependencies
        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {
                "error": "Configuration templates not found",
                "message": "Please contact the administrator",
            }

            result = await get_min_config_func(mock_mcp_context)

            # Should return structured error response
            assert "error" in result
            assert "message" in result
            assert isinstance(result, dict)  # Should still return valid structure
