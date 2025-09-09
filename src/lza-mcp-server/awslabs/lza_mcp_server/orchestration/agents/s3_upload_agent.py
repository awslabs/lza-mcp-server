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

"""S3 Configuration Upload tools for the LZA MCP Server."""

import logging
import os
import re
from typing import Dict, Any, Optional, List

from awslabs.lza_mcp_server.constants import DEFAULT_REGION, S3_OBJECT_KEY
from awslabs.lza_mcp_server.orchestration.agents.base_agent import (
    BaseAgent,
    AgentCapability,
)

# MCP framework components

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


# Strands Framework Integration
async def _execute_upload_tool(tool_func, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an S3 upload tool function.

    Args:
        tool_func: The tool function to execute
        parameters: Parameters to pass to the tool
    Returns:
        Result from the tool function
    """
    # Create a mock context for the tool call
    mock_ctx = type(
        "MockContext",
        (),
        {
            "info": lambda msg: logger.info(msg),
            "error": lambda msg: logger.error(msg),
            "warning": lambda msg: logger.warning(msg),
        },
    )()

    # Call the tool function with parameters
    if parameters:
        result = await tool_func(mock_ctx, **parameters)
    else:
        result = await tool_func(mock_ctx)

    return result


async def _generate_deployment_guidance(
    upload_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate deployment guidance after successful upload.

    Args:
        upload_result: Result from successful S3 upload

    Returns:
        Dictionary containing deployment guidance
    """
    return {
        "upload_summary": {
            "bucket": upload_result.get("bucket_name"),
            "object_key": upload_result.get("object_key", S3_OBJECT_KEY),
            "upload_size": upload_result.get("upload_size"),
            "upload_time": upload_result.get("execution_time"),
        },
        "deployment_readiness": [
            "Configuration successfully uploaded to S3",
            "Ready for LZA pipeline deployment",
            "Consider releasing the pipeline to start deployment",
        ],
        "verification_steps": [
            "Verify the uploaded configuration in S3 console",
            "Check that all required configuration files are included",
            "Ensure the zip file structure is correct for LZA deployment",
        ],
    }


async def _generate_next_steps(upload_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate recommended next steps after upload.

    Args:
        upload_result: Result from successful S3 upload

    Returns:
        List of recommended next steps
    """
    steps = [
        {
            "step": "Verify Upload",
            "description": "Confirm the configuration was uploaded correctly",
            "actions": [
                "Check S3 bucket for the uploaded configuration",
                "Verify the zip file contains all expected configuration files",
                "Ensure file permissions are correct for LZA access",
            ],
            "tools": ["AWS S3 Console", "AWS CLI"],
        }
    ]

    # Add pipeline release step if not already done
    if not upload_result.get("pipeline_release_accepted"):
        steps.append(
            {
                "step": "Release Pipeline",
                "description": "Start the LZA deployment pipeline",
                "actions": [
                    "Use releasePipelineAfterUpload tool to start deployment",
                    "Monitor pipeline execution in CodePipeline console",
                    "Review deployment logs for any issues",
                ],
                "tools": ["releasePipelineAfterUpload", "AWS CodePipeline Console"],
            }
        )

    steps.extend(
        [
            {
                "step": "Monitor Deployment",
                "description": "Track the deployment progress",
                "actions": [
                    "Monitor CloudFormation stack creation/updates",
                    "Check CloudWatch logs for deployment progress",
                    "Verify resources are created as expected",
                ],
                "tools": ["AWS CloudFormation Console", "AWS CloudWatch"],
            },
            {
                "step": "Validate Deployment",
                "description": "Ensure the deployment completed successfully",
                "actions": [
                    "Verify all accounts are created and configured",
                    "Check that security controls are in place",
                    "Validate network configurations are applied",
                ],
                "tools": ["AWS Organizations Console", "AWS Config Console"],
            },
        ]
    )

    return steps


def _generate_monitoring_recommendations() -> List[Dict[str, Any]]:
    """Generate monitoring recommendations for deployment.

    Returns:
        List of monitoring recommendations
    """
    return [
        {
            "category": "Pipeline Monitoring",
            "recommendations": [
                "Monitor CodePipeline execution status",
                "Set up CloudWatch alarms for pipeline failures",
                "Review pipeline execution history regularly",
            ],
        },
        {
            "category": "Resource Monitoring",
            "recommendations": [
                "Monitor CloudFormation stack events",
                "Track resource creation and configuration",
                "Set up billing alerts for cost monitoring",
            ],
        },
        {
            "category": "Security Monitoring",
            "recommendations": [
                "Monitor AWS Config compliance status",
                "Review CloudTrail logs for security events",
                "Set up GuardDuty for threat detection",
            ],
        },
    ]


async def _generate_pipeline_monitoring_guidance(
    pipeline_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate pipeline monitoring guidance after release.

    Args:
        pipeline_result: Result from pipeline release

    Returns:
        Dictionary containing pipeline monitoring guidance
    """
    return {
        "execution_details": {
            "pipeline_name": pipeline_result.get("pipeline_name"),
            "execution_id": pipeline_result.get("execution_id"),
            "start_time": pipeline_result.get("start_time"),
            "status": "RUNNING",
        },
        "monitoring_actions": [
            "Check pipeline status in AWS CodePipeline console",
            "Monitor individual stage execution progress",
            "Review logs for any errors or warnings",
            "Track CloudFormation stack updates",
        ],
        "expected_duration": "30-60 minutes for typical LZA deployment",
        "console_links": {
            "codepipeline": f"https://console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipeline_result.get('pipeline_name')}/view",
            "cloudformation": "https://console.aws.amazon.com/cloudformation/home",
        },
    }


async def _generate_deployment_tracking_info() -> Dict[str, Any]:
    """Generate deployment tracking information.

    Args:

    Returns:
        Dictionary containing deployment tracking information
    """
    return {
        "tracking_methods": [
            "AWS CodePipeline console for overall progress",
            "CloudFormation console for stack updates",
            "CloudWatch logs for detailed execution logs",
            "AWS Config for compliance tracking",
        ],
        "key_milestones": [
            "Source stage: Configuration retrieved from S3",
            "Build stage: Configuration validation and processing",
            "Deploy stage: CloudFormation stack deployment",
            "Completion: All resources created and configured",
        ],
        "troubleshooting_resources": [
            "Check CloudFormation events for stack failures",
            "Review CodeBuild logs for build issues",
            "Monitor CloudWatch logs for runtime errors",
            "Verify IAM permissions for deployment roles",
        ],
    }


async def _handle_upload_error(error: Exception, tool_name: str) -> Dict[str, Any]:
    """Handle S3 upload and deployment-specific errors with appropriate guidance.

    Args:
        error: The exception that occurred
        tool_name: Name of the tool that failed

    Returns:
        Dictionary containing error details and troubleshooting guidance
    """
    error_message = str(error)

    # Handle common S3 upload errors
    if "access denied" in error_message.lower() or "forbidden" in error_message.lower():
        return {
            "success": False,
            "error": error_message,
            "message": f"S3 access denied for {tool_name}",
            "error_type": "s3_access_denied",
            "troubleshooting": [
                "Verify AWS credentials have S3 permissions",
                "Check that the S3 bucket exists and is accessible",
                "Ensure IAM policies allow s3:PutObject and s3:GetObject",
                "Verify the bucket is in the correct AWS region",
            ],
        }

    elif "bucket" in error_message.lower() and "not found" in error_message.lower():
        return {
            "success": False,
            "error": error_message,
            "message": f"S3 bucket not found for {tool_name}",
            "error_type": "bucket_not_found",
            "troubleshooting": [
                "Verify the S3 bucket name is correct",
                "Check that the bucket exists in your AWS account",
                "Ensure you're using the correct AWS region",
                "Create the bucket if it doesn't exist",
            ],
        }

    elif "pipeline" in error_message.lower():
        return {
            "success": False,
            "error": error_message,
            "message": f"CodePipeline error in {tool_name}",
            "error_type": "pipeline_error",
            "troubleshooting": [
                "Verify the CodePipeline exists and is accessible",
                "Check IAM permissions for CodePipeline operations",
                "Ensure the pipeline is not already running",
                "Verify the pipeline configuration is correct",
            ],
        }

    elif "configuration" in error_message.lower() or "config" in error_message.lower():
        return {
            "success": False,
            "error": error_message,
            "message": f"Configuration error in {tool_name}",
            "error_type": "configuration_error",
            "troubleshooting": [
                "Verify the configuration folder contains valid LZA files",
                "Check that all required configuration files are present",
                "Ensure configuration files have correct YAML syntax",
                "Validate configuration using validation tools first",
            ],
        }

    else:
        return {
            "success": False,
            "error": error_message,
            "message": f"Unexpected error in {tool_name}",
            "error_type": "unexpected",
            "troubleshooting": [
                "Check application logs for more detailed error information",
                "Verify AWS connectivity and credentials",
                "Ensure all required dependencies are available",
                "Contact support if the issue persists",
            ],
        }


def _get_specific_operation_guidance(operation_type: str) -> List[str]:
    """Get specific guidance for an upload operation type.

    Args:
        operation_type: The operation type to get guidance for

    Returns:
        List of guidance items for the operation type
    """
    guidance_map = {
        "standard_upload": [
            "Automatically detects the correct S3 bucket based on AWS account and region",
            "Requires AWS connectivity to determine bucket name",
            "Uses the standard LZA bucket naming convention",
        ],
        "custom_bucket_upload": [
            "Allows specifying a custom S3 bucket name",
            "Useful when using non-standard bucket names",
            "Requires the bucket to exist and be accessible",
        ],
        "pipeline_release": [
            "Starts the LZA deployment pipeline after successful upload",
            "Requires CodePipeline permissions",
            "Monitors pipeline execution and provides status updates",
        ],
    }

    return guidance_map.get(
        operation_type,
        [
            "Review the operation requirements and prerequisites",
            "Ensure all necessary permissions are in place",
            "Monitor the operation progress and handle any errors",
        ],
    )


async def _enhance_upload_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance S3 upload results with deployment guidance and next steps.

    Args:
        result: Original result from upload operation
    Returns:
        Enhanced result with additional deployment guidance
    """
    if not result.get("success"):
        return result

    # Add deployment guidance
    result["deployment_guidance"] = await _generate_deployment_guidance(result)

    # Add next steps recommendations
    result["next_steps"] = await _generate_next_steps(result)

    # Add monitoring recommendations
    result["monitoring_recommendations"] = _generate_monitoring_recommendations()

    return result


async def _enhance_pipeline_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance pipeline release results with monitoring and tracking information.

    Args:
        result: Original result from pipeline release

    Returns:
        Enhanced result with additional monitoring information
    """
    if not result.get("success"):
        return result

    # Add pipeline monitoring guidance
    result["pipeline_monitoring"] = await _generate_pipeline_monitoring_guidance(result)

    # Add deployment tracking information
    result["deployment_tracking"] = await _generate_deployment_tracking_info()

    return result


class S3UploadAgent(BaseAgent):
    """Agent responsible for S3 configuration upload operations in the Strands orchestration system.

    This agent handles S3 upload operations, configuration management, and pipeline release
    functionality. It provides intelligent assistance for uploading validated LZA configurations
    to S3 buckets and integrating with deployment workflows.
    """

    def __init__(self):
        """Initialize the S3 Upload Agent with upload and deployment capabilities."""
        capabilities = [
            AgentCapability(
                name="s3_upload",
                description="Upload validated LZA configurations to S3 buckets",
                tools=[
                    "uploadConfigurationToS3",
                ],
                expertise_domain="configuration_deployment",
            ),
            AgentCapability(
                name="pipeline_release",
                description="Release CodePipeline after successful configuration upload",
                tools=["releasePipelineAfterUpload"],
                expertise_domain="deployment_automation",
            ),
        ]

        super().__init__(name="s3_upload_agent", capabilities=capabilities)

        # S3 upload-specific settings
        self.upload_keywords = [
            "upload",
            "s3",
            "deploy",
            "configuration",
            "config",
            "bucket",
            "pipeline",
            "release",
            "deployment",
            "zip",
            "archive",
        ]

        # Upload operation patterns
        self.upload_patterns = {
            "bucket_name": r"aws-accelerator-config-\d+-[a-z0-9-]+",
            "s3_uri": r"s3://[a-zA-Z0-9.\-_]+/.*",
            "config_path": r".*config.*\.yaml$",
        }

        # Supported upload operations
        self.upload_operations = {
            "standard_upload": "Upload configuration using auto-detected bucket name",
            "custom_bucket_upload": "Upload configuration to a specified S3 bucket",
            "pipeline_release": "Release CodePipeline after successful upload",
        }

    def set_tool_registry(self, tool_registry: Dict[str, Any]) -> None:
        """Set the tool registry for this agent (required by orchestration framework).

        Args:
            tool_registry: Dictionary mapping tool names to tool functions
        """
        self.tool_registry = tool_registry
        logger.info(
            f"S3 Upload agent tool registry set with {len(tool_registry)} tools"
        )

    async def start(self) -> None:
        """Start the agent (required by orchestration framework).

        This method is called by the orchestration framework to initialize
        the agent for task execution.
        """
        logger.info(f"S3 Upload agent '{self.name}' started successfully")
        # No additional startup logic needed for this agent

    async def run(self) -> None:
        """Run the agent task processing loop (required by orchestration framework).

        This method is called by the orchestration framework to start the agent's
        main processing loop. For this agent, we don't need a continuous loop
        since tasks are executed on-demand.
        """
        logger.info(f"S3 Upload agent '{self.name}' running and ready for tasks")
        # This agent processes tasks on-demand, so no continuous loop needed
        # The orchestration framework will call execute_task() when needed

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an S3 upload or pipeline release task.

        Args:
            task: Dictionary containing:
                - tool_name: Name of the tool to execute
                - parameters: Parameters to pass to the tool
                - context: Additional context for task execution

        Returns:
            Dictionary containing task execution results with upload details
        """
        if not await self.validate_task(task):
            return {
                "success": False,
                "error": "Invalid task format or missing required fields",
                "message": "Task validation failed",
            }

        tool_name = task["tool_name"]
        parameters = task.get("parameters", {})
        task.get("context", {})

        logger.info(f"S3 Upload agent executing task: {tool_name}")

        try:
            # Get the tool function from registry
            tool_func = self.tool_registry[tool_name]

            # Execute the S3 upload tool
            result = await _execute_upload_tool(tool_func, parameters)

            # Add upload guidance and deployment assistance
            if tool_name in [
                "uploadConfigurationToS3",
            ]:
                result = await _enhance_upload_result(result)
            elif tool_name == "releasePipelineAfterUpload":
                result = await _enhance_pipeline_result(result)

            logger.info(f"Task {tool_name} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Task {tool_name} failed: {str(e)}")
            return await _handle_upload_error(e, tool_name)

    def can_handle(self, query: str) -> float:
        """Determine confidence score for handling S3 upload and deployment queries.

        Args:
            query: User query or task description

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not query or not isinstance(query, str):
            return 0.0

        query_lower = query.lower()

        # High confidence patterns for S3 upload operations
        high_confidence_patterns = [
            r"upload.*s3",
            r"upload.*config",
            r"deploy.*config",
            r"s3.*upload",
            r"bucket.*upload",
            r"release.*pipeline",
            r"pipeline.*release",
            r"configuration.*upload",
            r"config.*deployment",
        ]

        for pattern in high_confidence_patterns:
            if re.search(pattern, query_lower):
                return 0.9

        # Medium confidence for upload-related keywords
        keyword_matches = sum(
            1 for keyword in self.upload_keywords if keyword in query_lower
        )
        if keyword_matches >= 2:
            return 0.7
        elif keyword_matches == 1:
            return 0.4

        # Check for specific S3 or deployment terms
        s3_deployment_terms = [
            "s3",
            "bucket",
            "deploy",
            "pipeline",
            "release",
            "upload",
        ]
        s3_matches = sum(1 for term in s3_deployment_terms if term in query_lower)
        if s3_matches > 0:
            return 0.6

        # Low confidence for general deployment terms
        general_patterns = [r"deploy", r"upload", r"release", r"publish"]

        for pattern in general_patterns:
            if re.search(pattern, query_lower):
                return 0.2

        return 0.0

    def get_upload_guidance(
        self, operation_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get specific guidance for S3 upload operations.

        Args:
            operation_type: Optional specific operation type

        Returns:
            Dictionary containing upload guidance
        """
        if operation_type and operation_type in self.upload_operations:
            return {
                "operation_type": operation_type,
                "description": self.upload_operations[operation_type],
                "guidance": _get_specific_operation_guidance(operation_type),
            }
        else:
            return {
                "available_operations": self.upload_operations,
                "general_guidance": [
                    "Ensure configurations are validated before uploading",
                    "Verify AWS connectivity and S3 permissions",
                    "Use appropriate bucket names for your deployment",
                    "Monitor upload progress and verify completion",
                ],
            }


# Agent registration function for Strands framework integration
def register_s3_upload_agent(orchestrator) -> S3UploadAgent:
    """Register the S3 Upload Agent with the Strands orchestration framework.

    Args:
        orchestrator: The Strands orchestrator instance

    Returns:
        The registered S3UploadAgent instance
    """
    agent = S3UploadAgent()
    orchestrator.register_agent(agent)
    logger.info("S3 Upload Agent registered with Strands orchestration framework")
    return agent
