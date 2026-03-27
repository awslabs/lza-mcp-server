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

"""Get available UC network deployment models with comparison information."""

import logging
from typing import Dict, Any, List
from mcp.server.fastmcp import Context
from awslabs.lza_mcp_server.utils.input_validation import validate_string_input

from . import common

logger = logging.getLogger(__name__)


async def tool_get_uc_network_models(ctx: Context, uc_release: str) -> Dict[str, Any]:
    """Get available UC network deployment models with comparison information.

    Dynamically discovers available network models from the specified UC release
    directory and provides a reference to the GitHub documentation to help users
    understand the differences between network architectures.

    Args:
        uc_release: UC release version (e.g., "v1.0.0"). Required parameter.

    Returns:
        Dictionary containing:
        - success (bool): Operation success status
        - uc_release (str): The UC release version queried
        - available_models (List[str]): List of available model names
        - documentation_url (str): GitHub URL to UC documentation
        - next_steps (str): Guidance for presenting models to user

    Example:
        ```python
        result = await get_uc_network_models(uc_release="v1.0.0")

        if result["success"]:
            print(f"Available models: {result['available_models']}")
            print(f"Documentation: {result['documentation_url']}")

            # Present to user and request selection
            print(result["next_steps"])
        ```
    """
    await ctx.info(f"Discovering network models for UC release: {uc_release}")

    # Validate uc_release parameter is provided first (before string validation)
    if not uc_release:
        error_msg = "uc_release parameter is required"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "MISSING_UC_RELEASE",
            "troubleshooting": [
                "The uc_release parameter is required",
                "Call get_uc_releases() first to discover available releases",
                "Select a release from the available options",
                "Pass the selected release name to get_uc_network_models()",
            ],
            "next_steps": "Call get_uc_releases() to discover available UC release versions, then retry with a valid uc_release parameter",
        }

    # Validate uc_release input format
    is_valid, validation_error = validate_string_input(
        uc_release, "uc_release", min_length=1, max_length=50
    )
    if not is_valid:
        error_msg = f"Invalid uc_release parameter: {validation_error}"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "INVALID_UC_RELEASE",
            "troubleshooting": [
                "UC release must be a valid string (1-50 characters)",
                "Call get_uc_releases() first to discover available releases",
            ],
            "next_steps": "Call get_uc_releases() to discover available UC release versions",
        }

    # Reject path traversal attempts
    if ".." in uc_release:
        error_msg = f"Invalid uc_release: path traversal detected in '{uc_release}'"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "PATH_TRAVERSAL_DETECTED",
            "troubleshooting": [
                "UC release must not contain path traversal sequences (..)",
                "Call get_uc_releases() first to discover available releases",
            ],
            "next_steps": "Call get_uc_releases() to discover available UC release versions",
        }

    try:
        # Get the release directory path
        release_path = common.get_uc_release_path(uc_release)

        # Check if release directory exists
        if not release_path.exists():
            # Get available releases for error message
            available_releases = []
            uc_base = common.get_uc_base_path()
            if uc_base.exists() and uc_base.is_dir():
                available_releases = [
                    item.name for item in uc_base.iterdir() if item.is_dir()
                ]

            error_msg = f"UC release not found: {uc_release}"
            await ctx.error(error_msg)

            if available_releases:
                available_list = "\n".join(
                    [f"  - {r}" for r in sorted(available_releases, reverse=True)]
                )
                troubleshooting = [
                    f"The specified UC release '{uc_release}' does not exist",
                    "Available releases:",
                    available_list,
                    "Select one of the available releases",
                ]
                next_steps = f"Call get_uc_network_models() with one of the available releases: {', '.join(available_releases)}"
            else:
                troubleshooting = [
                    f"The specified UC release '{uc_release}' does not exist",
                    "No UC releases found in the repository",
                    "Contact administrator to install UC releases",
                ]
                next_steps = (
                    "Contact administrator to verify UC repository installation"
                )

            return {
                "success": False,
                "error": error_msg,
                "error_code": "UC_RELEASE_NOT_FOUND",
                "troubleshooting": troubleshooting,
                "context": {
                    "uc_release": uc_release,
                    "available_releases": available_releases,
                },
                "next_steps": next_steps,
            }

        if not release_path.is_dir():
            error_msg = f"UC release path is not a directory: {uc_release}"
            await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_code": "UC_RELEASE_NOT_DIRECTORY",
                "troubleshooting": [
                    "The UC release path exists but is not a directory",
                    "Verify UC repository structure is intact",
                    "Contact administrator for assistance",
                ],
                "next_steps": "Contact administrator to verify UC repository installation",
            }

        # Scan for network model directories
        available_models: List[str] = []

        # Directories to skip (not network models)
        skip_dirs = {"docs", "scripts", ".git", ".github"}

        for item in release_path.iterdir():
            if item.is_dir() and item.name not in skip_dirs:
                model_name = item.name
                available_models.append(model_name)
                await ctx.info(f"Found network model: {model_name}")

        if not available_models:
            await ctx.info(f"No network models found in release {uc_release}")
            return {
                "success": True,
                "uc_release": uc_release,
                "available_models": [],
                "models": {},
                "next_steps": f"No network models found in UC release {uc_release}. Contact administrator to verify UC repository structure.",
            }

        # Sort models alphabetically for consistent presentation
        available_models.sort()

        await ctx.info(
            f"Discovered {len(available_models)} network model(s) for release {uc_release}"
        )

        # Build model list for presentation
        model_list = "\n".join([f"  - {name}" for name in available_models])

        # Reference GitHub documentation
        github_docs_url = "https://github.com/aws/lza-universal-configuration/blob/main/docs/index.adoc"

        return {
            "success": True,
            "uc_release": uc_release,
            "available_models": available_models,
            "documentation_url": github_docs_url,
            "next_steps": (
                f"Available network models for {uc_release}:\n{model_list}\n\n"
                f"For detailed information about network model differences, refer to the UC documentation: {github_docs_url}\n\n"
                f"Present the available models to the user and ask them to select one. "
                f"After the user selects a network model, call start_uc_merge_session() with "
                f"the selected uc_release and network_model parameters to begin the merge workflow."
            ),
        }

    except PermissionError as e:
        error_msg = f"Permission denied accessing UC release directory: {str(e)}"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "PERMISSION_DENIED",
            "troubleshooting": [
                "Check file system permissions for UC repository",
                "Verify the container has read access to the UC directory",
                "Contact administrator for assistance",
            ],
            "next_steps": "Contact administrator to verify UC repository permissions",
        }
    except Exception as e:
        error_msg = f"Unexpected error discovering network models: {str(e)}"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "UNEXPECTED_ERROR",
            "troubleshooting": [
                "Check system logs for detailed error information",
                "Verify UC repository structure is intact",
                "Contact administrator for assistance",
            ],
            "context": {"uc_release": uc_release, "error_type": type(e).__name__},
            "next_steps": "Contact administrator for assistance",
        }
