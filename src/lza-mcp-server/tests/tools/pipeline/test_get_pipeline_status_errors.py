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

"""Unit tests for get_pipeline_status error handling."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.get_deployment_status import (
    tool_get_deployment_status,
)


class TestPipelineStatusErrors:
    """Test error handling in pipeline status retrieval."""

    @pytest.mark.asyncio
    async def test_pipeline_not_found(self, mock_mcp_context):
        """Test handling of pipeline not found error."""
        error_response = {"Error": {"Code": "PipelineNotFoundException"}}
        client_error = ClientError(error_response, "get_pipeline")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=client_error,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, pipeline_name="non-existent-pipeline"
            )

            assert result["success"] is False
            assert "PipelineNotFoundException" in result.get("error_code", "")
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_execution_not_found(self, mock_mcp_context):
        """Test handling of execution not found error."""
        execution_id = "12345678-1234-1234-1234-123456789012"

        mock_pipeline_response = {
            "pipeline": {"stages": [{"name": "Source"}, {"name": "Build"}]}
        }

        mock_executions_response = {
            "pipelineExecutionSummaries": [
                {
                    "pipelineExecutionId": "different-id-1234-1234-1234-123456789012",
                    "status": "Succeeded",
                    "startTime": datetime(2024, 1, 15, 10, 30, 0),
                }
            ]
        }

        error_response = {"Error": {"Code": "PipelineExecutionNotFoundException"}}
        client_error = ClientError(error_response, "get_pipeline_execution")

        async def mock_retry(func, **kwargs):
            # Determine which API call based on kwargs
            if (
                "name" in kwargs
                and "pipelineName" not in kwargs
                and "pipelineExecutionId" not in kwargs
            ):
                # get_pipeline call
                return mock_pipeline_response
            elif "pipelineName" in kwargs and "maxResults" in kwargs:
                # list_pipeline_executions call
                return mock_executions_response
            elif "pipelineName" in kwargs and "pipelineExecutionId" in kwargs:
                # get_pipeline_execution call - raise error
                raise client_error
            return {}

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=mock_retry,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context,
                pipeline_name="test-pipeline",
                execution_id=execution_id,
            )

            assert result["success"] is False
            assert "PipelineExecutionNotFoundException" in result.get("error_code", "")
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_generic_aws_error(self, mock_mcp_context):
        """Test handling of generic AWS errors."""
        error_response = {"Error": {"Code": "AccessDeniedException"}}
        client_error = ClientError(error_response, "get_pipeline")

        with (
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.get_codepipeline_client"
            ) as mock_client,
            patch(
                "awslabs.lza_mcp_server.tools.pipeline.get_deployment_status.retry_with_exponential_backoff",
                side_effect=client_error,
            ),
        ):
            mock_client.return_value = Mock()

            result = await tool_get_deployment_status(
                mock_mcp_context, pipeline_name="test-pipeline"
            )

            assert result["success"] is False
            assert "error" in result
