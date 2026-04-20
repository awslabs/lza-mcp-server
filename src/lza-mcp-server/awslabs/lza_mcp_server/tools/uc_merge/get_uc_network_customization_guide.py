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

"""Get UC network customization guidance and file list."""

import json
import logging
from typing import Dict, Any, List

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    create_error_response,
    create_success_response,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
)

logger = logging.getLogger(__name__)


def get_uc_network_customization_guide(
    workspace_id: str, workspace_manager: WorkspaceManager
) -> Dict[str, Any]:
    """Get network customization guidance and file list for the session's network model.

    This tool provides metadata about the UC session and lists available configuration files.
    The LLM/Agent should read replacements-config.yaml to understand what settings are
    customizable and make intelligent decisions about what to update based on user needs.

    Args:
        workspace_id: Workspace identifier from start_uc_merge_session()
        workspace_manager: WorkspaceManager instance for file operations

    Returns:
        Dictionary containing:
        - workspace_id: Workspace identifier
        - network_model: Selected network model
        - configuration_files: Dictionary organizing files by type
        - next_steps: Guidance for next actions
    """
    # Read session metadata from workspace
    try:
        metadata_bytes = workspace_manager.read_file(
            workspace_id, ".session_metadata.json"
        )
    except WorkspaceNotFoundError as exc:
        error_str = str(exc)
        # Distinguish between workspace not found and file not found
        if "not found in workspace" in error_str:
            return create_error_response(
                error_message="Workspace is missing session metadata (.session_metadata.json)",
                error_code="INVALID_SESSION_METADATA",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Session metadata is missing from the workspace",
                    "Start a new session with start_uc_merge_session()",
                ],
                next_steps="Call start_uc_merge_session() to create a new session",
            )
        return create_error_response(
            error_message="Workspace not found",
            error_code="WORKSPACE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                "Verify the workspace_id is correct",
                "Start a new session with start_uc_merge_session()",
                "Check that the workspace has not been deleted",
            ],
            next_steps="Call start_uc_merge_session() to create a new session",
        )

    # Parse metadata
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return create_error_response(
            error_message="Session metadata is corrupted or not valid JSON",
            error_code="INVALID_SESSION_METADATA",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Session metadata is corrupted or incomplete",
                "Start a new session with start_uc_merge_session()",
            ],
            next_steps="Call start_uc_merge_session() to create a new session",
        )

    if "network_model" not in metadata:
        return create_error_response(
            error_message="Session is missing network_model metadata",
            error_code="INVALID_SESSION_METADATA",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Session metadata is corrupted or incomplete",
                "Start a new session with start_uc_merge_session()",
            ],
            next_steps="Call start_uc_merge_session() to create a new session",
        )

    network_model = metadata["network_model"]

    # List files in workspace and classify them
    try:
        file_list = workspace_manager.list_files(workspace_id)
    except WorkspaceNotFoundError:
        return create_error_response(
            error_message="Workspace not found",
            error_code="WORKSPACE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                "Verify the workspace_id is correct",
                "Start a new session with start_uc_merge_session()",
            ],
            next_steps="Call start_uc_merge_session() to create a new session",
        )

    # Classify files
    configuration_files = _scan_configuration_files(file_list)

    # Build next steps guidance
    next_steps = (
        "IMPORTANT: Execute steps 1-4 autonomously without stopping. Do NOT apply "
        "any changes or ask the user anything until step 5.\n\n"
        f"1. Read the UC replacements config: use readResource with URI "
        f"workspace://{workspace_id}/file/replacements-config.yaml "
        "to identify all customizable settings (network CIDRs, IPAM pools, "
        "global replacements, emails, etc.)\n"
        f"2. Read the UC accounts config: use readResource with URI "
        f"workspace://{workspace_id}/file/accounts-config.yaml "
        "to identify the account structure and which values need updating "
        "(especially emails)\n"
        f"3. Read the EXISTING LZA configuration: use readResource on the LZA workspace "
        "to read accounts-config.yaml and global-config.yaml. Extract current "
        "mandatory account emails and homeRegion\n"
        f"4. Compare UC defaults against existing LZA values. Build a summary of:\n"
        "   - Values that can be carried forward from existing LZA config (homeRegion, "
        "existing account emails)\n"
        "   - Values that require user input (email addresses for any NEW accounts "
        "not in the existing LZA config)\n"
        "   - Optional customizations the user may want to adjust (CIDR ranges, "
        "IPAM pools)\n"
        f"5. Present the summary to the user showing what will be set and what input "
        "is needed. CRITICAL: NEVER invent or fabricate email addresses. If an email "
        "is not in the existing LZA config, you MUST ask the user for it. "
        "Wait for user confirmation before applying any changes with "
        "writeWorkspaceFile(). After user confirms, apply all changes, then proceed "
        "to copyUcToLzaConfig()"
    )

    return create_success_response(
        data={
            "workspace_id": workspace_id,
            "network_model": network_model,
            "configuration_files": configuration_files,
        },
        next_steps=next_steps,
    )


def _scan_configuration_files(file_list: List[str]) -> Dict[str, list[str]]:
    """Classify workspace files by type.

    Takes a flat list of relative file paths from WorkspaceManager.list_files()
    and organizes them into config files, policy directories, and supporting
    directories.

    Args:
        file_list: List of relative file paths from the workspace

    Returns:
        Dictionary with files organized by type:
        - config_files: YAML configuration files at root level
        - policy_directories: Directories containing policies
        - supporting_directories: Other supporting directories
    """
    config_files: list[str] = []
    policy_directories: set[str] = set()
    supporting_directories: set[str] = set()

    for file_path in file_list:
        # Skip hidden files like .session_metadata.json
        if file_path.startswith("."):
            continue

        # Split path to check if it's at root level or in a subdirectory
        parts = file_path.split("/")

        if len(parts) == 1:
            # Root-level file
            if file_path.endswith((".yaml", ".yml")):
                config_files.append(file_path)
        else:
            # File in a subdirectory — classify the top-level directory
            top_dir = parts[0]
            if top_dir.startswith("."):
                continue
            if _is_policy_directory(top_dir):
                policy_directories.add(top_dir)
            else:
                supporting_directories.add(top_dir)

    # Sort for consistent ordering
    config_files.sort()

    return {
        "config_files": config_files,
        "policy_directories": sorted(policy_directories),
        "supporting_directories": sorted(supporting_directories),
    }


def _is_policy_directory(dir_name: str) -> bool:
    """Determine if a directory name indicates it contains policies.

    Uses heuristics to identify policy directories based on naming patterns.

    Args:
        dir_name: Directory name to check

    Returns:
        True if directory appears to contain policies, False otherwise
    """
    # Check for common policy-related keywords in directory name
    policy_keywords = [
        "policy",
        "policies",
        "firewall",
        "rules",
        "rcp",
    ]

    dir_name_lower = dir_name.lower()
    return any(keyword in dir_name_lower for keyword in policy_keywords)
