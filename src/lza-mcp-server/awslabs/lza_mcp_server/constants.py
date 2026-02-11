import os

# LZA Prefix Configuration
# This prefix is used by LZA to name resources (pipelines, stacks, SSM parameters, etc.)
# Default is "AWSAccelerator" but can be customized via LZA_PREFIX environment variable
# Empty or whitespace-only values fall back to default to prevent invalid resource names
_prefix = os.environ.get("LZA_PREFIX", "AWSAccelerator").strip()
LZA_PREFIX = _prefix if _prefix else "AWSAccelerator"

DEFAULT_REGION = "us-east-1"
DEFAULT_PIPELINE_NAME = f"{LZA_PREFIX}-Pipeline"
BUCKET_PREFIX = "awslabs-lza-mcp-server"
ACCOUNT_CONFIG_FILENAME = "accounts-config.yaml"
ORG_CONFIG_FILENAME = "organization-config.yaml"
# S3 Configuration constants
S3_OBJECT_KEY = "zipped/aws-accelerator-config.zip"
BUCKET_NAME_PATTERN = "aws-accelerator-config-{account_id}-{region}"

MAX_LOG_SIZE = 50000  # Maximum log size in characters to prevent memory issues
CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL for pipeline metadata
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0  # Initial delay in seconds for exponential backoff

# Timeout configurations (T-005, T-012 mitigation)
# These timeouts prevent hanging operations and ensure responsive behavior
AWS_CONNECT_TIMEOUT = 10  # Seconds to wait for connection establishment
AWS_READ_TIMEOUT = 60  # Seconds to wait for data from AWS services
AWS_OPERATION_TIMEOUT = 300  # Maximum seconds for any AWS operation (5 minutes)
ASYNC_OPERATION_TIMEOUT = 600  # Maximum seconds for async operations (10 minutes)
FILE_OPERATION_TIMEOUT = 120  # Maximum seconds for file I/O operations (2 minutes)
