import logging
import os
from typing import Any, Dict

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.constants import DEFAULT_REGION
from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_type import (
    detect_lza_deployment,
)

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_check_aws_connectivity(ctx: Context) -> Dict[str, Any]:
    """Check AWS connectivity and detect the LZA deployment type.

    This tool verifies that AWS credentials are properly configured and can access AWS services.
    It's the first step in the validation workflow and should be called before any other AWS operations.

    Beyond credential verification, it also detects which type of LZA deployment is present:
    - Standard deployment (running from the management account)
    - External pipeline deployment (one or more independent pipeline environments identified
      by their Accelerator Qualifier)

    For external pipeline deployments with multiple qualifiers, the tool returns the full list
    and instructs the agent to ask the user which qualifier to use before proceeding.

    Returns:
        Dictionary containing connectivity status, AWS account information, LZA deployment
        type details, and troubleshooting guidance if connection fails.

    Examples:

    Basic connectivity check:
    ```python
    result = await checkAwsConnectivity()
    if result["connected"]:
        print(f"Connected to AWS account: {result['account_id']}")
        print(f"Deployment type: {result['deployment']['deployment_type']}")
    else:
        print(f"Connection failed: {result['message']}")
    ```
    Use this as the first step before any AWS operations.
    """
    await ctx.info("Checking AWS connectivity...")

    try:
        session = get_aws_session()
        sts_client = session.client("sts")

        # Verify credentials via STS
        identity = sts_client.get_caller_identity()

        account_id = identity["Account"]
        user_arn = identity["Arn"]
        user_id = identity["UserId"]

        await ctx.info(f"Successfully connected to AWS account: {account_id}")

        region = AWS_REGION

        # Detect LZA deployment type
        await ctx.info("Detecting LZA deployment type...")
        deployment = detect_lza_deployment(session, region)
        logger.info(
            "Deployment detection result: %s", deployment.get("deployment_type")
        )

        if deployment.get("success"):
            await ctx.info(f"Deployment detected: {deployment.get('message')}")
        else:
            await ctx.info(
                f"Deployment detection inconclusive: {deployment.get('message')}"
            )

        return {
            "connected": True,
            "account_id": account_id,
            "user_arn": user_arn,
            "user_id": user_id,
            "region": region,
            "message": f"Successfully connected to AWS account {account_id} in region {region}",
            "deployment": deployment,
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
