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

"""Start UC merge session tool implementation."""

from typing import Dict, Any

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from .common import (
    get_uc_release_path,
    get_uc_network_model_path,
    create_error_response,
    create_success_response,
    categorize_uc_merge_error,
)
from .validation import validate_network_model, validate_uc_release
from .session_manager import SessionManager


async def tool_start_uc_merge_session(
    ctx, uc_release: str, network_model: str
) -> Dict[str, Any]:
    """Start a new UC merge session with the selected release and network model.

    Creates a session directory with a fresh copy of the UC configuration
    for the specified network model. The session_id must be passed to
    subsequent UC merge tools (read_uc_file, update_uc_file, copy_uc_to_lza_config).

    This ensures each merge session works with pristine UC files and doesn't
    interfere with other sessions.

    Args:
        ctx: MCP context for logging
        uc_release: UC release version (e.g., "v1.0.0"). Required parameter.
        network_model: Network model name (e.g., "hub-and-spoke", "shared-vpc"). Required parameter.

    Returns:
        Dictionary with session information or error details
    """
    await ctx.info(
        f"Starting UC merge session with release={uc_release}, network_model={network_model}"
    )

    # Validate required parameters
    if not uc_release:
        return create_error_response(
            error_message="Missing required parameter: uc_release",
            error_code="MISSING_PARAMETER",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "The uc_release parameter is required",
                "Call get_uc_releases() first to see available releases",
                "Provide a valid UC release version (e.g., 'v1.0.0')",
            ],
            next_steps="Call get_uc_releases() to discover available UC release versions, then retry with a valid uc_release parameter",
        )

    if not network_model:
        return create_error_response(
            error_message="Missing required parameter: network_model",
            error_code="MISSING_PARAMETER",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "The network_model parameter is required",
                "Call get_uc_network_models(uc_release) first to see available models",
                "Provide a valid network model name (e.g., 'hub-and-spoke', 'shared-vpc')",
            ],
            next_steps=f"Call get_uc_network_models(uc_release='{uc_release}') to discover available network models, then retry with a valid network_model parameter",
        )

    # Validate uc_release format
    is_valid, error_msg = validate_uc_release(uc_release)
    if not is_valid:
        return create_error_response(
            error_message=error_msg,
            error_code="INVALID_UC_RELEASE",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "UC release format is invalid",
                "Expected format: vX.Y.Z (e.g., v1.0.0)",
                "Call get_uc_releases() to see available releases",
            ],
            context={"uc_release": uc_release},
            next_steps="Call get_uc_releases() to discover available UC release versions",
        )

    # Validate network_model format
    is_valid, error_msg = validate_network_model(network_model)
    if not is_valid:
        return create_error_response(
            error_message=error_msg,
            error_code="INVALID_NETWORK_MODEL",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Network model format is invalid",
                "Must contain only lowercase letters, numbers, and hyphens",
                f"Call get_uc_network_models(uc_release='{uc_release}') to see available models",
            ],
            context={"network_model": network_model},
            next_steps=f"Call get_uc_network_models(uc_release='{uc_release}') to discover available network models",
        )

    # Check if uc_release exists
    uc_release_path = get_uc_release_path(uc_release)
    if not uc_release_path.exists():
        # Get available releases for error message
        available_releases = []
        from .common import get_uc_base_path

        uc_base_path = get_uc_base_path()
        if uc_base_path.exists():
            available_releases = [
                d.name
                for d in uc_base_path.iterdir()
                if d.is_dir() and d.name.startswith("v")
            ]

        return create_error_response(
            error_message=f"UC release '{uc_release}' does not exist",
            error_code="UC_RELEASE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                f"The specified UC release '{uc_release}' was not found",
                "Available releases: " + ", ".join(available_releases)
                if available_releases
                else "No releases found",
                "Call get_uc_releases() to see all available releases",
            ],
            context={
                "uc_release": uc_release,
                "available_releases": available_releases,
            },
            next_steps="Call get_uc_releases() to discover available UC release versions",
        )

    # Check if network_model exists within the release
    network_model_path = get_uc_network_model_path(uc_release, network_model)
    if not network_model_path.exists():
        # Get available models for error message
        available_models = []
        if uc_release_path.exists():
            available_models = [
                d.name
                for d in uc_release_path.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

        return create_error_response(
            error_message=f"Network model '{network_model}' does not exist in release '{uc_release}'",
            error_code="NETWORK_MODEL_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                f"The specified network model '{network_model}' was not found in release '{uc_release}'",
                "Available models: " + ", ".join(available_models)
                if available_models
                else "No models found",
                f"Call get_uc_network_models(uc_release='{uc_release}') to see available models",
            ],
            context={
                "uc_release": uc_release,
                "network_model": network_model,
                "available_models": available_models,
            },
            next_steps=f"Call get_uc_network_models(uc_release='{uc_release}') to discover available network models",
        )

    # Create session
    try:
        session_manager = SessionManager()

        # Generate unique session ID
        session_id = session_manager.generate_session_id()
        await ctx.info(f"Generated session ID: {session_id}")

        # Create session directory
        session_path = session_manager.create_session_directory(session_id)
        await ctx.info(f"Created session directory: {session_path}")

        # Copy UC files to session
        files_copied = session_manager.copy_files_to_session(
            session_id=session_id,
            source_dir=network_model_path,
            preserve_structure=True,
        )
        await ctx.info(f"Copied {files_copied} files to session")

        # Save session metadata
        session_manager.save_session_metadata(
            session_id=session_id, network_model=network_model, uc_release=uc_release
        )
        await ctx.info("Saved session metadata")

        # Clean up previous sessions
        cleaned_count = session_manager.cleanup_previous_sessions(
            keep_session_id=session_id
        )
        if cleaned_count > 0:
            await ctx.info(f"Cleaned up {cleaned_count} previous session(s)")

        return create_success_response(
            data={
                "session_id": session_id,
                "session_path": str(session_path),
                "uc_release": uc_release,
                "network_model": network_model,
                "files_copied": files_copied,
            },
            next_steps=f"Session created successfully with {network_model} configuration. REQUIRED: You must now call getLzaConfiguration() to retrieve the current LZA configuration, then call validateLzaForUcMerge() to ensure compatibility before proceeding with customization.",
        )

    except Exception as e:
        await ctx.error(f"Failed to create UC merge session: {str(e)}")

        error_info = categorize_uc_merge_error(e)

        return create_error_response(
            error_message=f"Failed to create UC merge session: {str(e)}",
            error_code=error_info["error_code"],
            category=error_info["category"],
            troubleshooting=error_info["troubleshooting"],
            context={"uc_release": uc_release, "network_model": network_model},
            next_steps="Review the error and troubleshooting steps, then retry start_uc_merge_session()",
        )
