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

"""Upload LZA configuration for both standard and external pipeline deployments.

Orchestrates destination selection (CodeCommit or S3) and input validation.
Implementation details are in put_config_to_codecommit and put_config_to_s3.
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.config.config_codecommit_resolver import (
    resolve_codecommit_location,
)
from awslabs.lza_mcp_server.tools.config.put_config_to_codecommit import (
    put_config_to_codecommit,
)
from awslabs.lza_mcp_server.tools.config.put_config_to_s3 import put_config_to_s3
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_qualifier,
    validate_s3_bucket_name,
    validate_string_input,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)

logger = logging.getLogger(__name__)


async def tool_put_lza_configuration(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    qualifier: Optional[str] = None,
    bucket_name: Optional[str] = None,
    repository_name: Optional[str] = None,
    branch: Optional[str] = None,
    commit_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload LZA configuration from a workspace to S3 or CodeCommit.

    Automatically selects the destination:
    - If repository_name is provided, or if the pipeline's source action is
      CodeCommit, files are committed via CreateCommit.
    - Otherwise, a ZIP is created and uploaded to S3.

    Args:
        ctx: MCP context for logging and progress.
        workspace_manager: WorkspaceManager instance for file operations.
        workspace_id: Workspace containing the configuration files.
        path: Relative path within the workspace where config files reside.
        qualifier: Accelerator Qualifier for external pipeline deployments.
        bucket_name: Explicit S3 bucket name override (S3 destination only).
        repository_name: CodeCommit repository name override.
        branch: CodeCommit branch to commit to (default: "main").
        commit_message: Commit message for CodeCommit (default: auto-generated).

    Returns:
        Dictionary with upload/commit results.
    """
    try:
        if path in ("/", "."):
            path = ""

        await ctx.info("Starting LZA configuration upload...")

        # --- input validation ---
        if qualifier:
            is_valid, err = validate_qualifier(qualifier)
            if not is_valid:
                return create_structured_error_response(
                    error=f"Invalid qualifier: {err}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_QUALIFIER",
                    troubleshooting=[
                        "Qualifier must contain only lowercase letters, numbers, and hyphens",
                        "Run checkAwsConnectivity() to see available qualifiers",
                    ],
                    context={},
                )

        if bucket_name:
            is_valid, err = validate_s3_bucket_name(bucket_name)
            if not is_valid:
                return create_structured_error_response(
                    error=f"Invalid bucket name: {err}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_BUCKET_NAME",
                    troubleshooting=[
                        "Bucket names must be 3-63 characters, lowercase",
                        "Must start and end with a letter or number",
                    ],
                    context={},
                )

        if repository_name:
            is_valid, err = validate_string_input(
                repository_name, "repository_name", min_length=1, max_length=100
            )
            if not is_valid:
                return create_structured_error_response(
                    error=f"Invalid repository name: {err}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_REPOSITORY_NAME",
                    troubleshooting=["Repository name must be 1-100 characters"],
                    context={},
                )

        if branch:
            is_valid, err = validate_string_input(
                branch, "branch", min_length=1, max_length=256
            )
            if not is_valid:
                return create_structured_error_response(
                    error="Invalid branch name",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="INVALID_BRANCH_NAME",
                    troubleshooting=["Branch name must be 1-256 characters"],
                    context={},
                )

        # --- validate workspace ---
        try:
            workspace_manager.list_files(workspace_id, ctx)
        except WorkspaceNotFoundError:
            return create_structured_error_response(
                error="Workspace not found",
                category=ErrorCategory.CONFIGURATION,
                error_code="WORKSPACE_NOT_FOUND",
                troubleshooting=[
                    "Verify the workspace_id is correct",
                    "Use getLzaConfiguration() to download config into a workspace first",
                ],
                context={},
            )

        # --- verify workspace has config files ---
        all_files = workspace_manager.list_files(workspace_id, ctx)
        prefix = path.rstrip("/") + "/" if path else ""
        matching_files = [f for f in all_files if f.startswith(prefix) or not prefix]

        if not matching_files:
            return create_structured_error_response(
                error="No configuration files found in workspace",
                category=ErrorCategory.CONFIGURATION,
                error_code="EMPTY_CONFIGURATION",
                troubleshooting=[
                    "Verify the workspace contains LZA configuration files",
                    "Use getLzaConfiguration() to download config first",
                    "Check the path parameter points to the correct location",
                ],
                context={},
            )

        # --- destination selection: CodeCommit or S3 ---
        cc_location = resolve_codecommit_location(
            qualifier=qualifier,
            repository_name=repository_name,
            branch=branch,
        )

        if cc_location:
            return await put_config_to_codecommit(
                ctx=ctx,
                workspace_manager=workspace_manager,
                workspace_id=workspace_id,
                path=path,
                matching_files=matching_files,
                prefix=prefix,
                qualifier=qualifier,
                cc_location=cc_location,
                commit_message=commit_message,
            )

        return await put_config_to_s3(
            ctx=ctx,
            workspace_manager=workspace_manager,
            workspace_id=workspace_id,
            path=path,
            matching_files=matching_files,
            qualifier=qualifier,
            bucket_name=bucket_name,
        )

    except (WorkspaceValidationError, WorkspaceStorageError) as e:
        logger.error("Workspace operation failed: %s", str(e))
        return create_structured_error_response(
            error=f"Workspace operation failed: {str(e)}",
            category=ErrorCategory.CONFIGURATION,
            error_code="WORKSPACE_ERROR",
            troubleshooting=[
                "Check workspace storage is accessible",
                "Verify workspace_id and path are valid",
            ],
            context={},
        )
    except Exception as e:
        logger.error("putLzaConfiguration failed: %s", str(e))
        return create_structured_error_response(
            error=f"Upload failed: {str(e)}",
            category=ErrorCategory.INTEGRATION,
            error_code="UPLOAD_ERROR",
            troubleshooting=[
                "Check AWS credentials and permissions",
                "Verify network connectivity",
            ],
            context={},
        )
