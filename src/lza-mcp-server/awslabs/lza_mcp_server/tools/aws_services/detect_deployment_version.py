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

"""LZA deployment version detection via SSM parameter discovery.

Discovers the installed LZA version for both standard and external pipeline
deployments by reading the installer stack version SSM parameter.

SSM parameter naming (from LZA installer source):
  Standard:  /{prefix}/{StackName}/version
  Qualified: /{prefix}/{qualifier}/{StackName}/version

Where StackName is the CloudFormation stack name, which differs between
installer types (e.g. AWSAccelerator-InstallerStack vs
AWSAccelerator-InstallerContainerStack).
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import get_aws_session, handle_aws_error
from awslabs.lza_mcp_server.constants import DEFAULT_REGION, LZA_PREFIX
from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_type import (
    DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
    DEPLOYMENT_TYPE_STANDARD,
    detect_lza_deployment,
)

logger = logging.getLogger(__name__)

# SSM path prefix used by LZA for all parameters
_SSM_PREFIX = "/accelerator"

# Pattern to match installer version parameters created by LZA stacks.
# Both installer-stack.ts and installer-container-stack.ts write:
#   /{prefix}/{StackName}/version  (standard)
#   /{prefix}/{qualifier}/{StackName}/version  (external pipeline)
_INSTALLER_VERSION_PATTERN = re.compile(
    r"^/accelerator/(?:.+/)?.*Installer.*Stack.*/version$"
)


def _normalize_version(raw_version: str) -> str:
    """Ensure version string has 'v' prefix for schema compatibility."""
    return raw_version if raw_version.startswith("v") else f"v{raw_version}"


def _find_version_param_for_standard(
    ssm_client: boto3.client,
) -> Optional[Dict[str, Any]]:
    """Find the installer version SSM parameter for a standard deployment.

    Tries the well-known path first (/{prefix}/{prefix}-InstallerStack/version).
    If not found, falls back to scanning /accelerator/ for any parameter matching
    the installer version pattern at the root level (no qualifier segment).

    Args:
        ssm_client: Configured SSM client

    Returns:
        SSM Parameter dict from GetParameter response, or None if not found.
    """
    # Try the well-known path first — cheapest call
    well_known = f"{_SSM_PREFIX}/{LZA_PREFIX}-InstallerStack/version"
    try:
        response = ssm_client.get_parameter(Name=well_known)
        logger.info("Found standard version parameter at %s", well_known)
        return response["Parameter"]
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ParameterNotFound":
            raise
        logger.info("Well-known parameter %s not found, scanning...", well_known)

    # Fallback: scan for any installer version param at root level
    try:
        paginator = ssm_client.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=_SSM_PREFIX, Recursive=True):
            for param in page.get("Parameters", []):
                name = param["Name"]
                if _INSTALLER_VERSION_PATTERN.match(name):
                    # Root-level: path has exactly 3 segments (/accelerator/{Stack}/version)
                    segments = name.strip("/").split("/")
                    if len(segments) == 3:
                        logger.info("Found standard version parameter: %s", name)
                        return param
    except ClientError:
        raise

    return None


def _find_version_param_for_qualifier(
    ssm_client: boto3.client,
    qualifier: str,
) -> Optional[Dict[str, Any]]:
    """Find the installer version SSM parameter for a specific qualifier.

    Scans /accelerator/{qualifier}/ for any parameter matching the installer
    version pattern. This handles both CodePipeline (InstallerStack) and
    Container (InstallerContainerStack) deployments.

    Args:
        ssm_client: Configured SSM client
        qualifier: The LZA Accelerator Qualifier (e.g. "container-dev-1")

    Returns:
        SSM Parameter dict from GetParametersByPath response, or None if not found.
    """
    path = f"{_SSM_PREFIX}/{qualifier}"
    try:
        paginator = ssm_client.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=path, Recursive=True):
            for param in page.get("Parameters", []):
                if _INSTALLER_VERSION_PATTERN.match(param["Name"]):
                    logger.info(
                        "Found version parameter for qualifier '%s': %s",
                        qualifier,
                        param["Name"],
                    )
                    return param
    except ClientError:
        raise

    return None


def detect_deployment_version(
    session: boto3.Session,
    region: str,
    deployment: Dict[str, Any],
) -> Dict[str, Any]:
    """Detect the installed LZA version based on the deployment type.

    Uses the deployment detection result (from detect_lza_deployment) to know
    whether to look for a standard or qualifier-scoped version parameter.

    For standard deployments, returns a single version.
    For external pipeline deployments, returns a version per qualifier.

    Args:
        session: Active boto3 session
        region: AWS region to query
        deployment: Result dict from detect_lza_deployment()

    Returns:
        Dictionary with:
        - success: bool
        - version: normalized version string (standard) or None (external)
        - raw_version: original value from SSM
        - parameter_name: SSM parameter path
        - last_modified: ISO timestamp
        - qualifier_versions: list of per-qualifier version dicts (external only)
        - deployment_type: echoed from input
    """
    deployment_type = deployment.get("deployment_type")

    if not deployment.get("success") or deployment_type is None:
        return {
            "success": False,
            "version": None,
            "deployment_type": None,
            "message": "Cannot detect version: deployment type detection failed",
            "troubleshooting": deployment.get("troubleshooting", []),
        }

    ssm_client = session.client("ssm", region_name=region)

    if deployment_type == DEPLOYMENT_TYPE_STANDARD:
        return _detect_standard_version(ssm_client, region)

    if deployment_type == DEPLOYMENT_TYPE_EXTERNAL_PIPELINE:
        qualifiers = deployment.get("qualifier_names", [])
        return _detect_external_version(ssm_client, region, qualifiers)

    return {
        "success": False,
        "version": None,
        "deployment_type": deployment_type,
        "message": f"Unsupported deployment type: {deployment_type}",
        "troubleshooting": [
            "Expected 'standard' or 'external_pipeline' deployment type",
        ],
    }


def _detect_standard_version(
    ssm_client: boto3.client,
    region: str,
) -> Dict[str, Any]:
    """Detect version for a standard management-account deployment."""
    try:
        param = _find_version_param_for_standard(ssm_client)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return {
            "success": False,
            "version": None,
            "deployment_type": DEPLOYMENT_TYPE_STANDARD,
            "error": str(e),
            "error_code": error_code,
            "message": f"Failed to retrieve version parameter: {error_code}",
            "troubleshooting": _ssm_troubleshooting(region, error_code),
        }

    if param is None:
        return {
            "success": False,
            "version": None,
            "deployment_type": DEPLOYMENT_TYPE_STANDARD,
            "message": f"No installer version parameter found in region {region}",
            "troubleshooting": [
                "The LZA installer stack may not be deployed in this region",
                f"Verify that LZA is installed in region: {region}",
                "Ensure you're using the correct home region for your LZA deployment",
            ],
        }

    return _format_version_result(param, DEPLOYMENT_TYPE_STANDARD, region)


def _detect_external_version(
    ssm_client: boto3.client,
    region: str,
    qualifiers: List[str],
) -> Dict[str, Any]:
    """Detect version for each qualifier in an external pipeline deployment."""
    qualifier_versions: List[Dict[str, Any]] = []
    errors: List[str] = []

    for qualifier in qualifiers:
        try:
            param = _find_version_param_for_qualifier(ssm_client, qualifier)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            errors.append(f"Qualifier '{qualifier}': {error_code} - {str(e)}")
            qualifier_versions.append(
                {
                    "qualifier": qualifier,
                    "success": False,
                    "version": None,
                    "error": str(e),
                }
            )
            continue

        if param is None:
            qualifier_versions.append(
                {
                    "qualifier": qualifier,
                    "success": False,
                    "version": None,
                    "message": f"No installer version parameter found for qualifier '{qualifier}'",
                }
            )
            continue

        raw = param["Value"]
        last_modified = param.get("LastModifiedDate")
        qualifier_versions.append(
            {
                "qualifier": qualifier,
                "success": True,
                "version": _normalize_version(raw),
                "raw_version": raw,
                "parameter_name": param["Name"],
                "last_modified": last_modified.isoformat() if last_modified else None,
            }
        )

    # Determine overall success: at least one qualifier resolved
    any_success = any(qv["success"] for qv in qualifier_versions)

    result: Dict[str, Any] = {
        "success": any_success,
        "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
        "qualifier_versions": qualifier_versions,
        "region": region,
    }

    if any_success:
        # Pick the first successful qualifier as the primary version
        first_ok = next(qv for qv in qualifier_versions if qv["success"])
        result["version"] = first_ok["version"]
        result["raw_version"] = first_ok["raw_version"]
        result["parameter_name"] = first_ok["parameter_name"]
        result["message"] = (
            f"LZA version {first_ok['version']} detected for qualifier "
            f"'{first_ok['qualifier']}' in region {region}"
        )
    else:
        result["version"] = None
        result["message"] = "No installer version found for any qualifier"
        result["troubleshooting"] = [
            "Verify the external pipeline installer stack has been deployed",
            f"Check SSM parameters under /accelerator/{{qualifier}}/ in region {region}",
        ] + errors

    return result


def _format_version_result(
    param: Dict[str, Any],
    deployment_type: str,
    region: str,
) -> Dict[str, Any]:
    """Build a success result dict from an SSM Parameter."""
    raw = param["Value"]
    last_modified = param.get("LastModifiedDate")
    return {
        "success": True,
        "version": _normalize_version(raw),
        "raw_version": raw,
        "deployment_type": deployment_type,
        "region": region,
        "parameter_name": param["Name"],
        "last_modified": last_modified.isoformat() if last_modified else None,
        "message": f"LZA version {_normalize_version(raw)} detected in region {region}",
    }


def _ssm_troubleshooting(region: str, error_code: str) -> List[str]:
    """Return troubleshooting steps for SSM errors."""
    steps = [
        f"Check SSM parameter access in region {region}",
        "Ensure IAM role has ssm:GetParameter and ssm:GetParametersByPath permissions",
        f"Resource: arn:aws:ssm:{region}:*:parameter/accelerator/*",
    ]
    if error_code == "AccessDeniedException":
        steps.insert(
            0, "Access denied — verify IAM permissions for SSM Parameter Store"
        )
    return steps


AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


async def tool_get_deployed_lza_version(ctx: Context) -> Dict[str, Any]:
    """Get the currently deployed LZA version from the environment.

    This tool retrieves the LZA version that is currently deployed in your AWS environment
    by first detecting the deployment type (standard vs external pipeline) and then reading
    the appropriate SSM parameter that stores the installer stack version.

    The tool will:
    1. Verify AWS credentials are properly configured
    2. Detect the deployment type (standard or external pipeline with qualifiers)
    3. Retrieve the LZA version from the correct SSM parameter
    4. Return version information and metadata

    For external pipeline deployments with multiple qualifiers, the tool returns
    version information for each qualifier.

    Returns:
        Dictionary containing the deployed LZA version, region, deployment type, and metadata

    Examples:

    Get deployed LZA version:
    ```python
    result = await getDeployedLzaVersion()
    if result["success"]:
        print(f"Deployed LZA version: {result['version']}")
        print(f"Deployment type: {result['deployment_type']}")
        print(f"Region: {result['region']}")
    else:
        print(f"Failed to retrieve version: {result['message']}")
    ```
    """
    await ctx.info("Retrieving deployed LZA version...")

    try:
        session = get_aws_session()

        # Verify connectivity
        try:
            sts_client = session.client("sts")
            identity = sts_client.get_caller_identity()
            account_id = identity["Account"]
            await ctx.info(f"Connected to AWS account: {account_id}")
        except Exception as e:
            error_response = handle_aws_error(e, "AWS connectivity check")
            return {"success": False, **error_response}

        # Detect deployment type
        await ctx.info("Detecting deployment type...")
        deployment = detect_lza_deployment(session, AWS_REGION)

        if not deployment.get("success"):
            await ctx.error(f"Deployment detection failed: {deployment.get('message')}")
            return {
                "success": False,
                "account_id": account_id,
                "region": AWS_REGION,
                "message": deployment.get(
                    "message", "Deployment type detection failed"
                ),
                "troubleshooting": deployment.get("troubleshooting", []),
            }

        deployment_type = deployment.get("deployment_type")
        await ctx.info(f"Deployment type: {deployment_type}")

        # Detect version
        await ctx.info("Reading version from SSM Parameter Store...")
        version_result = detect_deployment_version(session, AWS_REGION, deployment)

        # Enrich with account info
        version_result["account_id"] = account_id
        version_result["region"] = AWS_REGION

        if version_result.get("success"):
            await ctx.info(
                f"LZA version: {version_result['version']} "
                f"(deployment type: {deployment_type})"
            )
            version_result["note"] = (
                "Version is normalized with 'v' prefix for schema compatibility"
            )
        else:
            await ctx.error(
                f"Version detection failed: {version_result.get('message')}"
            )

        return version_result

    except Exception as e:
        error_message = f"Unexpected error retrieving LZA version: {str(e)}"
        await ctx.error(error_message)
        return {
            "success": False,
            "error": str(e),
            "message": error_message,
            "troubleshooting": [
                "Check network connectivity to AWS services",
                "Verify AWS region configuration",
                "Ensure boto3 and botocore are up to date",
                "Review application logs for more details",
            ],
        }
