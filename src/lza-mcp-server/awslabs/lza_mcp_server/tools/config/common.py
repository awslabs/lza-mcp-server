# Error handling constants and classes
from typing import Dict, Any
from ...error_categories import ErrorCategory


def categorize_configuration_error(error: Exception) -> Dict[str, Any]:
    """
    Categorize configuration-related errors and provide specific guidance.

    Args:
        error: Configuration exception to categorize

    Returns:
        Dictionary with error category and troubleshooting steps
    """
    error_str = str(error).lower()

    if "not found" in error_str or "does not exist" in error_str:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "CONFIG_NOT_FOUND",
            "troubleshooting": [
                "Configuration directory or files not found",
                "Ensure the configuration path exists and is accessible",
                "Verify the directory contains required LZA configuration files:",
                "  - accounts-config.yaml",
                "  - organization-config.yaml",
                "Check file system permissions",
            ],
        }

    elif "permission" in error_str or "access" in error_str:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "CONFIG_ACCESS_DENIED",
            "troubleshooting": [
                "Permission denied accessing configuration files",
                "Check file system permissions for the configuration directory",
                "Ensure the user has read access to all configuration files",
                "Verify the configuration directory is not locked by another process",
            ],
        }

    elif "yaml" in error_str or "parse" in error_str or "syntax" in error_str:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "CONFIG_PARSE_ERROR",
            "troubleshooting": [
                "Configuration file parsing error",
                "Check YAML syntax in configuration files",
                "Ensure proper indentation and formatting",
                "Validate configuration files against LZA schema",
                "Use a YAML validator to check file syntax",
            ],
        }

    elif "zip" in error_str or "archive" in error_str:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "ZIP_CREATION_ERROR",
            "troubleshooting": [
                "Failed to create ZIP archive from configuration",
                "Ensure the 'zip' command is available on the system",
                "Check available disk space for temporary files",
                "Verify configuration directory structure is valid",
                "Check for file locks or permissions issues",
            ],
        }

    else:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "CONFIG_VALIDATION_ERROR",
            "troubleshooting": [
                "Configuration validation failed",
                "Ensure all required LZA configuration files are present",
                "Verify configuration files follow LZA schema requirements",
                "Check for missing or invalid configuration values",
                "Run LZA validation tools to identify specific issues",
            ],
        }
