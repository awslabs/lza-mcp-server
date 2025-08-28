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
            f"Invalid execution ID format. Expected UUID format (e.g., 12345678-1234-1234-1234-123456789012), got: {exec_id}",
        )
    return True, ""
