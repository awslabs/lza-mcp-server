DEFAULT_REGION = "us-east-1"
DEFAULT_PIPELINE_NAME = "AWSAccelerator-Pipeline"
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
