import os
from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.constants import DEFAULT_REGION

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_check_aws_connectivity(ctx: Context) -> Dict[str, Any]:
    """Check AWS connectivity using configured credentials.

    This tool verifies that AWS credentials are properly configured and can access AWS services.
    It's the first step in the validation workflow and should be called before any other AWS operations.

    The tool will attempt to call AWS STS GetCallerIdentity to verify credentials and return
    information about the AWS account and user/role being used.

    Returns:
        Dictionary containing connectivity status, AWS account information, and troubleshooting guidance if connection fails

    Examples:

    Basic connectivity check:
    ```python
    # Check if AWS credentials are working
    result = await checkAwsConnectivity()
    if result["connected"]:
        print(f"✅ Connected to AWS account: {result['account_id']}")
    else:
        print(f"❌ Connection failed: {result['message']}")
    ```
    Use this as the first step before any AWS operations
    """
    await ctx.info("Checking AWS connectivity...")

    try:
        session = get_aws_session()
        sts_client = session.client("sts")

        # Get caller identity to verify credentials
        identity = sts_client.get_caller_identity()

        account_id = identity["Account"]
        user_arn = identity["Arn"]
        user_id = identity["UserId"]

        await ctx.info(f"Successfully connected to AWS account: {account_id}")

        region = AWS_REGION
        return {
            "connected": True,
            "account_id": account_id,
            "user_arn": user_arn,
            "user_id": user_id,
            "region": region,
            "message": f"Successfully connected to AWS account {account_id} in region {region}",
        }

    except Exception as e:
        error_message = f"AWS connectivity check failed: {str(e)}"
        await ctx.error(error_message)

        return {
            "connected": False,
            "error": str(e),
            "message": error_message,
            "troubleshooting": [
                "Ensure AWS credentials are configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)",
                "Check if AWS_REGION is set correctly",
                "Verify AWS profile is configured if using AWS_PROFILE",
                "For Docker: ensure credentials are passed as environment variables",
            ],
        }
