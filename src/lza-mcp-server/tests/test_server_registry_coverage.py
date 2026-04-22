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

"""Additional tests for server_registry.py to cover resource tools registration."""

from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.server_registry import register_all_components


class TestRegisterAllComponentsResourceTools:
    """Test resource tools registration in register_all_components."""

    @patch("awslabs.lza_mcp_server.tools.resource_tools.register_resource_tools")
    @patch("awslabs.lza_mcp_server.server_registry.register_workspace_components")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    @patch("awslabs.lza_mcp_server.server_registry.create_storage_adapter")
    def test_resource_tools_enabled_by_default(
        self,
        mock_adapter,
        mock_core,
        mock_uc,
        mock_ws,
        mock_resource_tools,
    ):
        """Test resource tools are registered when not disabled."""
        mock_adapter.return_value = Mock()
        mcp = Mock()

        register_all_components(
            mcp, enable_uc_merge=False, disable_resource_tools=False
        )

        mock_resource_tools.assert_called_once()

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.server_registry.register_workspace_components")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    @patch("awslabs.lza_mcp_server.server_registry.create_storage_adapter")
    def test_resource_tools_disabled(
        self,
        mock_adapter,
        mock_core,
        mock_uc,
        mock_ws,
        mock_logger,
    ):
        """Test resource tools are NOT registered when disabled."""
        mock_adapter.return_value = Mock()
        mcp = Mock()

        register_all_components(mcp, enable_uc_merge=False, disable_resource_tools=True)

        mock_logger.info.assert_any_call(
            "Resource workaround tools disabled (DISABLE_RESOURCE_TOOLS is set)"
        )


class TestRegisterWorkspaceComponents:
    """Test register_workspace_components directly."""

    @patch("awslabs.lza_mcp_server.resources.workspace.register_workspace_resources")
    @patch("awslabs.lza_mcp_server.tools.workspace.register_workspace_tools")
    def test_registers_tools_and_resources(self, mock_tools, mock_resources):
        """Test that workspace tools and resources are both registered."""
        from awslabs.lza_mcp_server.server_registry import (
            register_workspace_components,
        )

        mcp = Mock()
        wm = Mock()
        zu = Mock()

        register_workspace_components(mcp, wm, zu)

        mock_tools.assert_called_once_with(mcp, wm, zu)
        mock_resources.assert_called_once_with(mcp, wm)
