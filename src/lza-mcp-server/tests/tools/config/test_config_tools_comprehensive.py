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

"""Comprehensive tests for config tools covering all MCP functionality."""

import asyncio
import inspect
import json
import os
import shutil
import tempfile

import pytest
import yaml
from unittest.mock import patch, Mock, AsyncMock

from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
    register_config_tools,
)
from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
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


class TestConfigToolsComprehensive:
    @pytest.fixture
    def mock_fastmcp_server(self):
        return _make_mock_server()

    @pytest.fixture
    def complete_lza_config_set(self):
        return {
            "accounts": {
                "mandatoryAccounts": [
                    {
                        "name": "Management",
                        "description": "Mgmt",
                        "email": "mgmt@example.com",
                        "organizationalUnit": "Root",
                        "warm": False,
                    },
                    {
                        "name": "LogArchive",
                        "description": "Logs",
                        "email": "logs@example.com",
                        "organizationalUnit": "Security",
                        "warm": False,
                    },
                    {
                        "name": "Audit",
                        "description": "Audit",
                        "email": "audit@example.com",
                        "organizationalUnit": "Security",
                        "warm": False,
                    },
                ],
                "workloadAccounts": [],
            },
            "global": {
                "homeRegion": "us-east-1",
                "enabledRegions": ["us-east-1", "us-west-2"],
                "managementAccountAccessRole": "AWSControlTowerExecution",
                "terminationProtection": True,
                "cloudwatchLogRetentionInDays": 365,
                "controlTower": {
                    "enable": True,
                    "landingZone": {
                        "version": "3.3",
                        "logging": {"organizationTrail": True},
                    },
                },
            },
            "organization": {
                "organizationalUnits": [
                    {"name": "Security", "parent": "Root"},
                    {"name": "Workloads", "parent": "Root"},
                ]
            },
            "network": {
                "vpcs": [
                    {
                        "name": "SharedServices-Main",
                        "region": "us-east-1",
                        "cidr": "10.0.0.0/16",
                        "enableDnsHostnames": True,
                        "enableDnsSupport": True,
                    }
                ]
            },
            "security": {
                "centralSecurityServices": {
                    "guardduty": {"enable": True, "excludeRegions": []},
                    "securityhub": {"enable": True, "excludeRegions": []},
                }
            },
            "iam": {"policySets": [], "roleSets": [], "groupSets": [], "userSets": []},
        }

    @pytest.fixture
    def temp_complete_config_dir(self, complete_lza_config_set):
        temp_dir = tempfile.mkdtemp()
        for config_type, content in complete_lza_config_set.items():
            with open(os.path.join(temp_dir, f"{config_type}-config.yaml"), "w") as f:
                yaml.dump(content, f, default_flow_style=False)
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_complete_tool_registration(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()

        for name in (
            "getMinimumConfiguration",
            "getLzaConfiguration",
            "putLzaConfiguration",
        ):
            assert name in tools
            assert callable(tools[name]["function"])

    @pytest.mark.asyncio
    async def test_complete_minimum_configuration_workflow(
        self, mock_mcp_context, temp_complete_config_dir
    ):
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_complete_config_dir}):
            result = await tool_get_minimum_configuration(mock_mcp_context)

        assert "config_files" in result
        for cfg in ("accounts", "global", "organization", "network", "security", "iam"):
            assert cfg in result["config_files"]

        instructions = result["instructions_for_assistant"]
        for field in (
            "message",
            "file_naming",
            "required_action",
            "critical_customizations",
            "user_guidance",
            "explain_to_user",
        ):
            assert field in instructions

    @pytest.mark.asyncio
    async def test_complete_error_handling_scenarios(
        self, mock_mcp_context, mock_fastmcp_server
    ):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()
        get_min_func = tools["getMinimumConfiguration"]["function"]

        # Missing config dir
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": "/nonexistent/path"}):
            result = await get_min_func(mock_mcp_context)
            assert "error" in result

        # Invalid config type
        temp_dir = tempfile.mkdtemp()
        try:
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_dir}):
                result = await get_min_func(
                    mock_mcp_context, config_type="invalid_type"
                )
                assert "error" in result
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_complete_configuration_validation_logic(
        self, complete_lza_config_set
    ):
        accounts = complete_lza_config_set["accounts"]["mandatoryAccounts"]
        assert len(accounts) == 3
        names = {a["name"] for a in accounts}
        assert names == {"Management", "LogArchive", "Audit"}

        for acc in accounts:
            assert "@" in acc["email"]
            for field in ("name", "description", "email", "organizationalUnit", "warm"):
                assert field in acc

        global_cfg = complete_lza_config_set["global"]
        assert global_cfg["homeRegion"] in global_cfg["enabledRegions"]

    @pytest.mark.asyncio
    async def test_complete_mcp_integration_workflow(
        self, mock_fastmcp_server, mock_mcp_context, temp_complete_config_dir
    ):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()

        get_min_func = tools["getMinimumConfiguration"]["function"]
        with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_complete_config_dir}):
            config_result = await get_min_func(mock_mcp_context)
        assert "config_files" in config_result
        assert len(config_result["config_files"]) >= 6

        assert len(mock_mcp_context.info_messages) > 0

    @pytest.mark.asyncio
    async def test_complete_async_compatibility(
        self, mock_fastmcp_server, mock_mcp_context
    ):
        register_config_tools(mock_fastmcp_server)
        tools = mock_fastmcp_server.get_registered_tools()

        for name, info in tools.items():
            assert inspect.iscoroutinefunction(info["function"]), (
                f"{name} should be async"
            )

        contexts = [Mock(info=AsyncMock(), error=AsyncMock()) for _ in range(2)]
        func = tools["getMinimumConfiguration"]["function"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.manage_config_tools.tool_get_minimum_configuration"
        ) as mock_tool:
            mock_tool.return_value = {"config_files": {}}
            results = await asyncio.gather(func(contexts[0]), func(contexts[1]))
            assert len(results) == 2

    def test_complete_tool_metadata_compliance(self, mock_fastmcp_server):
        register_config_tools(mock_fastmcp_server)
        for name, info in mock_fastmcp_server.get_registered_tools().items():
            assert name[0].islower()
            assert "_" not in name
            assert "-" not in name
            assert len(info["description"]) > 20
            assert callable(info["function"])

    @pytest.mark.asyncio
    async def test_complete_json_serialization_compatibility(
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
                "config_files": {
                    "accounts": {
                        "mandatoryAccounts": [{"name": "Mgmt", "tags": ["core"]}]
                    }
                },
                "instructions_for_assistant": {"message": "OK"},
            }
            result = await func(mock_mcp_context)
            assert json.loads(json.dumps(result)) == result
