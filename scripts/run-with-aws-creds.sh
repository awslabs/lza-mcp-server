#!/bin/bash
set -e

# Export AWS credentials from current environment or profile
aws configure export-credentials --profile "${AWS_PROFILE:-lza-mcp-server}" --format env | source /dev/stdin

# Run container with all AWS_* environment variables
exec finch run --rm --interactive \
  $(env | grep '^AWS_' | sed 's/^/-e /') \
  -e FASTMCP_LOG_LEVEL=INFO \
  lza-mcp-server:local "$@"