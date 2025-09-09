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
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.config.manage_config_tools import register_config_tools


class TestRegisterConfigTools:
    """Test cases for register_config_tools function."""
    
    @pytest.fixture
    def mock_mcp_server(self):
        """Mock MCP server for tool registration."""
        server = Mock()
        registered_tools = {}
        
        def mock_tool_decorator(name=None, description=None):
            def decorator(func):
                registered_tools[name] = {
                    'name': name,
                    'description': description,
                    'function': func
                }
                return func
            return decorator
        
        server.tool = mock_tool_decorator
        server.get_registered_tools = lambda: registered_tools
        return server
    
    def test_register_config_tools_success(self, mock_mcp_server):
        """Test successful registration of config tools."""
        register_config_tools(mock_mcp_server)
        
        registered_tools = mock_mcp_server.get_registered_tools()
        
        # Verify both tools are registered
        assert 'getMinimumConfiguration' in registered_tools
        assert 'uploadConfigurationToS3' in registered_tools
        
        # Verify tool details
        get_min_config = registered_tools['getMinimumConfiguration']
        assert get_min_config['name'] == 'getMinimumConfiguration'
        assert 'minimal LZA configuration' in get_min_config['description']
        
        upload_config = registered_tools['uploadConfigurationToS3']
        assert upload_config['name'] == 'uploadConfigurationToS3'
        assert 'Upload LZA configuration' in upload_config['description']
    
    @pytest.mark.asyncio
    async def test_get_minimum_configuration_tool_wrapper(self, mock_mcp_server, mock_mcp_context):
        """Test getMinimumConfiguration tool wrapper."""
        register_config_tools(mock_mcp_server)
        registered_tools = mock_mcp_server.get_registered_tools()
        
        get_min_config_func = registered_tools['getMinimumConfiguration']['function']
        
        with patch('awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration') as mock_tool:
            mock_tool.return_value = {'config_files': {}}
            
            result = await get_min_config_func(mock_mcp_context)
            
            # Verify the underlying tool was called
            mock_tool.assert_called_once_with(mock_mcp_context, None, None)
            assert result == {'config_files': {}}
    
    @pytest.mark.asyncio
    async def test_upload_configuration_to_s3_tool_wrapper(self, mock_mcp_server, mock_mcp_context):
        """Test uploadConfigurationToS3 tool wrapper."""
        register_config_tools(mock_mcp_server)
        registered_tools = mock_mcp_server.get_registered_tools()
        
        upload_config_func = registered_tools['uploadConfigurationToS3']['function']
        
        with patch('awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_upload_configuration_to_s3') as mock_tool:
            mock_tool.return_value = {'status': 'success'}
            
            result = await upload_config_func(mock_mcp_context, '/path/to/config', 'my-bucket', False)
            
            # Verify the underlying tool was called with correct parameters
            mock_tool.assert_called_once_with(mock_mcp_context, '/path/to/config', 'my-bucket', False)
            assert result == {'status': 'success'}
    
    @pytest.mark.asyncio
    async def test_get_minimum_configuration_with_parameters(self, mock_mcp_server, mock_mcp_context):
        """Test getMinimumConfiguration with specific parameters."""
        register_config_tools(mock_mcp_server)
        registered_tools = mock_mcp_server.get_registered_tools()
        
        get_min_config_func = registered_tools['getMinimumConfiguration']['function']
        
        with patch('awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration') as mock_tool:
            mock_tool.return_value = {'config_files': {'accounts': {}}}
            
            result = await get_min_config_func(mock_mcp_context, 'accounts', '/save/path')
            
            # Verify parameters are passed correctly
            mock_tool.assert_called_once_with(mock_mcp_context, 'accounts', '/save/path')
            assert result == {'config_files': {'accounts': {}}}
    
    @pytest.mark.asyncio
    async def test_upload_configuration_default_parameters(self, mock_mcp_server, mock_mcp_context):
        """Test uploadConfigurationToS3 with default parameters."""
        register_config_tools(mock_mcp_server)
        registered_tools = mock_mcp_server.get_registered_tools()
        
        upload_config_func = registered_tools['uploadConfigurationToS3']['function']
        
        with patch('awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_upload_configuration_to_s3') as mock_tool:
            mock_tool.return_value = {'status': 'success'}
            
            result = await upload_config_func(mock_mcp_context)
            
            # Verify default parameters are used
            mock_tool.assert_called_once_with(mock_mcp_context, None, None, True)
            assert result == {'status': 'success'}