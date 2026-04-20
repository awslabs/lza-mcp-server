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

"""Additional tests for diagnose_deployment_errors.py to cover qualifier exception paths."""

import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    tool_diagnose_deployment_errors,
)


class MockContext:
    """Mock MCP context."""

    def __init__(self):
        self.info_messages = []
        self.error_messages = []

    async def info(self, message):
        self.info_messages.append(message)

    async def error(self, message):
        self.error_messages.append(message)


class TestDiagnoseQualifierExceptionPaths:
    """Test qualifier exception paths in tool_diagnose_deployment_errors."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_container_deployment"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
    )
    async def test_pipeline_exception_caught(self, mock_pipeline, mock_container):
        """Test that pipeline exception is caught and container is still checked."""
        ctx = MockContext()
        mock_pipeline.side_effect = RuntimeError("connection timeout")
        mock_container.return_value = {
            "success": True,
            "deployment_type": "ecs_container",
            "failed_deployments": [],
            "message": "No issues found",
        }

        result = await tool_diagnose_deployment_errors(
            ctx=ctx,
            pipeline_name="AWSAccelerator-Pipeline",
            execution_id=None,
            qualifier="myqualifier",
        )

        # Container was found, so result should be success
        assert result["success"] is True
        assert "ECS container" in result.get("sources_checked", [])

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_container_deployment"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
    )
    async def test_container_exception_caught(self, mock_pipeline, mock_container):
        """Test that container exception is caught and pipeline result is still used."""
        ctx = MockContext()
        mock_pipeline.return_value = {
            "success": True,
            "pipeline_name": "myqualifier-pipeline",
            "failed_actions": [],
            "message": "No issues",
        }
        mock_container.side_effect = RuntimeError("connection timeout")

        result = await tool_diagnose_deployment_errors(
            ctx=ctx,
            pipeline_name="AWSAccelerator-Pipeline",
            execution_id=None,
            qualifier="myqualifier",
        )

        # Pipeline was found, so result should be success
        assert result["success"] is True
        assert "CodePipeline" in result.get("sources_checked", [])

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_container_deployment"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
    )
    async def test_both_exceptions_caught(self, mock_pipeline, mock_container):
        """Test that both exceptions are caught — no sources found."""
        ctx = MockContext()
        mock_pipeline.side_effect = RuntimeError("pipeline error")
        mock_container.side_effect = RuntimeError("container error")

        result = await tool_diagnose_deployment_errors(
            ctx=ctx,
            pipeline_name="AWSAccelerator-Pipeline",
            execution_id=None,
            qualifier="myqualifier",
        )

        # Neither source found, so result should be failure
        assert result["success"] is False
        assert "No deployment infrastructure found" in result.get("error", "")

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_container_deployment"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
    )
    async def test_pipeline_not_found_skipped(self, mock_pipeline, mock_container):
        """Test pipeline with PipelineNotFoundException is skipped."""
        ctx = MockContext()
        mock_pipeline.return_value = {
            "success": False,
            "error_code": "PipelineNotFoundException",
        }
        mock_container.return_value = {
            "success": True,
            "deployment_type": "ecs_container",
            "failed_deployments": [],
            "message": "No issues found",
        }

        result = await tool_diagnose_deployment_errors(
            ctx=ctx,
            pipeline_name="AWSAccelerator-Pipeline",
            execution_id=None,
            qualifier="myqualifier",
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_container_deployment"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors._diagnose_standard_pipeline"
    )
    async def test_container_not_found_skipped(self, mock_pipeline, mock_container):
        """Test container with ResourceNotFoundException is skipped."""
        ctx = MockContext()
        mock_pipeline.return_value = {
            "success": True,
            "pipeline_name": "myqualifier-pipeline",
            "failed_actions": [],
            "message": "No issues",
        }
        mock_container.return_value = {
            "success": False,
            "error_code": "ResourceNotFoundException",
        }

        result = await tool_diagnose_deployment_errors(
            ctx=ctx,
            pipeline_name="AWSAccelerator-Pipeline",
            execution_id=None,
            qualifier="myqualifier",
        )

        assert result["success"] is True
