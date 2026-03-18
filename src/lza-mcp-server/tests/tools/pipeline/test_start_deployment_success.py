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

"""Unit tests for start_deployment success scenarios."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.pipeline.start_deployment import (
    tool_start_deployment,
)


def _make_ctx():
    """Create a mock MCP context with async methods."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestStartDeploymentStandardSuccess:
    """Test successful standard pipeline deployment scenarios."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"
    )
    async def test_standard_pipeline_success(self, mock_retry, mock_get_client):
        """Test successful standard pipeline release."""
        ctx = _make_ctx()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        mock_retry.side_effect = [
            {"pipeline": {"name": "AWSAccelerator-Pipeline"}},
            {"pipelineExecutionId": "exec-12345"},
        ]

        result = await tool_start_deployment(
            ctx, pipeline_name="AWSAccelerator-Pipeline"
        )

        assert result["success"] is True
        assert result["execution_id"] == "exec-12345"
        assert result["pipeline_name"] == "AWSAccelerator-Pipeline"
        assert result["deployment_type"] == "standard"
        assert "started successfully" in result["message"]

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"
    )
    async def test_standard_pipeline_with_custom_name(
        self, mock_retry, mock_get_client
    ):
        """Test pipeline release with custom pipeline name."""
        ctx = _make_ctx()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        custom_name = "My-Custom-Pipeline"
        mock_retry.side_effect = [
            {"pipeline": {"name": custom_name}},
            {"pipelineExecutionId": "exec-67890"},
        ]

        result = await tool_start_deployment(ctx, pipeline_name=custom_name)

        assert result["success"] is True
        assert result["execution_id"] == "exec-67890"
        assert result["pipeline_name"] == custom_name
        assert result["deployment_type"] == "standard"


class TestStartDeploymentExternalSuccess:
    """Test successful external pipeline deployment scenarios."""

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_ssm_client")
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"
    )
    async def test_qualifier_with_codepipeline_only(
        self, mock_retry, mock_get_cp_client, mock_get_ssm_client
    ):
        """Test external deployment where only CodePipeline exists."""
        ctx = _make_ctx()
        mock_cp = Mock()
        mock_get_cp_client.return_value = mock_cp
        mock_ssm = Mock()
        mock_get_ssm_client.return_value = mock_ssm

        from botocore.exceptions import ClientError

        # CodePipeline calls succeed
        # SSM describe_document fails with InvalidDocument
        call_count = [0]

        def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            # Calls 1-2: CodePipeline get_pipeline + start_pipeline_execution
            if call_count[0] <= 2:
                if call_count[0] == 1:
                    return {"pipeline": {"name": "test-qual-pipeline"}}
                return {"pipelineExecutionId": "cp-exec-123"}
            # Call 3: SSM describe_document fails
            raise ClientError(
                {"Error": {"Code": "InvalidDocument", "Message": "Not found"}},
                "DescribeDocument",
            )

        mock_retry.side_effect = retry_side_effect

        result = await tool_start_deployment(ctx, qualifier="test-qual")

        assert result["success"] is True
        assert result["deployment_type"] == "external_pipeline"
        assert result["qualifier"] == "test-qual"
        assert "CodePipeline" in result["sources_started"]
        assert result["pipeline_result"]["success"] is True

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_ssm_client")
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"
    )
    async def test_qualifier_with_ssm_automation_only(
        self, mock_retry, mock_get_cp_client, mock_get_ssm_client
    ):
        """Test external deployment where only SSM Automation exists."""
        ctx = _make_ctx()
        mock_cp = Mock()
        mock_get_cp_client.return_value = mock_cp
        mock_ssm = Mock()
        mock_get_ssm_client.return_value = mock_ssm

        from botocore.exceptions import ClientError

        call_count = [0]

        def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            # Call 1: CodePipeline get_pipeline fails
            if call_count[0] == 1:
                raise ClientError(
                    {
                        "Error": {
                            "Code": "PipelineNotFoundException",
                            "Message": "Not found",
                        }
                    },
                    "GetPipeline",
                )
            # Call 2: SSM describe_document succeeds
            if call_count[0] == 2:
                return {"Document": {"Name": "container-dev-1-RunEngine"}}
            # Call 3: SSM start_automation_execution succeeds
            return {"AutomationExecutionId": "ssm-exec-456"}

        mock_retry.side_effect = retry_side_effect

        result = await tool_start_deployment(ctx, qualifier="container-dev-1")

        assert result["success"] is True
        assert result["deployment_type"] == "external_pipeline"
        assert result["qualifier"] == "container-dev-1"
        assert "SSM Automation" in result["sources_started"]
        assert result["container_result"]["success"] is True
        assert result["container_result"]["automation_execution_id"] == "ssm-exec-456"

    @pytest.mark.asyncio
    @patch("awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_ssm_client")
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"
    )
    async def test_qualifier_with_both_sources(
        self, mock_retry, mock_get_cp_client, mock_get_ssm_client
    ):
        """Test external deployment where both CodePipeline and SSM exist."""
        ctx = _make_ctx()
        mock_cp = Mock()
        mock_get_cp_client.return_value = mock_cp
        mock_ssm = Mock()
        mock_get_ssm_client.return_value = mock_ssm

        call_count = [0]

        def retry_side_effect(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"pipeline": {"name": "dual-qual-pipeline"}}
            if call_count[0] == 2:
                return {"pipelineExecutionId": "cp-exec-789"}
            if call_count[0] == 3:
                return {"Document": {"Name": "dual-qual-RunEngine"}}
            return {"AutomationExecutionId": "ssm-exec-789"}

        mock_retry.side_effect = retry_side_effect

        result = await tool_start_deployment(ctx, qualifier="dual-qual")

        assert result["success"] is True
        assert result["deployment_type"] == "external_pipeline"
        assert "CodePipeline" in result["sources_started"]
        assert "SSM Automation" in result["sources_started"]
        assert result["pipeline_result"]["success"] is True
        assert result["container_result"]["success"] is True
