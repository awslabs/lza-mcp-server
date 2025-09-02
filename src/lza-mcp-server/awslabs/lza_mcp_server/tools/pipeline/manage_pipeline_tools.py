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

"""CodePipeline-related MCP tools for the LZA MCP Server."""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from ...constants import (
    CACHE_TTL_SECONDS,
    MAX_LOG_SIZE,
    DEFAULT_REGION,
    DEFAULT_PIPELINE_NAME,
)
from .release_pipeline import tool_release_pipeline
from .get_pipeline_status import tool_get_pipeline_status
from .diagnose_pipeline_errors import tool_diagnose_pipeline_errors
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)

_pipeline_cache = {}
_cache_timestamps = {}


def is_cache_valid(cache_key: str) -> bool:
    """Check if a cache entry is still valid based on TTL.

    Args:
        cache_key: The cache key to check

    Returns:
        bool: True if cache entry is valid, False otherwise
    """
    if cache_key not in _cache_timestamps:
        return False

    cache_time = _cache_timestamps[cache_key]
    current_time = datetime.now()
    return (current_time - cache_time).total_seconds() < CACHE_TTL_SECONDS


def get_cached_pipeline_metadata(pipeline_name: str) -> Optional[Dict[str, Any]]:
    """Get cached pipeline metadata if available and valid.

    Args:
        pipeline_name: Name of the pipeline

    Returns:
        Dict containing cached pipeline metadata or None if not cached/expired
    """
    cache_key = f"pipeline_metadata_{pipeline_name}"

    if is_cache_valid(cache_key) and cache_key in _pipeline_cache:
        logger.debug(f"Using cached pipeline metadata for: {pipeline_name}")
        return _pipeline_cache[cache_key]

    return None


def cache_pipeline_metadata(pipeline_name: str, metadata: Dict[str, Any]) -> None:
    """Cache pipeline metadata with timestamp.

    Args:
        pipeline_name: Name of the pipeline
        metadata: Pipeline metadata to cache
    """
    cache_key = f"pipeline_metadata_{pipeline_name}"
    _pipeline_cache[cache_key] = metadata
    _cache_timestamps[cache_key] = datetime.now()
    logger.debug(f"Cached pipeline metadata for: {pipeline_name}")


def clear_pipeline_cache() -> None:
    """Clear all cached pipeline metadata. Useful for testing."""
    global _pipeline_cache, _cache_timestamps
    _pipeline_cache.clear()
    _cache_timestamps.clear()


def truncate_logs(logs_content: str, max_size: int = MAX_LOG_SIZE) -> str:
    """Truncate log content to prevent memory issues while preserving important information.

    Args:
        logs_content: The full log content
        max_size: Maximum size in characters

    Returns:
        str: Truncated log content with truncation notice if applicable
    """
    if len(logs_content) <= max_size:
        return logs_content

    keep_size = max_size // 2 - 100  # Reserve space for truncation message

    first_part = logs_content[:keep_size]
    last_part = logs_content[-keep_size:]

    truncation_message = f"\n\n... [TRUNCATED: {len(logs_content) - (2 * keep_size)} characters removed] ...\n\n"

    return first_part + truncation_message + last_part


def format_success_response(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Format a successful response with consistent structure.

    Args:
        data: The response data to include
        message: Success message to include

    Returns:
        Dict containing success=True, message, and the provided data
    """
    response = {"success": True, "message": message}
    response.update(data)
    return response


def validate_pipeline_name(pipeline_name: str) -> tuple[bool, str]:
    """Validate that a pipeline name meets AWS CodePipeline naming requirements.

    Args:
        pipeline_name: The pipeline name to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not pipeline_name:
        return False, "Pipeline name cannot be empty"

    if not isinstance(pipeline_name, str):
        return False, "Pipeline name must be a string"

    # AWS CodePipeline naming rules:
    # - Must be 1-100 characters
    # - Can contain letters, numbers, periods, underscores, and hyphens
    # - Cannot contain spaces or other special characters
    if len(pipeline_name) < 1:
        return False, "Pipeline name cannot be empty"

    if len(pipeline_name) > 100:
        return (
            False,
            f"Pipeline name too long ({len(pipeline_name)} characters). Maximum is 100 characters",
        )

    # Check for valid characters
    import re

    if not re.match(r"^[a-zA-Z0-9._-]+$", pipeline_name):
        invalid_chars = set(pipeline_name) - set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        return (
            False,
            f"Pipeline name contains invalid characters: {', '.join(sorted(invalid_chars))}. Only letters, numbers, periods, underscores, and hyphens are allowed",
        )

    return True, ""


def validate_execution_id(execution_id: str) -> tuple[bool, str]:
    """Validate that an execution ID meets AWS CodePipeline execution ID format.

    Args:
        execution_id: The execution ID to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not execution_id:
        return False, "Execution ID cannot be empty"

    if not isinstance(execution_id, str):
        return False, "Execution ID must be a string"

    # AWS execution IDs are UUIDs (36 characters with hyphens)
    import re

    uuid_pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )

    if not re.match(uuid_pattern, execution_id):
        return (
            False,
            f"Invalid execution ID format. Expected UUID format (e.g., 12345678-1234-1234-1234-123456789012), got: {execution_id}",
        )

    return True, ""


def get_stage_description(stage_name: str) -> str:
    """Get a description of what happens in a specific LZA pipeline stage.

    Args:
        stage_name: Name of the pipeline stage

    Returns:
        str: Description of what the stage does
    """
    stage_descriptions = {
        "Source": "Retrieves LZA source code from GitHub and configuration files from the aws-accelerator-config repository",
        "Build": "Transpiles the LZA source code and performs input/type validation for configuration files",
        "Prepare": "Creates and validates AWS accounts, generates accounts via Control Tower Account Factory, and creates/validates OUs",
        "Accounts": "Validates all accounts are part of the AWS Organization and creates/attaches Service Control Policies (SCPs)",
        "Bootstrap": "Runs AWS CDK bootstrap to initialize environments and deploys CDK toolkit CloudFormation templates",
        "Review": "Runs CDK diff against target accounts and provides manual approval gate for changes (optional stage)",
        "Logging": "Deploys centralized KMS keys, logging infrastructure, S3 buckets, Kinesis streams, and Data Firehose",
        "Organization": "Deploys AWS Organization-wide resources like trusted services, policies, Cost and Usage Reports, and Budgets",
        "SecurityAudit": "Deploys security service dependencies for Macie, GuardDuty, Security Hub in the audit account",
        "Security_Audit": "Deploys security service dependencies for Macie, GuardDuty, Security Hub in the audit account",
        "Deploy": "Deploys infrastructure across multiple sub-actions including networking, security, operations, and customizations",
    }

    return stage_descriptions.get(stage_name, f"Stage: {stage_name}")


def get_action_description(action_name: str) -> str:
    """Get a description of what happens in a specific LZA pipeline action.

    Args:
        action_name: Name of the pipeline action

    Returns:
        str: Description of what the action does
    """
    action_descriptions = {
        "Network_Prepare": "Creates Transit Gateway and RAM shares",
        "Security": "Configures member account security services",
        "Operations": "Deploys users, groups, roles, and SAML providers",
        "Network_VPCs": "Deploys VPCs, subnets, endpoints, and DNS resources",
        "Security_Resources": "Deploys Config, CloudWatch metrics, and alarms",
        "Network_Associations": "Creates network associations and Gateway Load Balancer endpoints",
        "Customizations": "Deploys custom CloudFormation stacks/stacksets (optional)",
        "Finalize": "Removes quarantine SCPs from new accounts",
    }

    return action_descriptions.get(action_name, f"Action: {action_name}")


def extract_create_failed_error(logs_content: str) -> str:
    """Extract the first CREATE_FAILED error from CodeBuild logs.

    This focuses specifically on CloudFormation CREATE_FAILED errors which are
    the most actionable for LZA troubleshooting.

    Args:
        logs_content: The full build log content

    Returns:
        str: The first CREATE_FAILED line found, or None if none found
    """
    if not logs_content:
        return None

    lines = logs_content.split("\n")

    # Look specifically for CREATE_FAILED lines
    for line in lines:
        if "CREATE_FAILED" in line:
            clean_line = line.strip()
            if clean_line:
                return clean_line

    return None


def extract_error_line(logs_content: str) -> str:
    """Extract the first '| error |' line from CodeBuild logs.

    This searches for general error patterns when CloudFormation CREATE_FAILED
    errors are not found, providing additional error detection capability.

    Args:
        logs_content: The full build log content

    Returns:
        str: The first '| error |' line found, or None if none found
    """
    if not logs_content:
        return None

    lines = logs_content.split("\n")

    # Look specifically for '| error |' lines
    for line in lines:
        if "| error |" in line:
            clean_line = line.strip()
            if clean_line:
                return clean_line

    return None


def register_pipeline_tools(mcp):
    """Register CodePipeline-related MCP tools.

    This function will be called by the main server to register all pipeline tools.

    Args:
        mcp: The FastMCP server instance to register tools with
    """

    @mcp.tool(
        name="releasePipeline",
        description="Start the LZA pipeline execution to deploy configuration changes",
    )  # nosemgrep: useless-inner-function
    async def release_pipeline(
        ctx: Context, pipeline_name: str = DEFAULT_PIPELINE_NAME
    ) -> Dict[str, Any]:
        return await tool_release_pipeline(ctx, pipeline_name)

    @mcp.tool(
        name="getPipelineStatus",
        description="Get current pipeline status and execution progress with detailed stage information",
    )  # nosemgrep: useless-inner-function
    async def get_pipeline_status(
        ctx: Context,
        pipeline_name: str = DEFAULT_PIPELINE_NAME,
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await tool_get_pipeline_status(ctx, pipeline_name, execution_id)

    @mcp.tool(
        name="diagnosePipelineErrors",
        description="Retrieve detailed error logs and diagnostics for failed pipeline executions",
    )  # nosemgrep: useless-inner-function
    async def diagnose_pipeline_errors(
        ctx: Context,
        pipeline_name: str = DEFAULT_PIPELINE_NAME,
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await tool_diagnose_pipeline_errors(ctx, pipeline_name, execution_id)


def validate_aws_region(region: str) -> tuple[bool, str]:
    """Validate that an AWS region meets AWS region naming requirements.

    Args:
        region: The AWS region to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not region:
        return False, "AWS region cannot be empty"

    if not isinstance(region, str):
        return False, "AWS region must be a string"

    # AWS region format: us-east-1, eu-west-1, ap-southeast-2, etc.
    import re

    region_pattern = r"^[a-z]{2,3}-[a-z]+-[0-9]+$"

    if not re.match(region_pattern, region):
        return (
            False,
            f"Invalid AWS region format. Expected format like 'us-east-1', got: {region}",
        )

    return True, ""
