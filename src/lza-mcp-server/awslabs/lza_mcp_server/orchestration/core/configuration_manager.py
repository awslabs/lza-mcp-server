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


import logging
import os
from typing import Dict, Any, List

# MCP framework components
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.constants import DEFAULT_REGION
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.common import (
    categorize_configuration_error,
)

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def cleanup_configuration_zip(ctx: Context, zip_path: str) -> Dict[str, Any]:
    """
    Clean up ZIP file using the same logic as validation workflow.

    This method reuses the exact same cleanup logic as _cleanup_zip_with_bash
    from validation_tools.py to ensure consistent behavior and error handling.

    Args:
        ctx: MCP context for logging
        zip_path: Path to the ZIP file to clean up

    Returns:
        Dictionary with cleanup success status
    """
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            await ctx.info(f"Cleaned up ZIP file: {zip_path}")
            return {"success": True, "message": f"ZIP file cleaned up: {zip_path}"}
        else:
            await ctx.info("ZIP file already cleaned up")
            return {"success": True, "message": "ZIP file already cleaned up"}

    except Exception as e:
        error_msg = f"Cleanup error: {str(e)}"
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}


async def create_configuration_zip(
    ctx: Context, config_path: str, output_path: str
) -> Dict[str, Any]:
    """
    Create ZIP file from configuration folder using existing validation workflow logic.

    This method reuses the exact same ZIP creation logic as _create_zip_with_bash
    from validation_tools.py to ensure compatibility with the validation workflow
    and consistent file structure preservation.

    Args:
        ctx: MCP context for logging and user interaction
        config_path: Path to the configuration directory to zip
        output_path: Path where the ZIP file should be created

    Returns:
        Dictionary with success status and ZIP file details
    """
    try:
        import zipfile
        from pathlib import Path

        # Validate config_path
        try:
            config_dir_path = Path(config_path).resolve()
            if not config_dir_path.exists() or not config_dir_path.is_dir():
                error_msg = f"Config directory does not exist or is not a directory: {config_path}"
                await ctx.error(error_msg)
                return {"success": False, "error": error_msg}
        except (OSError, ValueError) as e:
            error_msg = f"Invalid config directory path: {config_path} - {str(e)}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}

        # Validate output_path
        try:
            output_file_path = Path(output_path).resolve()
            output_dir = output_file_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as e:
            error_msg = f"Invalid output file path: {output_path} - {str(e)}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}

        # Create ZIP using zipfile library
        with zipfile.ZipFile(output_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in config_dir_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(config_dir_path)
                    zipf.write(file_path, arcname)

        await ctx.info(f"Successfully created ZIP file: {output_path}")
        file_size = os.path.getsize(output_file_path)

        return {
            "success": True,
            "zip_path": output_path,
            "file_size": file_size,
            "message": f"Configuration ZIP created successfully: {output_path}",
        }

    except Exception as e:
        error_msg = f"Error creating ZIP: {str(e)}"
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}


async def select_configuration(ctx: Context, discovered_configs: List[str]) -> str:
    """
    Select configuration from discovered options.

    This method reuses the exact same logic as _select_configuration from validation_tools.py
    to ensure consistent user selection interface patterns.

    Args:
        ctx: MCP context for logging and user interaction
        discovered_configs: List of discovered configuration paths

    Returns:
        Selected configuration path

    Raises:
        ValueError: If no configurations are available for selection
    """
    if not discovered_configs:
        raise ValueError("No LZA configurations available for selection")

    if len(discovered_configs) == 1:
        selected = discovered_configs[0]
        await ctx.info(f"Using single discovered configuration: {selected}")
        return selected

    # For multiple configs, use the first one (in a real implementation,
    # this would prompt the user)
    # This matches the exact behavior from validation_tools._select_configuration
    selected = discovered_configs[0]
    await ctx.info(f"Multiple configurations found, using: {selected}")
    return selected


class ConfigurationManager:
    """Handles configuration discovery and validation."""

    def __init__(self):
        """Initialize ConfigurationManager."""
        self.logger = logger

    async def discover_configurations(
        self, ctx: Context, workspace_path: str
    ) -> List[str]:
        """
        Discover LZA configurations in the workspace.

        This method reuses the exact same logic as _discover_lza_configurations from validation_tools.py
        to ensure consistent behavior across the MCP server.

        Args:
            ctx: MCP context for logging and user interaction
            workspace_path: Path to search for LZA configurations

        Returns:
            List of paths containing valid LZA configurations
        """
        discovered_configs = []

        # Search for directories containing both accounts-config.yaml and organization-config.yaml
        # This is the same logic as validation_tools._discover_lza_configurations
        for root, dirs, files in os.walk(workspace_path):
            if "accounts-config.yaml" in files and "organization-config.yaml" in files:
                discovered_configs.append(root)
                await ctx.info(f"Found LZA configuration in: {root}")

        self.logger.info(
            f"Discovered {len(discovered_configs)} LZA configurations in {workspace_path}"
        )
        return discovered_configs

    async def validate_configuration_path(self, config_path: str) -> bool:
        """
        Validate that the configuration path contains valid LZA configuration.

        This method checks for the presence of required LZA configuration files
        using the same validation logic as the discovery process, with structured error handling.

        Args:
            config_path: Path to validate as LZA configuration

        Returns:
            True if path contains valid LZA configuration, False otherwise

        Raises:
            S3UploadError: If validation fails with structured error information
        """
        try:
            if not os.path.exists(config_path):
                self.logger.warning(f"Configuration path does not exist: {config_path}")
                raise S3UploadError(
                    message=f"Configuration path does not exist: {config_path}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="CONFIG_PATH_NOT_FOUND",
                    troubleshooting=[
                        "Verify the configuration path is correct",
                        "Ensure the directory exists and is accessible",
                        "Check file system permissions",
                    ],
                    context={
                        "config_path": config_path,
                        "operation": "configuration_validation",
                    },
                )

            if not os.path.isdir(config_path):
                self.logger.warning(
                    f"Configuration path is not a directory: {config_path}"
                )
                raise S3UploadError(
                    message=f"Configuration path is not a directory: {config_path}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="CONFIG_PATH_NOT_DIRECTORY",
                    troubleshooting=[
                        "Ensure the path points to a directory, not a file",
                        "Verify the directory structure is correct",
                    ],
                    context={
                        "config_path": config_path,
                        "operation": "configuration_validation",
                    },
                )

            # Check for required LZA configuration files (same as discovery logic)
            required_files = ["accounts-config.yaml", "organization-config.yaml"]
            files_in_dir = os.listdir(config_path)
            missing_files = []

            for required_file in required_files:
                if required_file not in files_in_dir:
                    missing_files.append(required_file)
                    self.logger.warning(
                        f"Required file '{required_file}' not found in {config_path}"
                    )

            if missing_files:
                raise S3UploadError(
                    message=f"Missing required LZA configuration files: {', '.join(missing_files)}",
                    category=ErrorCategory.CONFIGURATION,
                    error_code="CONFIG_FILES_MISSING",
                    troubleshooting=[
                        "Ensure all required LZA configuration files are present:",
                        "  - accounts-config.yaml",
                        "  - organization-config.yaml",
                        "Verify the configuration directory structure is correct",
                        "Check that files are properly named (case-sensitive)",
                    ],
                    context={
                        "config_path": config_path,
                        "missing_files": missing_files,
                        "required_files": required_files,
                        "files_found": files_in_dir,
                        "operation": "configuration_validation",
                    },
                )

            self.logger.info(
                f"Configuration path validated successfully: {config_path}"
            )
            return True

        except S3UploadError:
            # Re-raise S3UploadError as-is
            raise
        except Exception as e:
            self.logger.error(
                f"Error validating configuration path {config_path}: {str(e)}"
            )
            error_info = categorize_configuration_error(e)
            raise S3UploadError(
                message=f"Unexpected error validating configuration: {str(e)}",
                category=error_info["category"],
                error_code=error_info["error_code"],
                troubleshooting=error_info["troubleshooting"],
                context={
                    "config_path": config_path,
                    "operation": "configuration_validation",
                    "error_type": type(e).__name__,
                },
            )
