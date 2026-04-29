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
