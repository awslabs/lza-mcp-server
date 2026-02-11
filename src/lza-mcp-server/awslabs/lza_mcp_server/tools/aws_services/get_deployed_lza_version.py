# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Dict, Any

from mcp.server.fastmcp import Context
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import get_aws_session, handle_aws_error
from awslabs.lza_mcp_server.constants import DEFAULT_REGION, LZA_PREFIX

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)
LZA_VERSION_SSM_PARAMETER = f"/accelerator/{LZA_PREFIX}-InstallerStack/version"


async def tool_get_deployed_lza_version(ctx: Context) -> Dict[str, Any]:
    """Get the currently deployed LZA version from the environment.

    This tool retrieves the LZA version that is currently deployed in your AWS environment
    by reading the SSM parameter that stores the installer stack version. It first checks
    AWS connectivity, then queries the SSM parameter in the home region.

    The tool will:
    1. Verify AWS credentials are properly configured
    2. Retrieve the LZA version from SSM Parameter Store
    3. Return version information and metadata

    Returns:
        Dictionary containing the deployed LZA version, region, and metadata

    Examples:

    Get deployed LZA version:
    ```python
    # Check what version of LZA is currently deployed
    result = await getDeployedLzaVersion()
    if result["success"]:
        print(f"Deployed LZA version: {result['version']}")
        print(f"Region: {result['region']}")
    else:
        print(f"Failed to retrieve version: {result['message']}")
    ```
    """
    await ctx.info("Retrieving deployed LZA version from SSM Parameter Store...")

    try:
        # Get AWS session
        session = get_aws_session()

        # First verify connectivity
        try:
            sts_client = session.client("sts")
            identity = sts_client.get_caller_identity()
            account_id = identity["Account"]
            await ctx.info(f"Connected to AWS account: {account_id}")
        except Exception as e:
            error_response = handle_aws_error(e, "AWS connectivity check")
            return {
                "success": False,
                **error_response,
            }

        # Get SSM client
        ssm_client = session.client("ssm")

        # Retrieve the LZA version parameter
        try:
            response = ssm_client.get_parameter(Name=LZA_VERSION_SSM_PARAMETER)

            raw_version = response["Parameter"]["Value"]
            parameter_type = response["Parameter"]["Type"]
            last_modified = response["Parameter"]["LastModifiedDate"]
            parameter_arn = response["Parameter"]["ARN"]

            # Normalize version format: ensure it has 'v' prefix for schema compatibility
            # SSM parameter may return "1.13.0" but schemas use "v1.13.0"
            normalized_version = (
                raw_version if raw_version.startswith("v") else f"v{raw_version}"
            )

            await ctx.info(
                f"Successfully retrieved LZA version: {raw_version} (normalized: {normalized_version})"
            )

            return {
                "success": True,
                "version": normalized_version,
                "raw_version": raw_version,
                "region": AWS_REGION,
                "account_id": account_id,
                "parameter_name": LZA_VERSION_SSM_PARAMETER,
                "parameter_type": parameter_type,
                "last_modified": last_modified.isoformat(),
                "parameter_arn": parameter_arn,
                "message": f"LZA version {normalized_version} is deployed in region {AWS_REGION}",
                "note": "Version is normalized with 'v' prefix for schema compatibility",
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code == "ParameterNotFound":
                await ctx.error(
                    f"LZA version parameter not found: {LZA_VERSION_SSM_PARAMETER}"
                )
                return {
                    "success": False,
                    "error": "ParameterNotFound",
                    "message": f"LZA version parameter not found in region {AWS_REGION}",
                    "parameter_name": LZA_VERSION_SSM_PARAMETER,
                    "troubleshooting": [
                        "The LZA installer stack may not be deployed in this region",
                        f"Verify that LZA is installed in region: {AWS_REGION}",
                        "Check if the SSM parameter exists using AWS CLI:",
                        f"  aws ssm get-parameter --name {LZA_VERSION_SSM_PARAMETER} --region {AWS_REGION}",
                        "Ensure you're using the correct home region for your LZA deployment",
                        "The parameter is created during LZA installation",
                    ],
                }
            elif error_code == "AccessDeniedException":
                await ctx.error("Access denied when retrieving LZA version parameter")
                return {
                    "success": False,
                    "error": "AccessDeniedException",
                    "message": "Insufficient permissions to read SSM parameter",
                    "parameter_name": LZA_VERSION_SSM_PARAMETER,
                    "troubleshooting": [
                        "Ensure your AWS credentials have the required IAM permissions:",
                        "  - ssm:GetParameter",
                        f"  - Resource: arn:aws:ssm:{AWS_REGION}:{account_id}:parameter/accelerator/*",
                        "",
                        "Sample IAM policy:",
                        "{",
                        '  "Version": "2012-10-17",',
                        '  "Statement": [',
                        "    {",
                        '      "Effect": "Allow",',
                        '      "Action": "ssm:GetParameter",',
                        f'      "Resource": "arn:aws:ssm:{AWS_REGION}:{account_id}:parameter/accelerator/*"',
                        "    }",
                        "  ]",
                        "}",
                    ],
                }
            else:
                error_response = handle_aws_error(e, "retrieving LZA version from SSM")
                return {
                    "success": False,
                    "parameter_name": LZA_VERSION_SSM_PARAMETER,
                    **error_response,
                }

    except Exception as e:
        error_message = f"Unexpected error retrieving LZA version: {str(e)}"
        await ctx.error(error_message)
        return {
            "success": False,
            "error": str(e),
            "message": error_message,
            "parameter_name": LZA_VERSION_SSM_PARAMETER,
            "troubleshooting": [
                "Check network connectivity to AWS services",
                "Verify AWS region configuration",
                "Ensure boto3 and botocore are up to date",
                "Review application logs for more details",
            ],
        }
