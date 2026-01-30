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

"""Unit tests for manage_aws_service_tools registration."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools import (
    register_aws_tools,
)


class MockContext:
    """Mock MCP context for testing."""

    async def info(self, message):
        pass

    async def error(self, message):
        pass


class TestRegisterAwsTools:
    """Test AWS tools registration."""

    def test_register_aws_tools_success(self):
        """Test successful registration of AWS tools."""
        mock_mcp = Mock()

        register_aws_tools(mock_mcp)

        # Verify that tool registration was called twice
        assert mock_mcp.tool.call_count == 2

        # Verify the tools were registered with correct names and descriptions
        tool_calls = mock_mcp.tool.call_args_list

        # First tool: checkAwsConnectivity
        assert tool_calls[0][1]["name"] == "checkAwsConnectivity"
        assert "AWS credentials" in tool_calls[0][1]["description"]

        # Second tool: getDeployedLzaVersion
        assert tool_calls[1][1]["name"] == "getDeployedLzaVersion"
        assert "deployed LZA version" in tool_calls[1][1]["description"]

    @pytest.mark.asyncio
    async def test_check_aws_connectivity_wrapper(self):
        """Test checkAwsConnectivity wrapper function."""
        mock_mcp = Mock()
        registered_functions = {}

        # Capture the registered functions
        def mock_tool(name, description):
            def decorator(func):
                registered_functions[name] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool

        # Register the tools
        register_aws_tools(mock_mcp)

        # Verify checkAwsConnectivity was registered
        assert "checkAwsConnectivity" in registered_functions

        # Mock the underlying tool function
        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools.tool_check_aws_connectivity"
        ) as mock_tool_func:
            mock_tool_func.return_value = {
                "connected": True,
                "account_id": "123456789012",
            }

            # Call the registered function
            mock_context = MockContext()
            result = await registered_functions["checkAwsConnectivity"](mock_context)

            # Verify the underlying tool was called
            mock_tool_func.assert_called_once_with(mock_context)
            assert result["connected"] is True
            assert result["account_id"] == "123456789012"

    @pytest.mark.asyncio
    async def test_get_deployed_lza_version_wrapper(self):
        """Test getDeployedLzaVersion wrapper function."""
        mock_mcp = Mock()
        registered_functions = {}

        # Capture the registered functions
        def mock_tool(name, description):
            def decorator(func):
                registered_functions[name] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool

        # Register the tools
        register_aws_tools(mock_mcp)

        # Verify getDeployedLzaVersion was registered
        assert "getDeployedLzaVersion" in registered_functions

        # Mock the underlying tool function
        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools.tool_get_deployed_lza_version"
        ) as mock_tool_func:
            mock_tool_func.return_value = {
                "success": True,
                "version": "v1.5.0",
            }

            # Call the registered function
            mock_context = MockContext()
            result = await registered_functions["getDeployedLzaVersion"](mock_context)

            # Verify the underlying tool was called
            mock_tool_func.assert_called_once_with(mock_context)
            assert result["success"] is True
            assert result["version"] == "v1.5.0"

    @pytest.mark.asyncio
    async def test_both_wrappers_independent(self):
        """Test that both wrapper functions work independently."""
        mock_mcp = Mock()
        registered_functions = {}

        # Capture the registered functions
        def mock_tool(name, description):
            def decorator(func):
                registered_functions[name] = func
                return func

            return decorator

        mock_mcp.tool = mock_tool

        # Register the tools
        register_aws_tools(mock_mcp)

        # Mock both underlying tool functions
        with (
            patch(
                "awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools.tool_check_aws_connectivity"
            ) as mock_connectivity,
            patch(
                "awslabs.lza_mcp_server.tools.aws_services.manage_aws_service_tools.tool_get_deployed_lza_version"
            ) as mock_version,
        ):
            mock_connectivity.return_value = {"connected": True}
            mock_version.return_value = {"version": "v1.5.0"}

            mock_context = MockContext()

            # Call both functions
            result1 = await registered_functions["checkAwsConnectivity"](mock_context)
            result2 = await registered_functions["getDeployedLzaVersion"](mock_context)

            # Verify both were called independently
            mock_connectivity.assert_called_once()
            mock_version.assert_called_once()
            assert result1["connected"] is True
            assert result2["version"] == "v1.5.0"
