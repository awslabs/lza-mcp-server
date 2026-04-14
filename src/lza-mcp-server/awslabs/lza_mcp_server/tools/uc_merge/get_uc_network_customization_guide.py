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

from pathlib import Path
from typing import Dict, Any

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    create_error_response,
    create_success_response,
)
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager


def get_uc_network_customization_guide(session_id: str) -> Dict[str, Any]:
    """Get network customization guidance and file list for the session's network model.

    This tool provides metadata about the UC session and lists available configuration files.
    The LLM/Agent should read replacements-config.yaml to understand what settings are
    customizable and make intelligent decisions about what to update based on user needs.

    Args:
        session_id: Session identifier from start_uc_merge_session()

    Returns:
        Dictionary containing:
        - session_id: Session identifier
        - network_model: Selected network model
        - configuration_files: Dictionary organizing files by type
        - next_steps: Guidance for next actions
    """
    session_manager = SessionManager()

    # Validate session exists
    is_valid, error_msg = session_manager.validate_session(session_id)
    if not is_valid:
        return create_error_response(
            error_message=error_msg,
            error_code="INVALID_SESSION",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Start a new session with start_uc_merge_session()",
                "Verify the session_id is correct",
                "Check that the session has not been cleaned up",
            ],
            next_steps="Call start_uc_merge_session() to create a new session",
        )

    # Load session metadata to get network model
    metadata = session_manager.load_session_metadata(session_id)
    if not metadata or "network_model" not in metadata:
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
    session_path = session_manager.get_session_path(session_id)

    # Scan session directory for configuration files
    configuration_files = _scan_configuration_files(session_path)

    # Build next steps guidance
    next_steps = (
        f"Read the UC configuration files to understand what needs to be customized:\n"
        f"1. Call readUcFile(session_id='{session_id}', file_path='replacements-config.yaml') "
        "to see all available network settings, IPAM pools, and other customizable values\n"
        f"2. Call readUcFile(session_id='{session_id}', file_path='accounts-config.yaml') "
        "to see the account structure\n"
        f"3. Call readLzaConfigFile(file_path='accounts-config.yaml') and "
        "readLzaConfigFile(file_path='global-config.yaml') to extract existing LZA values "
        "(mandatory account emails, homeRegion)\n"
        f"4. Based on the replacements-config.yaml content and user requirements, determine "
        "which settings need updates and use updateUcFile() to apply changes\n"
        f"5. Focus on mandatory updates (account emails, homeRegion) and ask user about "
        "optional network customizations only if needed"
    )

    return create_success_response(
        data={
            "session_id": session_id,
            "network_model": network_model,
            "configuration_files": configuration_files,
        },
        next_steps=next_steps,
    )


def _scan_configuration_files(session_path: Path) -> Dict[str, list[str]]:
    """Scan session directory and organize files by type.

    Args:
        session_path: Path to session directory

    Returns:
        Dictionary with files organized by type:
        - config_files: YAML configuration files
        - policy_directories: Directories containing policies
        - supporting_directories: Other supporting directories
    """
    config_files: list[str] = []
    policy_directories: list[str] = []
    supporting_directories: list[str] = []

    if not session_path.exists():
        return {
            "config_files": config_files,
            "policy_directories": policy_directories,
            "supporting_directories": supporting_directories,
        }

    # Scan for YAML config files in root
    for item in session_path.iterdir():
        if item.is_file() and item.suffix in [".yaml", ".yml"]:
            config_files.append(item.name)

    # Scan for directories and classify them dynamically
    for item in session_path.iterdir():
        if item.is_dir():
            # Skip hidden directories (like .session_metadata.json parent)
            if item.name.startswith("."):
                continue

            # Classify directory based on name patterns
            if _is_policy_directory(item.name):
                policy_directories.append(item.name)
            else:
                supporting_directories.append(item.name)

    # Sort for consistent ordering
    config_files.sort()
    policy_directories.sort()
    supporting_directories.sort()

    return {
        "config_files": config_files,
        "policy_directories": policy_directories,
        "supporting_directories": supporting_directories,
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
