import logging
import os
from typing import Dict, Any

from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import get_aws_account_id, get_aws_session
from awslabs.lza_mcp_server.constants import DEFAULT_REGION, BUCKET_PREFIX

logger = logging.getLogger(__name__)

# AWS Configuration
VALIDATION_BUCKET = os.environ.get("LZA_MCP_VALIDATION_BUCKET", None)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


def get_validation_bucket():
    """Get or create a bucket for validation configurations."""
    bucket_name = VALIDATION_BUCKET
    region = AWS_REGION

    if not bucket_name:
        account_id = get_aws_account_id()
        bucket_name = f"{BUCKET_PREFIX}-{account_id}-{region}"
        logger.info(f"Using default validation bucket name: {bucket_name}")

    session = get_aws_session()
    s3_client = session.client("s3")

    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"Validation bucket exists: {bucket_name}")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            logger.info(f"Creating validation bucket: {bucket_name}")

            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )

            # Add lifecycle policy
            lifecycle_config = {
                "Rules": [
                    {
                        "Status": "Enabled",
                        "ID": "DeleteOldValidationFiles",
                        "Expiration": {"Days": 1},
                        "Filter": {"Prefix": "validations/"},
                    }
                ]
            }
            s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name, LifecycleConfiguration=lifecycle_config
            )

            # Add tags
            s3_client.put_bucket_tagging(
                Bucket=bucket_name,
                Tagging={
                    "TagSet": [
                        {"Key": "Purpose", "Value": "LZA-MCP-Validation"},
                        {"Key": "CreatedBy", "Value": "LZA-MCP-Server"},
                    ]
                },
            )

            logger.info(f"Successfully created validation bucket: {bucket_name}")
        else:
            logger.warning(f"Error checking validation bucket: {str(e)}")
            raise

    return bucket_name


async def tool_setup_s3_bucket(ctx: Context, bucket_name: str = "") -> Dict[str, Any]:
    """Set up an S3 bucket for LZA configuration validation.

    Creates or verifies an S3 bucket that will be used for storing LZA configuration files
    during the validation process. The bucket is automatically configured with:

    - Lifecycle policies to clean up old validation files (1 day retention)
    - Appropriate tags for identification and management
    - Regional configuration based on the AWS_REGION setting

    If no bucket name is provided, a default name will be generated using the pattern:
    awslabs-lza-mcp-server-{account-id}-{region}

    Args:
        bucket_name (str, optional): Optional custom bucket name. If not provided, uses default naming convention

    Returns:
        Dictionary containing bucket setup status, final bucket name, and upload instructions

    Examples:

    Set up bucket with default name:
    ```python
    # Let the system create a bucket with default naming
    result = await setupS3Bucket()
    if result["success"]:
        bucket_name = result["bucket_name"]
        print(f"✅ S3 bucket ready: {bucket_name}")
        print("Upload instructions:")
        print(result["upload_instructions"]["zip_command"])
        print(result["upload_instructions"]["upload_command"])
    ```
    Most common usage - let the system handle bucket naming

    Set up bucket with custom name:
    ```python
    # Use a specific bucket name
    result = await setupS3Bucket(bucket_name="my-lza-validation-bucket")
    if result["success"]:
        print(f"✅ Custom bucket ready: {result['bucket_name']}")
    ```
    Use when you need a specific bucket name for organizational requirements
    """
    await ctx.info("Setting up S3 bucket for validation...")

    try:
        if bucket_name:
            # Use custom bucket name
            global VALIDATION_BUCKET
            VALIDATION_BUCKET = bucket_name
            await ctx.info(f"Using custom bucket name: {bucket_name}")

        # Get or create the validation bucket
        final_bucket_name = get_validation_bucket()

        await ctx.info(f"S3 bucket ready: {final_bucket_name}")

        region = AWS_REGION
        return {
            "success": True,
            "bucket_name": final_bucket_name,
            "region": region,
            "message": f"S3 bucket '{final_bucket_name}' is ready for validation",
            "upload_instructions": {
                "zip_command": "cd /path/to/your/lza/config && zip -r ~/tmp/lza-validation/lza-config.zip .",
                "upload_command": f"aws s3 cp ~/tmp/lza-validation/lza-config.zip s3://{final_bucket_name}/validations/lza-config.zip",
            },
        }

    except Exception as e:
        error_message = f"Failed to set up S3 bucket: {str(e)}"
        await ctx.error(error_message)

        return {
            "success": False,
            "error": str(e),
            "message": error_message,
            "troubleshooting": [
                "Ensure AWS credentials have S3 permissions",
                "Check if the bucket name is available (if using custom name)",
                "Verify AWS region is accessible",
            ],
        }
