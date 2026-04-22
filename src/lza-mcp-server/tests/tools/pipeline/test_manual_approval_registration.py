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

"""Unit tests for manual approval tool registration and descriptions."""

import pytest
from unittest.mock import Mock

from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
    register_pipeline_tools,
)
from awslabs.lza_mcp_server.tools.pipeline.descriptions import DESCRIPTIONS


class TestManualApprovalRegistration:
    """Test that submitManualApproval is always registered."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server instance."""
        mcp = Mock()
        mcp.tool = Mock(side_effect=lambda name, description: lambda func: func)
        return mcp

    def test_submit_manual_approval_always_registered(self, mock_mcp):
        """submitManualApproval is always registered (no feature flag)."""
        register_pipeline_tools(mock_mcp)

        tool_names = [call[1]["name"] for call in mock_mcp.tool.call_args_list]
        assert "submitManualApproval" in tool_names
        # 3 base tools + 1 submitManualApproval = 4
        assert mock_mcp.tool.call_count == 4


class TestManualApprovalDescriptions:
    """Test that description variants exist and differ for manual approval tools."""

    def test_get_manual_approval_status_not_a_separate_tool(self):
        """getManualApprovalStatus is not a separate description entry — merged into getDeploymentStatus."""
        assert "getManualApprovalStatus" not in DESCRIPTIONS

    def test_deployment_status_description_mentions_approval(self):
        """getDeploymentStatus description mentions approval detection."""
        desc = DESCRIPTIONS["getDeploymentStatus"]
        assert "approval" in desc["standard"].lower()

    def test_submit_manual_approval_descriptions_exist(self):
        """submitManualApproval has both standard and disable_guidance variants."""
        assert "submitManualApproval" in DESCRIPTIONS
        desc = DESCRIPTIONS["submitManualApproval"]
        assert "standard" in desc
        assert "disable_guidance" in desc

    def test_submit_manual_approval_descriptions_differ(self):
        """submitManualApproval standard and disable_guidance variants differ."""
        desc = DESCRIPTIONS["submitManualApproval"]
        assert desc["standard"] != desc["disable_guidance"]

    def test_submit_manual_approval_references_deployment_status(self):
        """submitManualApproval description references getDeploymentStatus."""
        desc = DESCRIPTIONS["submitManualApproval"]
        assert "getDeploymentStatus" in desc["standard"]
