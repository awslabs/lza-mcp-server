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

"""Integration tests for pipeline_tools module.

These tests work with real AWS services and require proper AWS credentials.
They are designed to test the actual integration with AWS CodePipeline services.

Prerequisites:
- AWS credentials configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_PROFILE)
- AWS_REGION environment variable set
- IAM permissions for CodePipeline operations
- A test pipeline named 'test-pipeline' (optional, will use default if not specified)

Environment Variables:
- AWS_REGION: AWS region for testing (default: us-east-1)
- TEST_PIPELINE_NAME: Name of test pipeline (default: AWSAccelerator-Pipeline)
- SKIP_INTEGRATION_TESTS: Set to 'true' to skip integration tests
"""

import os
import pytest
import asyncio
from unittest.mock import Mock
from mcp.server.fastmcp import Context, FastMCP

# Skip integration tests if explicitly disabled
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION_TESTS", "").lower() == "true",
    reason="Integration tests disabled via SKIP_INTEGRATION_TESTS environment variable",
)

# Test configuration
TEST_PIPELINE_NAME = os.environ.get("TEST_PIPELINE_NAME", "AWSAccelerator-Pipeline")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class TestPipelineToolsIntegration:
    """Integration tests for pipeline tools with real AWS services."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock MCP context for testing."""
        return Mock(spec=Context)

    @pytest.fixture
    def mcp_server(self):
        """Create a FastMCP server instance for testing tool registration."""
        return FastMCP("test-server")

    @pytest.fixture
    def registered_tools(self, mcp_server):
        """Register pipeline tools and return the tool functions."""
        from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
            register_pipeline_tools,
        )

        # Capture registered tools
        tool_functions = {}
        original_tool = mcp_server.tool

        def capture_tool(name, **kwargs):
            def decorator(func):
                tool_functions[name] = func
                return original_tool(name, **kwargs)(func)

            return decorator

        mcp_server.tool = capture_tool
        register_pipeline_tools(mcp_server)

        return tool_functions

    @pytest.mark.asyncio
    async def test_tool_registration_and_discovery(self, mcp_server, registered_tools):
        """Test that pipeline tools are properly registered with FastMCP framework.

        Requirements: 4.1 - Tool registration and discovery
        """
        # Verify all expected tools are registered
        expected_tools = [
            "releasePipeline",
            "getPipelineStatus",
            "diagnosePipelineErrors",
        ]

        for tool_name in expected_tools:
            assert tool_name in registered_tools, f"Tool {tool_name} not registered"
            assert callable(registered_tools[tool_name]), (
                f"Tool {tool_name} is not callable"
            )

        # Verify tools have proper async signatures
        for tool_name, tool_func in registered_tools.items():
            assert asyncio.iscoroutinefunction(tool_func), (
                f"Tool {tool_name} is not async"
            )

    @pytest.mark.asyncio
    async def test_pipeline_status_with_real_aws(self, mock_context, registered_tools):
        """Test pipeline status retrieval with real AWS CodePipeline service.

        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5 - Pipeline status monitoring
        """
        get_status_func = registered_tools["getPipelineStatus"]

        # Test with default pipeline name
        result = await get_status_func(mock_context)

        # Verify response structure
        assert isinstance(result, dict), "Response should be a dictionary"
        assert "success" in result, "Response should have 'success' field"
        assert "message" in result, "Response should have 'message' field"

        if result["success"]:
            # If successful, verify required fields are present
            assert "pipeline_name" in result, (
                "Successful response should have 'pipeline_name'"
            )
            assert "status" in result, "Successful response should have 'status'"

            # Verify status is a valid CodePipeline status
            valid_statuses = [
                "SUCCEEDED",
                "FAILED",
                "IN_PROGRESS",
                "STOPPED",
                "STOPPING",
                "SUPERSEDED",
            ]
            if "status" in result:
                assert result["status"] in valid_statuses, (
                    f"Invalid status: {result['status']}"
                )

            # Verify stage_progress structure
            if "stage_progress" in result:
                stage_progress = result["stage_progress"]
                assert "total_stages" in stage_progress, (
                    "stage_progress should have 'total_stages'"
                )
                assert "completed_stages" in stage_progress, (
                    "stage_progress should have 'completed_stages'"
                )
                assert isinstance(stage_progress["completed_stages"], int), (
                    "completed_stages should be an integer"
                )
                assert stage_progress["completed_stages"] >= 0, (
                    "completed_stages should be non-negative"
                )

            # If execution is found, verify execution_id format
            if "execution_id" in result:
                execution_id = result["execution_id"]
                assert isinstance(execution_id, str), "Execution ID should be a string"
                assert len(execution_id) == 36, (
                    "Execution ID should be 36 characters (UUID format)"
                )
                assert execution_id.count("-") == 4, (
                    "Execution ID should have 4 hyphens (UUID format)"
                )
        else:
            # If failed, verify error information is present
            assert "error" in result, "Failed response should have 'error' field"
            assert "troubleshooting" in result, (
                "Failed response should have 'troubleshooting' field"
            )
            assert isinstance(result["troubleshooting"], list), (
                "Troubleshooting should be a list"
            )

    @pytest.mark.asyncio
    async def test_pipeline_status_with_custom_pipeline(
        self, mock_context, registered_tools
    ):
        """Test pipeline status with custom pipeline name.

        Requirements: 4.2 - Custom pipeline name support
        """
        from unittest.mock import patch, Mock

        get_status_func = registered_tools["getPipelineStatus"]

        # Mock the AWS CodePipeline client
        with patch(
            "awslabs.lza_mcp_server.aws_access.get_codepipeline_client"
        ) as mock_client:
            mock_codepipeline = Mock()
            mock_client.return_value = mock_codepipeline

            # Mock pipeline structure
            mock_codepipeline.get_pipeline.return_value = {
                "pipeline": {
                    "stages": [
                        {"name": "Source"},
                        {"name": "Build"},
                        {"name": "Deploy"},
                    ]
                }
            }

            # Mock pipeline executions
            mock_codepipeline.list_pipeline_executions.return_value = {
                "pipelineExecutionSummaries": [
                    {
                        "pipelineExecutionId": "test-execution-id",
                        "status": "SUCCEEDED",
                        "startTime": "2024-01-01T00:00:00Z",
                    }
                ]
            }

            # Mock pipeline state
            mock_codepipeline.get_pipeline_state.return_value = {
                "stageStates": [
                    {"stageName": "Source", "latestExecution": {"status": "SUCCEEDED"}},
                    {"stageName": "Build", "latestExecution": {"status": "SUCCEEDED"}},
                    {"stageName": "Deploy", "latestExecution": {"status": "SUCCEEDED"}},
                ]
            }

            # Test with custom pipeline name
            result = await get_status_func(
                mock_context, pipeline_name=TEST_PIPELINE_NAME
            )

            # Verify response structure
            assert isinstance(result, dict), "Response should be a dictionary"
            assert "success" in result, "Response should have 'success' field"
            # Pipeline name field is optional in some responses
        if result.get("success"):
            assert "pipeline_name" in result, (
                "Successful response should have 'pipeline_name' field"
            )

            # Verify pipeline name is correctly set
            if "pipeline_name" in result:
                assert result["pipeline_name"] == TEST_PIPELINE_NAME, (
                    "Pipeline name should match input"
                )

    @pytest.mark.asyncio
    async def test_pipeline_release_validation(self, mock_context, registered_tools):
        """Test pipeline release input validation and AWS connectivity.

        Requirements: 1.1, 1.2, 1.3, 1.4 - Pipeline release functionality
        """
        release_func = registered_tools["releasePipeline"]

        # Test with invalid pipeline name (should fail validation before AWS call)
        result = await release_func(mock_context, pipeline_name="invalid pipeline name")

        assert result["success"] is False, "Invalid pipeline name should fail"
        assert "invalid characters" in result["error"].lower(), (
            "Should mention invalid characters"
        )
        assert "troubleshooting" in result, "Should provide troubleshooting guidance"

        # Test with empty pipeline name
        result = await release_func(mock_context, pipeline_name="")

        assert result["success"] is False, "Empty pipeline name should fail"
        assert "cannot be empty" in result["error"].lower(), "Should mention empty name"

        # Test with too long pipeline name
        long_name = "a" * 101
        result = await release_func(mock_context, pipeline_name=long_name)

        assert result["success"] is False, "Too long pipeline name should fail"
        assert "exceeds maximum length" in result["error"].lower(), "Should mention length limit"

    @pytest.mark.asyncio
    async def test_error_diagnosis_validation(self, mock_context, registered_tools):
        """Test error diagnosis input validation and AWS connectivity.

        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5 - Error diagnosis functionality
        """
        diagnose_func = registered_tools["diagnosePipelineErrors"]

        # Test with invalid execution ID format
        result = await diagnose_func(mock_context, execution_id="invalid-execution-id")

        assert result["success"] is False, "Invalid execution ID should fail"
        assert "invalid execution id format" in result["error"].lower(), (
            "Should mention invalid format"
        )
        assert "troubleshooting" in result, "Should provide troubleshooting guidance"

        # Test with valid format but non-existent execution ID
        fake_execution_id = "12345678-1234-1234-1234-123456789012"
        result = await diagnose_func(mock_context, execution_id=fake_execution_id)

        # This should either succeed (if pipeline exists) or fail with appropriate error
        assert isinstance(result, dict), "Response should be a dictionary"
        assert "success" in result, "Response should have 'success' field"

        if not result["success"]:
            # If it fails, should be due to pipeline/execution not found, not validation
            assert "troubleshooting" in result, (
                "Failed response should have troubleshooting"
            )

    @pytest.mark.asyncio
    async def test_async_function_behavior(self, mock_context, registered_tools):
        """Test that all tools properly handle async execution and context usage.

        Requirements: 5.1 - Async function behavior validation
        """
        # Test all tools can be called concurrently
        tasks = []

        # Create concurrent calls to all tools
        tasks.append(registered_tools["getPipelineStatus"](mock_context))
        tasks.append(
            registered_tools["releasePipeline"](
                mock_context, pipeline_name="test-concurrent"
            )
        )
        tasks.append(registered_tools["diagnosePipelineErrors"](mock_context))

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all tasks completed (either successfully or with expected errors)
        assert len(results) == 3, "All tasks should complete"

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # If there's an exception, it should be a handled AWS error, not a programming error
                pytest.fail(f"Task {i} raised unexpected exception: {result}")
            else:
                # Should be a proper response dictionary
                assert isinstance(result, dict), f"Task {i} should return a dictionary"
                assert "success" in result, f"Task {i} should have 'success' field"

    @pytest.mark.asyncio
    async def test_context_usage_and_logging(self, registered_tools):
        """Test that tools properly use the MCP context for logging and feedback.

        Requirements: 5.1 - Context usage validation
        """
        # Create a mock context that tracks calls
        mock_context = Mock(spec=Context)

        # Test that context is passed to tools without errors
        get_status_func = registered_tools["getPipelineStatus"]
        result = await get_status_func(mock_context)

        # Verify the function completed and returned a result
        assert isinstance(result, dict), "Function should return a dictionary"
        assert "success" in result, "Response should have 'success' field"

        # The context should have been passed without causing errors
        # (We can't easily test logging calls without more complex mocking,
        # but we can verify the function accepts and uses the context parameter)

    @pytest.mark.asyncio
    async def test_error_handling_with_real_aws(self, mock_context, registered_tools):
        """Test error handling with real AWS service responses.

        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5 - Error handling
        """
        # Test with non-existent pipeline
        get_status_func = registered_tools["getPipelineStatus"]
        result = await get_status_func(
            mock_context, pipeline_name="definitely-does-not-exist-pipeline-12345"
        )

        # Should handle the error gracefully
        assert isinstance(result, dict), "Response should be a dictionary"
        assert "success" in result, "Response should have 'success' field"

        if not result["success"]:
            # Should provide proper error information
            assert "error" in result, "Failed response should have 'error' field"
            assert "troubleshooting" in result, (
                "Failed response should have 'troubleshooting' field"
            )
            assert isinstance(result["troubleshooting"], list), (
                "Troubleshooting should be a list"
            )
            assert len(result["troubleshooting"]) > 0, (
                "Should provide troubleshooting steps"
            )

            # Should include helpful guidance
            troubleshooting_text = " ".join(result["troubleshooting"]).lower()
            assert any(
                keyword in troubleshooting_text
                for keyword in ["credentials", "aws", "region", "permissions", "access"]
            ), "Should provide relevant troubleshooting guidance"


class TestPipelineToolsFixtures:
    """Test fixtures for various pipeline execution states."""

    @pytest.fixture
    def pipeline_execution_succeeded(self):
        """Fixture for a successful pipeline execution state."""
        return {
            "pipelineExecutionId": "12345678-1234-1234-1234-123456789012",
            "pipelineName": "test-pipeline",
            "pipelineVersion": 1,
            "status": "SUCCEEDED",
            "statusSummary": "Execution succeeded",
            "startTime": "2024-01-15T10:00:00Z",
            "lastUpdateTime": "2024-01-15T10:30:00Z",
        }

    @pytest.fixture
    def pipeline_execution_failed(self):
        """Fixture for a failed pipeline execution state."""
        return {
            "pipelineExecutionId": "87654321-4321-4321-4321-210987654321",
            "pipelineName": "test-pipeline",
            "pipelineVersion": 1,
            "status": "FAILED",
            "statusSummary": "Execution failed",
            "startTime": "2024-01-15T11:00:00Z",
            "lastUpdateTime": "2024-01-15T11:15:00Z",
        }

    @pytest.fixture
    def pipeline_execution_in_progress(self):
        """Fixture for an in-progress pipeline execution state."""
        return {
            "pipelineExecutionId": "11111111-2222-3333-4444-555555555555",
            "pipelineName": "test-pipeline",
            "pipelineVersion": 1,
            "status": "IN_PROGRESS",
            "statusSummary": "Execution in progress",
            "startTime": "2024-01-15T12:00:00Z",
            "lastUpdateTime": "2024-01-15T12:10:00Z",
        }

    @pytest.fixture
    def pipeline_with_stages(self):
        """Fixture for a pipeline with multiple stages."""
        return {
            "pipeline": {
                "name": "test-pipeline",
                "roleArn": "arn:aws:iam::123456789012:role/service-role/AWSCodePipelineServiceRole",
                "stages": [
                    {
                        "name": "Source",
                        "actions": [
                            {
                                "name": "SourceAction",
                                "actionTypeId": {
                                    "category": "Source",
                                    "owner": "AWS",
                                    "provider": "S3",
                                    "version": "1",
                                },
                            }
                        ],
                    },
                    {
                        "name": "Build",
                        "actions": [
                            {
                                "name": "BuildAction",
                                "actionTypeId": {
                                    "category": "Build",
                                    "owner": "AWS",
                                    "provider": "CodeBuild",
                                    "version": "1",
                                },
                            }
                        ],
                    },
                    {
                        "name": "Deploy",
                        "actions": [
                            {
                                "name": "DeployAction",
                                "actionTypeId": {
                                    "category": "Deploy",
                                    "owner": "AWS",
                                    "provider": "CloudFormation",
                                    "version": "1",
                                },
                            }
                        ],
                    },
                ],
            }
        }

    @pytest.fixture
    def codebuild_logs_sample(self):
        """Fixture for sample CodeBuild logs."""
        return {
            "builds": [
                {
                    "id": "test-project:12345678-1234-1234-1234-123456789012",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:build/test-project:12345678-1234-1234-1234-123456789012",
                    "buildNumber": 1,
                    "startTime": "2024-01-15T10:05:00Z",
                    "endTime": "2024-01-15T10:15:00Z",
                    "currentPhase": "COMPLETED",
                    "buildStatus": "FAILED",
                    "projectName": "test-project",
                    "logs": {
                        "groupName": "/aws/codebuild/test-project",
                        "streamName": "12345678-1234-1234-1234-123456789012",
                    },
                }
            ]
        }

    def test_fixture_data_validity(
        self,
        pipeline_execution_succeeded,
        pipeline_execution_failed,
        pipeline_execution_in_progress,
        pipeline_with_stages,
        codebuild_logs_sample,
    ):
        """Test that all fixtures contain valid data structures."""
        # Test successful execution fixture
        assert pipeline_execution_succeeded["status"] == "SUCCEEDED"
        assert "pipelineExecutionId" in pipeline_execution_succeeded
        assert "startTime" in pipeline_execution_succeeded

        # Test failed execution fixture
        assert pipeline_execution_failed["status"] == "FAILED"
        assert "pipelineExecutionId" in pipeline_execution_failed

        # Test in-progress execution fixture
        assert pipeline_execution_in_progress["status"] == "IN_PROGRESS"
        assert "pipelineExecutionId" in pipeline_execution_in_progress

        # Test pipeline structure fixture
        assert "pipeline" in pipeline_with_stages
        assert "stages" in pipeline_with_stages["pipeline"]
        assert len(pipeline_with_stages["pipeline"]["stages"]) == 3

        # Test CodeBuild logs fixture
        assert "builds" in codebuild_logs_sample
        assert len(codebuild_logs_sample["builds"]) == 1
        assert codebuild_logs_sample["builds"][0]["buildStatus"] == "FAILED"


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])
