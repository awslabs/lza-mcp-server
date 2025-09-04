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

"""Unit tests for manage validation tools module."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.tools.validation.manage_validation_tools import (
    register_validation_tools,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class TestRegisterValidationTools:
    """Test cases for register_validation_tools function."""

    def test_register_validation_tools_success(self):
        """Test successful registration of validation tools."""
        mock_mcp = Mock()

        register_validation_tools(mock_mcp)

        # Verify that tool registration was called 3 times
        assert mock_mcp.tool.call_count == 3

        # Verify the tools were registered with correct names
        tool_calls = mock_mcp.tool.call_args_list
        tool_names = [call[1]["name"] for call in tool_calls]

        assert "validateConfigurationFromS3" in tool_names
        assert "validateConfigurationFromShare" in tool_names
        assert "cleanupValidationZip" in tool_names

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_tool_success(self):
        """Test the registered cleanup validation zip tool."""
        mock_mcp = Mock()
        cleanup_tool = None

        # Capture the cleanup tool function
        def capture_tool(name):
            def decorator(func):
                nonlocal cleanup_tool
                if name == "cleanupValidationZip":
                    cleanup_tool = func
                return func

            return decorator

        mock_mcp.tool.side_effect = capture_tool

        register_validation_tools(mock_mcp)

        assert cleanup_tool is not None

        # Test the cleanup tool with existing file
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test content")

            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await cleanup_tool(mock_ctx, temp_dir)

            assert result["success"] is True
            assert result["existed"] is True

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_tool_file_not_exists(self):
        """Test the registered cleanup tool when file doesn't exist."""
        mock_mcp = Mock()
        cleanup_tool = None

        # Capture the cleanup tool function
        def capture_tool(name):
            def decorator(func):
                nonlocal cleanup_tool
                if name == "cleanupValidationZip":
                    cleanup_tool = func
                return func

            return decorator

        mock_mcp.tool.side_effect = capture_tool

        register_validation_tools(mock_mcp)

        assert cleanup_tool is not None

        # Test the cleanup tool with non-existent file
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_ctx = MockContext()

            with patch("os.path.expanduser", return_value=temp_dir):
                result = await cleanup_tool(mock_ctx, temp_dir)

            assert result["success"] is True
            assert result["existed"] is False

    @pytest.mark.asyncio
    async def test_cleanup_validation_zip_tool_error(self):
        """Test the registered cleanup tool with error."""
        mock_mcp = Mock()
        cleanup_tool = None

        # Capture the cleanup tool function
        def capture_tool(name):
            def decorator(func):
                nonlocal cleanup_tool
                if name == "cleanupValidationZip":
                    cleanup_tool = func
                return func

            return decorator

        mock_mcp.tool.side_effect = capture_tool

        register_validation_tools(mock_mcp)

        assert cleanup_tool is not None

        # Test the cleanup tool with permission error
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("test content")

            mock_ctx = MockContext()

            with (
                patch("os.path.expanduser", return_value=temp_dir),
                patch("os.remove", side_effect=PermissionError("Access denied")),
            ):
                result = await cleanup_tool(mock_ctx, temp_dir)

            assert result["success"] is False
            assert "Failed to clean up ZIP file" in result["error"]

    def test_register_validation_tools_with_mock_functions(self):
        """Test registration with mocked validation functions."""
        mock_mcp = Mock()

        with (
            patch(
                "awslabs.lza_mcp_server.tools.validation.manage_validation_tools.tool_validate_configuration_from_s3"
            ) as mock_s3_tool,
            patch(
                "awslabs.lza_mcp_server.tools.validation.manage_validation_tools.tool_validate_configuration_from_share"
            ) as mock_share_tool,
        ):
            register_validation_tools(mock_mcp)

            # Verify imports were successful (functions exist)
            assert mock_s3_tool is not None
            assert mock_share_tool is not None

            # Verify tool registration was called
            assert mock_mcp.tool.call_count == 3
