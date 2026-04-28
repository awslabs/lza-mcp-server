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

"""Retrieve LZA configuration for both standard and external pipeline deployments.

Orchestrates source selection (CodeCommit or S3) and workspace management.
Implementation details are in get_config_from_codecommit and get_config_from_s3.

Note: GetFolder returns at most 1000 entries per call.  LZA configuration
repositories are well within this limit in practice.
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager
from awslabs.lza_mcp_server.tools.config.config_codecommit_resolver import (
    resolve_codecommit_location,
)
from awslabs.lza_mcp_server.tools.config.get_config_from_codecommit import (
    get_config_from_codecommit,
)
from awslabs.lza_mcp_server.tools.config.get_config_from_s3 import get_config_from_s3
from awslabs.lza_mcp_server.tools.pipeline.common import validate_qualifier
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.input_validation import (
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


class LzaConfigRetrieval:
    """Retrieve and extract LZA configuration into a workspace.

    Supports two config sources:
    - S3 (default): downloads a ZIP from the LZA config bucket and extracts it.
    - CodeCommit: walks the repository tree with GetFolder/GetBlob and writes
      files directly into the workspace.

    Handles both standard and external pipeline (qualifier-based) deployments.
    Uses WorkspaceManager for all file operations.
    """

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        self.logger = logger
        self.s3_manager = S3Manager()
        self._workspace_manager = workspace_manager

    async def get_configuration(
        self,
        ctx: Context,
        qualifier: Optional[str] = None,
        bucket_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        path: Optional[str] = None,
        repository_name: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Download and extract LZA configuration into a workspace.

        Automatically selects the config source:
        - If repository_name is provided, or if the pipeline's source action is
          CodeCommit, files are fetched via GetFolder/GetBlob.
        - Otherwise, a ZIP is downloaded from S3 and extracted.

        Args:
            ctx: MCP context for progress reporting.
            qualifier: Accelerator Qualifier for external pipeline deployments.
                       Omit for standard (management account) deployments.
            bucket_name: Explicit S3 bucket name override (S3 source only).
            workspace_id: Optional workspace ID. If omitted a new workspace is
                          created automatically.
            path: Optional relative path within the workspace to extract into.
            repository_name: CodeCommit repository name override.
            branch: CodeCommit branch to read from (default: "main").

        Returns:
            Dictionary with extraction results, workspace_id, paths, and metadata.
        """
        created_workspace = False

        try:
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
                            "Bucket names must be 3-63 characters, lowercase, no spaces",
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

            # --- workspace resolution ---
            if workspace_id:
                try:
                    self._workspace_manager.list_files(workspace_id, ctx)
                except WorkspaceNotFoundError:
                    return create_structured_error_response(
                        error="Workspace not found",
                        category=ErrorCategory.CONFIGURATION,
                        error_code="WORKSPACE_NOT_FOUND",
                        troubleshooting=[
                            "Verify the workspace_id is correct",
                            "Use createWorkspace() to create a new workspace first",
                        ],
                        context={},
                    )
            else:
                workspace_id = self._workspace_manager.create_workspace(ctx)
                created_workspace = True
                await ctx.info(f"Created new workspace: {workspace_id}")

            # --- source selection: CodeCommit or S3 ---
            cc_location = resolve_codecommit_location(
                qualifier=qualifier,
                repository_name=repository_name,
                branch=branch,
            )

            if cc_location:
                return await get_config_from_codecommit(
                    ctx=ctx,
                    workspace_manager=self._workspace_manager,
                    workspace_id=workspace_id,
                    created_workspace=created_workspace,
                    path=path,
                    qualifier=qualifier,
                    cc_location=cc_location,
                )

            return await get_config_from_s3(
                ctx=ctx,
                workspace_manager=self._workspace_manager,
                s3_manager=self.s3_manager,
                workspace_id=workspace_id,
                created_workspace=created_workspace,
                path=path,
                qualifier=qualifier,
                bucket_name=bucket_name,
            )

        except (WorkspaceValidationError, WorkspaceStorageError) as e:
            self.logger.error("Workspace operation failed: %s", str(e))
            return create_structured_error_response(
                error=f"Workspace operation failed: {str(e)}",
                category=ErrorCategory.CONFIGURATION,
                error_code="WORKSPACE_ERROR",
                troubleshooting=[
                    "Check workspace storage is accessible",
                    "Verify workspace_id is valid",
                ],
                context={},
            )
        except Exception as e:
            self.logger.error("Configuration retrieval failed: %s", str(e))
            return create_structured_error_response(
                error=f"Configuration retrieval failed: {str(e)}",
                category=ErrorCategory.S3,
                error_code="RETRIEVAL_ERROR",
                troubleshooting=[
                    "Check AWS credentials and permissions",
                    "Verify network connectivity",
                    "Ensure sufficient disk space",
                ],
                context={},
            )
