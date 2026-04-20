import logging

logger = logging.getLogger(__name__)

# ECS deployment status markers
ECS_DEPLOYMENT_COMPLETE = "DEPLOYMENT COMPLETE"
ECS_DEPLOYMENT_FAILED_MARKERS = [
    "DEPLOYMENT FAILED",
    "Error: Process completed with exit code",
    "error Command failed with exit code",
]


def determine_ecs_deployment_status(log_lines: list[str]) -> str:
    """Determine ECS container deployment status from log lines.

    Scans the log lines (particularly the tail) for deployment outcome markers.

    Returns:
        "COMPLETE" if DEPLOYMENT COMPLETE found,
        "FAILED" if a failure marker found,
        "IN_PROGRESS" otherwise (no terminal marker found)
    """
    # Check the last 50 lines for terminal markers — they appear at the end
    tail = log_lines[-50:] if len(log_lines) > 50 else log_lines

    for line in reversed(tail):
        if ECS_DEPLOYMENT_COMPLETE in line:
            return "COMPLETE"
        for marker in ECS_DEPLOYMENT_FAILED_MARKERS:
            if marker in line:
                return "FAILED"

    # Also scan full log for failure markers in case they appear mid-stream
    for line in log_lines:
        for marker in ECS_DEPLOYMENT_FAILED_MARKERS:
            if marker in line:
                return "FAILED"

    return "IN_PROGRESS"


def extract_create_failed_error(logs_content: str) -> str:
    """Extract the first CREATE_FAILED error from CodeBuild logs."""
    if not logs_content:
        return None
    lines = logs_content.split("\n")
    for line in lines:
        if "CREATE_FAILED" in line:
            clean_line = line.strip()
            if clean_line:
                return clean_line
    return None


def truncate_logs(logs_content: str, max_size: int = 50000) -> str:
    """Truncate log content to prevent memory issues."""
    if len(logs_content) <= max_size:
        return logs_content
    keep_size = max_size // 2 - 100
    first_part = logs_content[:keep_size]
    last_part = logs_content[-keep_size:]
    truncation_message = f"\n\n... [TRUNCATED: {len(logs_content) - (2 * keep_size)} characters removed] ...\n\n"
    return first_part + truncation_message + last_part


# Validate pipeline name format
def validate_pipeline_name_local(name: str) -> tuple[bool, str]:
    if not name or not isinstance(name, str):
        return False, "Pipeline name cannot be empty"
    if len(name) > 100:
        return (
            False,
            f"Pipeline name too long ({len(name)} characters). Maximum is 100 characters",
        )
    import re

    if not re.match(r"^[a-zA-Z0-9._-]+$", name):
        invalid_chars = set(name) - set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        return (
            False,
            f"Pipeline name contains invalid characters: {', '.join(sorted(invalid_chars))}. Only letters, numbers, periods, underscores, and hyphens are allowed",
        )
    return True, ""


# Validate execution ID format if provided
def validate_execution_id_local(exec_id: str) -> tuple[bool, str]:
    if not exec_id or not isinstance(exec_id, str):
        return False, "Execution ID cannot be empty"
    import re

    uuid_pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    if not re.match(uuid_pattern, exec_id):
        return (
            False,
            "Invalid execution ID format. Expected UUID format (e.g., 12345678-1234-1234-1234-123456789012)",
        )
    return True, ""


def validate_qualifier(qualifier: str) -> tuple[bool, str]:
    """Validate LZA Accelerator Qualifier format.

    Qualifiers are alphanumeric with hyphens, used to scope external pipeline deployments.

    Args:
        qualifier: The qualifier string to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not qualifier or not isinstance(qualifier, str):
        return False, "Qualifier cannot be empty"
    import re

    if len(qualifier) > 100:
        return (
            False,
            f"Qualifier too long ({len(qualifier)} characters). Maximum is 100 characters",
        )
    if not re.match(r"^[a-zA-Z0-9-]+$", qualifier):
        return (
            False,
            "Qualifier can only contain letters, numbers, and hyphens",
        )
    return True, ""
