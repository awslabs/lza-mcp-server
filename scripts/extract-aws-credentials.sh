#!/bin/bash
# Script to extract AWS credentials from credential_process and pass to docker
set -e

# Configuration
PROFILE="${AWS_PROFILE:-lza-mcp-server}"
REGION="${AWS_REGION:-us-east-1}"
DEBUG="${DEBUG:-false}"

# Debug logging function
debug_log() {
    if [[ "$DEBUG" == "true" ]]; then
        echo "[DEBUG] $1" >&2
    fi
}

debug_log "Starting credential extraction for profile: $PROFILE"

# Check if AWS CLI is available
if ! command -v aws >/dev/null 2>&1; then
    echo "[ERROR] AWS CLI not found. Please install AWS CLI first." >&2
    exit 1
fi

# Extract credentials using the profile (handles credential_process)
debug_log "Extracting credentials using aws configure export-credentials..."
TEMP_CREDS=$(aws configure export-credentials --profile "$PROFILE" --format env 2>/dev/null) || {
    echo "[ERROR] Failed to get credentials for profile '$PROFILE'" >&2
    echo "[ERROR] Make sure the profile exists and credential_process is configured correctly" >&2
    exit 1
}

# Export credentials to current environment
debug_log "Setting credentials in environment..."
eval "$TEMP_CREDS"

# Validate that credentials were actually set
if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "[ERROR] Failed to extract valid credentials from profile '$PROFILE'" >&2
    echo "[ERROR] AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY is empty" >&2
    exit 1
fi

# Set AWS_REGION if not already set by credentials
export AWS_REGION="${AWS_REGION:-$REGION}"

debug_log "Successfully extracted credentials"
debug_log "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:10}..."
debug_log "AWS_REGION: $AWS_REGION"

# Execute whatever command was passed to us with the credentials now set
debug_log "Executing command: $*"
exec "$@"