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

"""Unit tests for server component registration."""

from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.server_registry import (
    register_all_components,
    register_core_tools,
    register_uc_merge_tools_if_enabled,
)


class TestRegisterCoreTools:
    """Test core tools registration."""

    @patch("awslabs.lza_mcp_server.tools.schema.register_schema_tools")
    @patch("awslabs.lza_mcp_server.tools.pipeline.register_pipeline_tools")
    @patch("awslabs.lza_mcp_server.tools.config.register_config_tools")
    @patch("awslabs.lza_mcp_server.tools.aws_services.register_aws_tools")
    def test_registers_all_core_tools(
        self,
        mock_aws_tools,
        mock_config_tools,
        mock_pipeline_tools,
        mock_schema_tools,
    ):
        """Test all core tools are registered."""
        mock_mcp = Mock()

        register_core_tools(mock_mcp)

        mock_aws_tools.assert_called_once_with(mock_mcp)
        mock_config_tools.assert_called_once_with(mock_mcp)
        mock_pipeline_tools.assert_called_once_with(mock_mcp)
        mock_schema_tools.assert_called_once_with(mock_mcp)

    @patch("awslabs.lza_mcp_server.tools.schema.register_schema_tools")
    @patch("awslabs.lza_mcp_server.tools.pipeline.register_pipeline_tools")
    @patch("awslabs.lza_mcp_server.tools.config.register_config_tools")
    @patch("awslabs.lza_mcp_server.tools.aws_services.register_aws_tools")
    def test_registration_order(
        self,
        mock_aws_tools,
        mock_config_tools,
        mock_pipeline_tools,
        mock_schema_tools,
    ):
        """Test tools are registered in correct order."""
        mock_mcp = Mock()
        call_order = []

        mock_aws_tools.side_effect = lambda x: call_order.append("aws")
        mock_config_tools.side_effect = lambda x: call_order.append("config")
        mock_pipeline_tools.side_effect = lambda x: call_order.append("pipeline")
        mock_schema_tools.side_effect = lambda x: call_order.append("schema")

        register_core_tools(mock_mcp)

        assert call_order == ["aws", "config", "pipeline", "schema"]


class TestRegisterUcMergeToolsIfEnabled:
    """Test conditional UC Merge tools registration."""

    @patch("awslabs.lza_mcp_server.tools.uc_merge.register_uc_merge_tools")
    def test_registers_when_enabled(self, mock_uc_merge_tools):
        """Test UC Merge tools are registered when enabled."""
        mock_mcp = Mock()

        register_uc_merge_tools_if_enabled(mock_mcp, enabled=True)

        mock_uc_merge_tools.assert_called_once_with(mock_mcp)

    @patch("awslabs.lza_mcp_server.tools.uc_merge.register_uc_merge_tools")
    def test_does_not_register_when_disabled(self, mock_uc_merge_tools):
        """Test UC Merge tools are not registered when disabled."""
        mock_mcp = Mock()

        register_uc_merge_tools_if_enabled(mock_mcp, enabled=False)

        mock_uc_merge_tools.assert_not_called()

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.tools.uc_merge.register_uc_merge_tools")
    def test_logs_enabled_message(self, mock_uc_merge_tools, mock_logger):
        """Test logs message when UC Merge tools are enabled."""
        mock_mcp = Mock()

        register_uc_merge_tools_if_enabled(mock_mcp, enabled=True)

        mock_logger.info.assert_called_with("UC Merge tools enabled and registered")

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.tools.uc_merge.register_uc_merge_tools")
    def test_logs_disabled_message(self, mock_uc_merge_tools, mock_logger):
        """Test logs message when UC Merge tools are disabled."""
        mock_mcp = Mock()

        register_uc_merge_tools_if_enabled(mock_mcp, enabled=False)

        mock_logger.info.assert_called_with(
            "UC Merge tools disabled (set ENABLE_UC_MERGE=true to enable)"
        )


class TestRegisterAllComponents:
    """Test complete component registration."""

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    def test_registers_core_and_uc_merge_enabled(
        self,
        mock_core_tools,
        mock_uc_merge_conditional,
        mock_logger,
    ):
        """Test registers core tools and UC Merge when enabled."""
        mock_mcp = Mock()

        register_all_components(mock_mcp, enable_uc_merge=True)

        mock_core_tools.assert_called_once_with(mock_mcp)
        mock_uc_merge_conditional.assert_called_once_with(mock_mcp, True)
        mock_logger.info.assert_called_with(
            "All MCP components registered successfully"
        )

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    def test_registers_core_and_uc_merge_disabled(
        self,
        mock_core_tools,
        mock_uc_merge_conditional,
        mock_logger,
    ):
        """Test registers core tools without UC Merge when disabled."""
        mock_mcp = Mock()

        register_all_components(mock_mcp, enable_uc_merge=False)

        mock_core_tools.assert_called_once_with(mock_mcp)
        mock_uc_merge_conditional.assert_called_once_with(mock_mcp, False)
        mock_logger.info.assert_called_with(
            "All MCP components registered successfully"
        )

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    def test_registration_order(
        self,
        mock_core_tools,
        mock_uc_merge_conditional,
        mock_logger,
    ):
        """Test components are registered in correct order."""
        mock_mcp = Mock()
        call_order = []

        mock_core_tools.side_effect = lambda x: call_order.append("core")
        mock_uc_merge_conditional.side_effect = lambda x, y: call_order.append(
            "uc_merge"
        )

        register_all_components(mock_mcp, enable_uc_merge=True)

        assert call_order == ["core", "uc_merge"]

    @patch("awslabs.lza_mcp_server.server_registry.logger")
    @patch("awslabs.lza_mcp_server.server_registry.register_uc_merge_tools_if_enabled")
    @patch("awslabs.lza_mcp_server.server_registry.register_core_tools")
    def test_logs_completion_message(
        self,
        mock_core_tools,
        mock_uc_merge_conditional,
        mock_logger,
    ):
        """Test logs completion message after registration."""
        mock_mcp = Mock()

        register_all_components(mock_mcp, enable_uc_merge=False)

        # Should log completion message
        assert any(
            "All MCP components registered successfully" in str(call)
            for call in mock_logger.info.call_args_list
        )
