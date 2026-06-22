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

"""CodeCommit implementation for putLzaConfiguration.

Commits all workspace files to a CodeCommit branch in a single CreateCommit
call.  Files that exist in the remote branch but are absent from the workspace
are included as deleteFiles entries, ensuring deletions are properly tracked.
Git records a diff only for files whose content actually changed, so the commit
history stays clean.
"""

import logging
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.config.codecommit_utils import (
    commit_files,
    list_all_files,
)
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


async def put_config_to_codecommit(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    path: str,
    matching_files: list,
    prefix: str,
    qualifier: Optional[str],
    cc_location: Any,
    commit_message: Optional[str],
) -> Dict[str, Any]:
    """Commit workspace files to a CodeCommit branch.

    Args:
        ctx: MCP context for progress reporting.
        workspace_manager: WorkspaceManager instance for file operations.
        workspace_id: Workspace containing the configuration files.
        path: Relative path within the workspace (for response metadata).
        matching_files: List of workspace file paths to commit.
        prefix: Path prefix to strip from file paths when building archive names.
        qualifier: Accelerator Qualifier (for response metadata only).
        cc_location: Resolved CodeCommit location (repository_name, branch, qualifier).
        commit_message: Commit message (auto-generated if None).

    Returns:
        Dictionary with commit results and metadata.
    """
    await ctx.info(
        f"CodeCommit destination: repo={cc_location.repository_name} "
        f"branch={cc_location.branch}"
    )

    # Build file dict: archive path → raw bytes
    files: Dict[str, bytes] = {}
    for file_path in matching_files:
        content = workspace_manager.read_file(workspace_id, file_path, ctx)
        arcname = file_path[len(prefix) :] if prefix else file_path
        if isinstance(content, str):
            content = content.encode("utf-8")
        files[arcname] = content

    message = commit_message or "Update LZA configuration via LZA MCP Server"

    try:
        # Determine which files were deleted from the workspace by comparing
        # the workspace contents against the current remote branch state.
        # A missing/empty branch simply means there is nothing to delete; any
        # other error (repo not found, access denied) is allowed to propagate
        # so the shared error handler below can map it to a clear message.
        delete_files: List[str] = []
        try:
            remote_file_list = list_all_files(
                repository_name=cc_location.repository_name,
                commit_specifier=cc_location.branch,
            )
            remote_paths = {abs_path for abs_path, _ in remote_file_list}
            workspace_paths = set(files.keys())
            delete_files = sorted(remote_paths - workspace_paths)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in (
                "BranchDoesNotExistException",
                "CommitDoesNotExistException",
            ):
                logger.info(
                    "Branch '%s' has no commits yet; skipping deletion detection",
                    cc_location.branch,
                )
            else:
                raise

        if delete_files:
            await ctx.info(
                f"Detected {len(delete_files)} stale file(s) to remove from the "
                f"remote branch"
            )
            logger.info("Files to delete: %s", delete_files)

        await ctx.info(
            f"Committing {len(files)} file(s) (putting {len(files)}, "
            f"deleting {len(delete_files)}) to "
            f"{cc_location.repository_name}/{cc_location.branch}..."
        )

        commit_result = commit_files(
            repository_name=cc_location.repository_name,
            branch=cc_location.branch,
            files=files,
            commit_message=message,
            delete_files=delete_files or None,
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "RepositoryDoesNotExistException":
            return create_structured_error_response(
                error="CodeCommit repository does not exist",
                category=ErrorCategory.CONFIGURATION,
                error_code="REPOSITORY_NOT_FOUND",
                troubleshooting=[
                    "Verify the repository name is correct",
                    "Check that the repository exists in your AWS account and region",
                    "Ensure codecommit:CreateCommit permission is granted",
                ],
                context={},
            )
        if error_code == "ParentCommitIdOutdatedException":
            return create_structured_error_response(
                error="Commit conflict: the branch has been updated since the last read",
                category=ErrorCategory.CONFIGURATION,
                error_code="COMMIT_CONFLICT",
                troubleshooting=[
                    "Re-run getLzaConfiguration() to get the latest version",
                    "Apply your changes again and retry putLzaConfiguration()",
                ],
                context={},
            )
        return create_structured_error_response(
            error=f"CodeCommit commit failed: {str(e)}",
            category=ErrorCategory.CONFIGURATION,
            error_code=error_code or "CODECOMMIT_ERROR",
            troubleshooting=[
                "Check AWS credentials and CodeCommit permissions",
                "Verify the repository and branch exist",
            ],
            context={},
        )

    await ctx.info(
        f"Committed to {cc_location.repository_name}/{cc_location.branch}: "
        f"{commit_result['commitId']}"
    )

    return {
        "success": True,
        "message": "Configuration committed to CodeCommit successfully",
        "workspace_id": workspace_id,
        "path": path,
        "config_source": "codecommit",
        "repository_name": cc_location.repository_name,
        "branch": cc_location.branch,
        "commit_id": commit_result["commitId"],
        "tree_id": commit_result["treeId"],
        "file_count": len(files),
        "files_deleted": len(delete_files),
        "qualifier": qualifier,
    }
