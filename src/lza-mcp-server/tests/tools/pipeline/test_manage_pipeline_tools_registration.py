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

"""Unit tests for manage_pipeline_tools tool registration."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
    register_pipeline_tools,
)


class TestToolRegistration:
    """Test tool registration functionality."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server instance."""
        mcp = Mock()
        mcp.tool = Mock(side_effect=lambda name, description: lambda func: func)
        return mcp

    def test_register_pipeline_tools_basic(self, mock_mcp):
        """Test basic tool registration."""
        register_pipeline_tools(mock_mcp)

        # Verify tool decorator was called for each tool
        assert mock_mcp.tool.call_count == 4

        # Verify tool names
        tool_calls = [call[1]["name"] for call in mock_mcp.tool.call_args_list]
        assert "startDeployment" in tool_calls
        assert "getDeploymentStatus" in tool_calls
        assert "diagnoseDeploymentErrors" in tool_calls
        assert "submitManualApproval" in tool_calls

    def test_register_pipeline_tools_descriptions(self, mock_mcp):
        """Test that tools are registered with descriptions."""
        register_pipeline_tools(mock_mcp)

        # Verify descriptions are provided
        for call_args in mock_mcp.tool.call_args_list:
            kwargs = call_args[1]
            assert "description" in kwargs
            assert len(kwargs["description"]) > 0

    def test_register_pipeline_tools_start_deployment(self, mock_mcp):
        """Test startDeployment tool registration."""
        register_pipeline_tools(mock_mcp)

        # Find the startDeployment tool call
        start_call = None
        for call_args in mock_mcp.tool.call_args_list:
            if call_args[1]["name"] == "startDeployment":
                start_call = call_args
                break

        assert start_call is not None
        assert "Start an LZA deployment" in start_call[1]["description"]

    def test_register_pipeline_tools_get_pipeline_status(self, mock_mcp):
        """Test getDeploymentStatus tool registration."""
        register_pipeline_tools(mock_mcp)

        # Find the getDeploymentStatus tool call
        status_call = None
        for call_args in mock_mcp.tool.call_args_list:
            if call_args[1]["name"] == "getDeploymentStatus":
                status_call = call_args
                break

        assert status_call is not None
        assert "status" in status_call[1]["description"]
        assert "progress" in status_call[1]["description"]

    def test_register_pipeline_tools_diagnose_deployment_errors(self, mock_mcp):
        """Test diagnoseDeploymentErrors tool registration."""
        register_pipeline_tools(mock_mcp)

        # Find the diagnoseDeploymentErrors tool call
        diagnose_call = None
        for call_args in mock_mcp.tool.call_args_list:
            if call_args[1]["name"] == "diagnoseDeploymentErrors":
                diagnose_call = call_args
                break

        assert diagnose_call is not None
        assert (
            "Deep-dive diagnosis of failed LZA deployments"
            in diagnose_call[1]["description"]
        )

    @patch("awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.logger")
    def test_register_pipeline_tools_logging(self, mock_logger, mock_mcp):
        """Test that registration logs success message."""
        register_pipeline_tools(mock_mcp)

        # Verify success logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "Pipeline tools registered successfully" in log_message


class TestToolFunctionWrappers:
    """Test the tool function wrappers created during registration."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server that captures registered functions."""
        registered_tools = {}

        def tool_decorator(name, description):
            def wrapper(func):
                registered_tools[name] = func
                return func

            return wrapper

        mcp = Mock()
        mcp.tool = tool_decorator
        mcp.registered_tools = registered_tools
        return mcp

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.tool_start_deployment"
    )
    async def test_start_deployment_wrapper(self, mock_tool_start, mock_mcp):
        """Test startDeployment wrapper function."""
        # Register tools
        register_pipeline_tools(mock_mcp)

        # Get the registered function
        start_func = mock_mcp.registered_tools["startDeployment"]

        # Mock the underlying tool function
        mock_tool_start.return_value = {"success": True}

        # Create mock context
        mock_ctx = Mock()

        # Call the wrapper with qualifier
        result = await start_func(mock_ctx, qualifier="test-qual")

        # Verify the underlying function was called correctly
        mock_tool_start.assert_called_once_with(
            mock_ctx, "test-qual", "AWSAccelerator-Pipeline"
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.tool_get_deployment_status"
    )
    async def test_get_pipeline_status_wrapper(self, mock_tool_status, mock_mcp):
        """Test getDeploymentStatus wrapper function."""
        # Register tools
        register_pipeline_tools(mock_mcp)

        # Get the registered function
        status_func = mock_mcp.registered_tools["getDeploymentStatus"]

        # Mock the underlying tool function
        mock_tool_status.return_value = {"success": True, "status": "InProgress"}

        # Create mock context
        mock_ctx = Mock()

        # Call the wrapper with execution_id
        result = await status_func(
            mock_ctx, None, "test-pipeline", "12345678-1234-1234-1234-123456789012"
        )

        # Verify the underlying function was called correctly
        mock_tool_status.assert_called_once_with(
            mock_ctx, None, "test-pipeline", "12345678-1234-1234-1234-123456789012"
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.tool_diagnose_deployment_errors"
    )
    async def test_diagnose_deployment_errors_wrapper(
        self, mock_tool_diagnose, mock_mcp
    ):
        """Test diagnoseDeploymentErrors wrapper function."""
        # Register tools
        register_pipeline_tools(mock_mcp)

        # Get the registered function
        diagnose_func = mock_mcp.registered_tools["diagnoseDeploymentErrors"]

        # Mock the underlying tool function
        mock_tool_diagnose.return_value = {"success": True, "errors": []}

        # Create mock context
        mock_ctx = Mock()

        # Call the wrapper
        result = await diagnose_func(mock_ctx, None, "test-pipeline", None)

        # Verify the underlying function was called correctly
        mock_tool_diagnose.assert_called_once_with(
            mock_ctx, None, "test-pipeline", None
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.tool_start_deployment"
    )
    async def test_wrapper_default_pipeline_name(self, mock_tool_start, mock_mcp):
        """Test wrapper uses default pipeline name when not provided."""
        # Register tools
        register_pipeline_tools(mock_mcp)

        # Get the registered function
        start_func = mock_mcp.registered_tools["startDeployment"]

        # Mock the underlying tool function
        mock_tool_start.return_value = {"success": True}

        # Create mock context
        mock_ctx = Mock()

        # Call the wrapper without qualifier or pipeline name (should use defaults)
        await start_func(mock_ctx)

        # Verify the underlying function was called with defaults
        mock_tool_start.assert_called_once()
        call_args = mock_tool_start.call_args
        assert call_args[0][0] == mock_ctx
        # qualifier should be None (default)
        assert call_args[0][1] is None
        # pipeline_name should be the default
        assert call_args[0][2] == "AWSAccelerator-Pipeline"


class TestToolRegistrationEdgeCases:
    """Test edge cases in tool registration."""

    def test_register_pipeline_tools_multiple_times(self):
        """Test registering tools multiple times."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=lambda name, description: lambda func: func)

        # Register tools twice
        register_pipeline_tools(mock_mcp)
        first_call_count = mock_mcp.tool.call_count

        register_pipeline_tools(mock_mcp)
        second_call_count = mock_mcp.tool.call_count

        # Should register tools both times
        assert first_call_count == 4
        assert second_call_count == 8  # 4 + 4

    def test_register_pipeline_tools_with_none_mcp(self):
        """Test registering tools with None MCP instance."""
        with pytest.raises(AttributeError):
            register_pipeline_tools(None)

    def test_register_pipeline_tools_preserves_function_names(self):
        """Test that registered functions preserve their names."""
        registered_tools = {}

        def tool_decorator(name, description):
            def wrapper(func):
                registered_tools[name] = func
                return func

            return wrapper

        mock_mcp = Mock()
        mock_mcp.tool = tool_decorator

        register_pipeline_tools(mock_mcp)

        # Verify function names are preserved
        assert "startDeployment" in registered_tools
        assert "getDeploymentStatus" in registered_tools
        assert "diagnoseDeploymentErrors" in registered_tools

        # Verify functions are callable
        for func in registered_tools.values():
            assert callable(func)


class TestToolRegistrationIntegration:
    """Test tool registration integration scenarios."""

    @pytest.fixture
    def mock_mcp_with_tracking(self):
        """Create a mock MCP that tracks all registered tools."""

        class MockMCP:
            def __init__(self):
                self.tools = {}
                self.tool_call_count = 0

            def tool(self, name, description):
                self.tool_call_count += 1

                def decorator(func):
                    self.tools[name] = {
                        "function": func,
                        "description": description,
                        "name": name,
                    }
                    return func

                return decorator

        return MockMCP()

    def test_all_tools_registered_correctly(self, mock_mcp_with_tracking):
        """Test that all tools are registered with correct metadata."""
        register_pipeline_tools(mock_mcp_with_tracking)

        # Verify all expected tools are registered
        expected_tools = [
            "startDeployment",
            "getDeploymentStatus",
            "diagnoseDeploymentErrors",
            "submitManualApproval",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_with_tracking.tools
            tool_info = mock_mcp_with_tracking.tools[tool_name]
            assert tool_info["name"] == tool_name
            assert len(tool_info["description"]) > 0
            assert callable(tool_info["function"])

    def test_tool_registration_order(self, mock_mcp_with_tracking):
        """Test that tools are registered in expected order."""
        register_pipeline_tools(mock_mcp_with_tracking)

        # Get the order of registration
        tool_names = list(mock_mcp_with_tracking.tools.keys())

        # Verify order matches expected order
        assert tool_names[0] == "startDeployment"
        assert tool_names[1] == "getDeploymentStatus"
        assert tool_names[2] == "diagnoseDeploymentErrors"

    @patch("awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.logger")
    def test_registration_error_handling(self, mock_logger):
        """Test error handling during registration."""
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=Exception("Registration failed"))

        # Registration should raise the exception
        with pytest.raises(Exception) as exc_info:
            register_pipeline_tools(mock_mcp)

        assert "Registration failed" in str(exc_info.value)
