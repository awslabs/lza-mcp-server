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
from pathlib import Path
from typing import Dict, Any
import yaml

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from .common import (
    create_error_response,
    create_success_response,
    LZA_CONFIG_BASE_PATH,
)
from .validation import (
    validate_fresh_installation_accounts,
    validate_fresh_installation_network,
    validate_fresh_installation_iam,
)

logger = logging.getLogger(__name__)


async def validate_lza_for_uc_merge(ctx: Context) -> Dict[str, Any]:
    """Validate that the LZA installation is fresh and compatible with UC merge.
    
    This tool validates that the current LZA installation meets the requirements
    for UC merge by checking:
    - accounts-config.yaml has only 3 mandatory accounts (no workload accounts)
    - network-config.yaml has minimal configuration (empty arrays)
    - iam-config.yaml has minimal configuration (empty arrays)
    
    Call this after getConfigurationFromS3() to ensure the installation is
    compatible with UC merge before proceeding.
    
    Returns:
        Dictionary with validation results:
        {
            "success": bool,
            "validation_passed": bool,
            "checks": {
                "accounts": {"passed": bool, "message": str},
                "network": {"passed": bool, "message": str},
                "iam": {"passed": bool, "message": str}
            },
            "next_steps": str
        }
    """
    try:
        await ctx.info("Validating LZA installation for UC merge compatibility")
        
        # Check if configuration has been retrieved
        base_directory = LZA_CONFIG_BASE_PATH / "retrieved-config"
        
        if not base_directory.exists():
            return create_error_response(
                error_message=(
                    "LZA configuration directory not found. "
                    "Call getConfigurationFromS3() first to retrieve the configuration."
                ),
                error_code="CONFIG_NOT_RETRIEVED",
                category=ErrorCategory.CONFIGURATION,
                troubleshooting=[
                    "Call getConfigurationFromS3() to retrieve the LZA configuration",
                    "Verify the configuration was extracted successfully",
                    "Ensure getConfigurationFromS3() completed without errors"
                ],
                context={"expected_directory": str(base_directory)},
                next_steps="Call getConfigurationFromS3() to retrieve the LZA configuration."
            )
        
        validation_results = {
            "accounts": {"passed": False, "message": ""},
            "network": {"passed": False, "message": ""},
            "iam": {"passed": False, "message": ""}
        }
        
        # Validate accounts-config.yaml
        accounts_path = base_directory / "accounts-config.yaml"
        if not accounts_path.exists():
            return create_error_response(
                error_message="accounts-config.yaml not found in LZA configuration",
                error_code="FILE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify getConfigurationFromS3() extracted all files",
                    "Check that accounts-config.yaml exists in the S3 configuration",
                    "Ensure the LZA installation is complete"
                ],
                context={"file": "accounts-config.yaml"},
                next_steps="Verify the LZA configuration is complete and retry."
            )
        
        try:
            accounts_content = accounts_path.read_text(encoding="utf-8")
            accounts_config = yaml.safe_load(accounts_content)
            is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)
            validation_results["accounts"]["passed"] = is_valid
            validation_results["accounts"]["message"] = (
                "Only mandatory accounts present" if is_valid else error_msg
            )
        except Exception as e:
            validation_results["accounts"]["message"] = f"Failed to parse: {str(e)}"
        
        # Validate network-config.yaml
        network_path = base_directory / "network-config.yaml"
        if not network_path.exists():
            return create_error_response(
                error_message="network-config.yaml not found in LZA configuration",
                error_code="FILE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify getConfigurationFromS3() extracted all files",
                    "Check that network-config.yaml exists in the S3 configuration",
                    "Ensure the LZA installation is complete"
                ],
                context={"file": "network-config.yaml"},
                next_steps="Verify the LZA configuration is complete and retry."
            )
        
        try:
            network_content = network_path.read_text(encoding="utf-8")
            network_config = yaml.safe_load(network_content)
            is_valid, error_msg = validate_fresh_installation_network(network_config)
            validation_results["network"]["passed"] = is_valid
            validation_results["network"]["message"] = (
                "Minimal network configuration" if is_valid else error_msg
            )
        except Exception as e:
            validation_results["network"]["message"] = f"Failed to parse: {str(e)}"
        
        # Validate iam-config.yaml
        iam_path = base_directory / "iam-config.yaml"
        if not iam_path.exists():
            return create_error_response(
                error_message="iam-config.yaml not found in LZA configuration",
                error_code="FILE_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify getConfigurationFromS3() extracted all files",
                    "Check that iam-config.yaml exists in the S3 configuration",
                    "Ensure the LZA installation is complete"
                ],
                context={"file": "iam-config.yaml"},
                next_steps="Verify the LZA configuration is complete and retry."
            )
        
        try:
            iam_content = iam_path.read_text(encoding="utf-8")
            iam_config = yaml.safe_load(iam_content)
            is_valid, error_msg = validate_fresh_installation_iam(iam_config)
            validation_results["iam"]["passed"] = is_valid
            validation_results["iam"]["message"] = (
                "Minimal IAM configuration" if is_valid else error_msg
            )
        except Exception as e:
            validation_results["iam"]["message"] = f"Failed to parse: {str(e)}"
        
        # Check if all validations passed
        all_passed = all(
            check["passed"] for check in validation_results.values()
        )
        
        if not all_passed:
            # Find which checks failed
            failed_checks = [
                name for name, check in validation_results.items()
                if not check["passed"]
            ]
            
            await ctx.error(
                f"LZA validation failed for: {', '.join(failed_checks)}"
            )
            
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
                    "Review the validation results for specific issues"
                ],
                context={
                    "validation_results": validation_results,
                    "failed_checks": failed_checks
                },
                next_steps=(
                    "UC merge cannot proceed with this installation. "
                    "Use manual configuration approach for existing deployments."
                )
            )
        
        await ctx.info("LZA installation validation passed - compatible with UC merge")
        
        return create_success_response(
            data={
                "validation_passed": True,
                "checks": validation_results
            },
            next_steps=(
                "Validation passed! The LZA installation is compatible with UC merge. "
                "Next, call get_uc_releases() to discover available UC versions."
            )
        )
        
    except Exception as e:
        logger.error(f"Unexpected error validating LZA installation: {str(e)}")
        return create_error_response(
            error_message=f"Unexpected error during validation: {str(e)}",
            error_code="UNEXPECTED_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Check system logs for more details",
                "Verify the configuration directory is accessible",
                "Ensure configuration files are valid YAML",
                "Try calling getConfigurationFromS3() again"
            ],
            context={"error_type": type(e).__name__},
            next_steps="Review the error and retry the operation."
        )
