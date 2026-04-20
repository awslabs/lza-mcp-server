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

"""Validate LZA installation is fresh and compatible with UC merge."""

import logging
from typing import Any, Dict

import yaml
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)

from .common import create_error_response, create_success_response
from .validation import (
    validate_fresh_installation_accounts,
    validate_fresh_installation_iam,
    validate_fresh_installation_network,
)

logger = logging.getLogger(__name__)


async def validate_lza_for_uc_merge(
    ctx: Context,
    workspace_id: str,
    path: str,
    workspace_manager: WorkspaceManager,
) -> Dict[str, Any]:
    """Validate that the LZA installation is fresh and compatible with UC merge.

    Reads accounts-config.yaml, network-config.yaml, and iam-config.yaml from
    the specified workspace via WorkspaceManager and validates each for a fresh
    LZA installation.

    Args:
        ctx: MCP context for logging.
        workspace_id: Workspace ID from getLzaConfiguration.
        path: Optional path prefix within the workspace (defaults to "").
        workspace_manager: WorkspaceManager instance for file I/O.

    Returns:
        Dictionary with validation results.
    """
    if not workspace_id:
        return create_error_response(
            error_message=(
                "workspace_id is required. "
                "Provide the workspace_id returned by getLzaConfiguration()."
            ),
            error_code="MISSING_WORKSPACE_ID",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Call getLzaConfiguration() first to retrieve the LZA configuration into a workspace",
                "Pass the workspace_id returned by getLzaConfiguration() to this tool",
            ],
            next_steps="Call getLzaConfiguration() to retrieve the LZA configuration.",
        )

    try:
        await ctx.info("Validating LZA installation for UC merge compatibility")

        # Build file paths with optional prefix
        prefix = f"{path}/" if path else ""

        validation_results: Dict[str, Dict[str, Any]] = {
            "accounts": {"passed": False, "message": ""},
            "network": {"passed": False, "message": ""},
            "iam": {"passed": False, "message": ""},
        }

        # Validate accounts-config.yaml
        accounts_file = f"{prefix}accounts-config.yaml"
        try:
            accounts_bytes = workspace_manager.read_file(workspace_id, accounts_file)
            accounts_content = accounts_bytes.decode("utf-8")
            accounts_config = yaml.safe_load(accounts_content)
            is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)
            validation_results["accounts"]["passed"] = is_valid
            validation_results["accounts"]["message"] = (
                "Only mandatory accounts present" if is_valid else error_msg
            )
        except WorkspaceNotFoundError as e:
            error_str = str(e)
            if "File" in error_str and "not found" in error_str:
                return create_error_response(
                    error_message="accounts-config.yaml not found in workspace",
                    error_code="FILE_NOT_FOUND",
                    category=ErrorCategory.FILE_NOT_FOUND,
                    troubleshooting=[
                        "Verify getLzaConfiguration() extracted all files",
                        "Check that accounts-config.yaml exists in the S3 configuration",
                        "Ensure the LZA installation is complete",
                    ],
                    context={
                        "file": "accounts-config.yaml",
                    },
                    next_steps="Verify the LZA configuration is complete and retry.",
                )
            # Workspace itself not found — re-raise for outer handler
            raise
        except (WorkspaceValidationError, WorkspaceStorageError):
            raise
        except Exception as e:
            validation_results["accounts"]["message"] = f"Failed to parse: {str(e)}"

        # Validate network-config.yaml
        network_file = f"{prefix}network-config.yaml"
        try:
            network_bytes = workspace_manager.read_file(workspace_id, network_file)
            network_content = network_bytes.decode("utf-8")
            network_config = yaml.safe_load(network_content)
            is_valid, error_msg = validate_fresh_installation_network(network_config)
            validation_results["network"]["passed"] = is_valid
            validation_results["network"]["message"] = (
                "Minimal network configuration" if is_valid else error_msg
            )
        except WorkspaceNotFoundError as e:
            error_str = str(e)
            if "File" in error_str and "not found" in error_str:
                return create_error_response(
                    error_message="network-config.yaml not found in workspace",
                    error_code="FILE_NOT_FOUND",
                    category=ErrorCategory.FILE_NOT_FOUND,
                    troubleshooting=[
                        "Verify getLzaConfiguration() extracted all files",
                        "Check that network-config.yaml exists in the S3 configuration",
                        "Ensure the LZA installation is complete",
                    ],
                    context={
                        "file": "network-config.yaml",
                    },
                    next_steps="Verify the LZA configuration is complete and retry.",
                )
            raise
        except (WorkspaceValidationError, WorkspaceStorageError):
            raise
        except Exception as e:
            validation_results["network"]["message"] = f"Failed to parse: {str(e)}"

        # Validate iam-config.yaml
        iam_file = f"{prefix}iam-config.yaml"
        try:
            iam_bytes = workspace_manager.read_file(workspace_id, iam_file)
            iam_content = iam_bytes.decode("utf-8")
            iam_config = yaml.safe_load(iam_content)
            is_valid, error_msg = validate_fresh_installation_iam(iam_config)
            validation_results["iam"]["passed"] = is_valid
            validation_results["iam"]["message"] = (
                "Minimal IAM configuration" if is_valid else error_msg
            )
        except WorkspaceNotFoundError as e:
            error_str = str(e)
            if "File" in error_str and "not found" in error_str:
                return create_error_response(
                    error_message="iam-config.yaml not found in workspace",
                    error_code="FILE_NOT_FOUND",
                    category=ErrorCategory.FILE_NOT_FOUND,
                    troubleshooting=[
                        "Verify getLzaConfiguration() extracted all files",
                        "Check that iam-config.yaml exists in the S3 configuration",
                        "Ensure the LZA installation is complete",
                    ],
                    context={"file": "iam-config.yaml"},
                    next_steps="Verify the LZA configuration is complete and retry.",
                )
            raise
        except (WorkspaceValidationError, WorkspaceStorageError):
            raise
        except Exception as e:
            validation_results["iam"]["message"] = f"Failed to parse: {str(e)}"

        # Check if all validations passed
        all_passed = all(check["passed"] for check in validation_results.values())

        if not all_passed:
            failed_checks = [
                name
                for name, check in validation_results.items()
                if not check["passed"]
            ]

            await ctx.error(f"LZA validation failed for: {', '.join(failed_checks)}")

            return create_error_response(
                error_message=(
                    "LZA installation is not compatible with UC merge. "
                    f"Failed validation checks: {', '.join(failed_checks)}"
                ),
                error_code="NOT_FRESH_INSTALLATION",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "UC merge requires a fresh LZA installation with only 3 mandatory accounts",
                    "The current installation has additional workload accounts or custom configurations",
                    "Consider manual configuration instead of UC merge for existing deployments",
                    "Review the validation results for specific issues",
                ],
                context={
                    "validation_results": validation_results,
                    "failed_checks": failed_checks,
                },
                next_steps=(
                    "UC merge cannot proceed with this installation. "
                    "Use manual configuration approach for existing deployments."
                ),
            )

        await ctx.info("LZA installation validation passed - compatible with UC merge")

        return create_success_response(
            data={"validation_passed": True, "checks": validation_results},
            next_steps=(
                "Validation passed! The LZA installation is compatible with UC merge. "
                "Next, call get_uc_releases() to discover available UC versions."
            ),
        )

    except WorkspaceNotFoundError:
        return create_error_response(
            error_message="Workspace not found.",
            error_code="WORKSPACE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                "Verify workspace_id is correct",
                "Use createWorkspace or getLzaConfiguration to create a workspace",
            ],
            context={"error_type": "WorkspaceNotFoundError"},
            next_steps="Verify workspace_id, use getLzaConfiguration to create a workspace.",
        )
    except WorkspaceValidationError as e:
        return create_error_response(
            error_message=f"Workspace validation error: {str(e)}",
            error_code="WORKSPACE_VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Check path is relative, no traversal",
                "Verify workspace_id format is valid",
            ],
            context={"error_type": type(e).__name__},
            next_steps="Check path parameter and retry.",
        )
    except WorkspaceStorageError as e:
        return create_error_response(
            error_message=f"Workspace storage error: {str(e)}",
            error_code="WORKSPACE_STORAGE_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check storage adapter configuration",
                "Verify workspace storage is accessible",
            ],
            context={"error_type": type(e).__name__},
            next_steps="Check storage adapter configuration.",
        )
    except Exception as e:
        logger.error(f"Unexpected error validating LZA installation: {str(e)}")
        return create_error_response(
            error_message=f"Unexpected error during validation: {str(e)}",
            error_code="UNEXPECTED_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Check system logs for more details",
                "Verify the workspace is accessible",
                "Ensure configuration files are valid YAML",
                "Try calling getLzaConfiguration() again",
            ],
            context={"error_type": type(e).__name__},
            next_steps="Review the error and retry the operation.",
        )
