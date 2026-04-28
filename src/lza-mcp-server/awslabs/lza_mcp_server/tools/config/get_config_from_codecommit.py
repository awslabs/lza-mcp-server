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

"""CodeCommit implementation for getLzaConfiguration.

Fetches all files from a CodeCommit repository branch using GetFolder/GetBlob
and writes them into a workspace.
"""

import logging
import posixpath
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.config.codecommit_utils import fetch_all_files
from awslabs.lza_mcp_server.utils.error_handling import create_structured_error_response
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


async def get_config_from_codecommit(
    ctx: Context,
    workspace_manager: WorkspaceManager,
    workspace_id: str,
    created_workspace: bool,
    path: Optional[str],
    qualifier: Optional[str],
    cc_location: Any,
) -> Dict[str, Any]:
    """Fetch config files from CodeCommit and write them into the workspace.

    Args:
        ctx: MCP context for progress reporting.
        workspace_manager: WorkspaceManager instance for file operations.
        workspace_id: Target workspace to write files into.
        created_workspace: Whether the workspace was created by this call.
        path: Optional base path within the workspace to write files under.
        qualifier: Accelerator Qualifier (for response metadata only).
        cc_location: Resolved CodeCommit location (repository_name, branch, qualifier).

    Returns:
        Dictionary with extraction results, workspace_id, and metadata.
    """
    await ctx.info(
        f"CodeCommit source detected: repo={cc_location.repository_name} "
        f"branch={cc_location.branch}"
    )
    if qualifier:
        await ctx.info(f"Qualifier: {qualifier}")

    base_path = path or ""

    try:
        files = fetch_all_files(cc_location.repository_name, cc_location.branch)
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
                    "Ensure codecommit:GetFolder and codecommit:GetBlob permissions are granted",
                ],
                context={},
            )
        if error_code in ("BranchDoesNotExistException", "CommitDoesNotExistException"):
            return create_structured_error_response(
                error="Branch not found in CodeCommit repository",
                category=ErrorCategory.CONFIGURATION,
                error_code="BRANCH_NOT_FOUND",
                troubleshooting=[
                    "Verify the branch exists in the repository",
                    "Common default branches are 'main' and 'master'",
                    "Provide the branch parameter explicitly if the default is incorrect",
                ],
                context={},
            )
        return create_structured_error_response(
            error=f"CodeCommit fetch failed: {str(e)}",
            category=ErrorCategory.CONFIGURATION,
            error_code=error_code or "CODECOMMIT_ERROR",
            troubleshooting=[
                "Check AWS credentials and CodeCommit permissions",
                "Verify the repository and branch exist",
            ],
            context={},
        )

    if not files:
        return create_structured_error_response(
            error="No files found in CodeCommit repository",
            category=ErrorCategory.CONFIGURATION,
            error_code="EMPTY_REPOSITORY",
            troubleshooting=[
                "Verify the repository contains LZA configuration files",
                "Check that the branch has content",
            ],
            context={},
        )

    # Write files into workspace
    file_count = 0
    root_files: list[str] = []
    root_folders: set[str] = set()

    for abs_path, content in files.items():
        ws_file_path = posixpath.join(base_path, abs_path) if base_path else abs_path
        workspace_manager.write_file(workspace_id, ws_file_path, content, ctx)
        file_count += 1

        if "/" not in abs_path:
            root_files.append(abs_path)
        else:
            root_folders.add(abs_path.split("/")[0])

    root_files = sorted(root_files)
    root_folders_list = sorted(root_folders)

    await ctx.info(
        f"Fetched {file_count} files from CodeCommit into workspace {workspace_id}"
    )

    structure: Dict[str, Any] = {
        "root": {
            "files": root_files,
            "directories": {
                folder: {"files": [], "directories": {}} for folder in root_folders_list
            },
        }
    }

    return {
        "success": True,
        "workspace_id": workspace_id,
        "workspace_created": created_workspace,
        "path": base_path or "/",
        "file_count": file_count,
        "root_files": root_files,
        "root_folders": root_folders_list,
        "structure": structure,
        "config_source": "codecommit",
        "repository_name": cc_location.repository_name,
        "branch": cc_location.branch,
        "qualifier": qualifier,
        "message": "Configuration retrieved from CodeCommit into workspace successfully",
        "llm_instructions": (
            f"IMPORTANT - Configuration Workflow:\n"
            f"1. Configuration has been fetched from CodeCommit into workspace '{workspace_id}'"
            + (f" at path '{base_path}'" if base_path else "")
            + "\n"
            f"2. Use readLzaConfigFile or workspace tools to inspect/edit files\n"
            f"3. After making changes, call putLzaConfiguration("
            f"workspace_id='{workspace_id}'"
            + (f", path='{base_path}'" if base_path else "")
            + f", repository_name='{cc_location.repository_name}'"
            + f", branch='{cc_location.branch}'"
            + (f", qualifier={repr(qualifier)}" if qualifier else "")
            + ")\n"
            "4. Then call startDeployment()"
            + (f" with qualifier={repr(qualifier)}" if qualifier else "")
            + "\n\n"
            f"TYPICAL WORKFLOW:\n"
            f"  - getLzaConfiguration() ← You are here\n"
            f"  - Edit files in workspace '{workspace_id}'\n"
            f"  - putLzaConfiguration("
            f"workspace_id='{workspace_id}'"
            + (f", path='{base_path}'" if base_path else "")
            + f", repository_name='{cc_location.repository_name}'"
            + f", branch='{cc_location.branch}'"
            + (f", qualifier={repr(qualifier)}" if qualifier else "")
            + ")\n"
            "  - startDeployment()"
            + (f" qualifier={repr(qualifier)}" if qualifier else "")
        ),
    }
