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

"""LZA deployment type detection via SSM, CodePipeline, and ECS discovery."""

import logging
import re
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

logger = logging.getLogger(__name__)

# SSM path constants
_SSM_PREFIX = "/accelerator"
_LZA_PREFIX_PARAM_SUFFIX = "lza-prefix"

# Deployment type constants
DEPLOYMENT_TYPE_STANDARD = "standard"
DEPLOYMENT_TYPE_EXTERNAL_PIPELINE = "external_pipeline"

# External pipeline runner constants
RUNNER_CODEPIPELINE = "codepipeline"
RUNNER_ECS_CONTAINER = "ecs_container"
RUNNER_UNKNOWN = "unknown"


def _extract_qualifier_from_param_name(param_name: str) -> Optional[str]:
    """Extract the qualifier segment from a scoped SSM parameter path.

    For a path like /accelerator/{qualifier}/lza-prefix, returns the qualifier.
    Returns None if the path does not match the expected scoped pattern.
    """
    # Match /accelerator/{qualifier}/lza-prefix — qualifier must be a single path segment
    match = re.match(
        r"^/accelerator/([^/]+)/lza-prefix$",
        param_name,
    )
    return match.group(1) if match else None


def _detect_runner_for_qualifier(
    session: boto3.Session,
    qualifier: str,
    region: str,
) -> str:
    """Determine whether a qualifier uses CodePipeline or ECS container runner.

    Checks CodePipeline first (cheap list call), then ECS. Both are treated as
    non-fatal — a service error or empty result just means that signal is
    inconclusive for that check.

    Args:
        session: Active boto3 session
        qualifier: The LZA Accelerator Qualifier (e.g. "container-dev-1")
        region: AWS region to query

    Returns:
        One of RUNNER_CODEPIPELINE, RUNNER_ECS_CONTAINER, or RUNNER_UNKNOWN
    """
    # Check CodePipeline — look for any pipeline whose name contains the qualifier
    try:
        cp_client = session.client("codepipeline", region_name=region)
        paginator = cp_client.get_paginator("list_pipelines")
        for page in paginator.paginate():
            for pipeline in page.get("pipelines", []):
                if qualifier.lower() in pipeline["name"].lower():
                    logger.info(
                        "Found CodePipeline pipeline '%s' for qualifier '%s'",
                        pipeline["name"],
                        qualifier,
                    )
                    return RUNNER_CODEPIPELINE
        logger.info("No CodePipeline pipelines found for qualifier '%s'", qualifier)
    except (ClientError, EndpointResolutionError) as e:
        # CodePipeline may not be available in all regions — treat as inconclusive
        logger.info(
            "CodePipeline check inconclusive for qualifier '%s': %s", qualifier, str(e)
        )

    # Check ECS — look for a cluster whose name contains the qualifier
    try:
        ecs_client = session.client("ecs", region_name=region)
        paginator = ecs_client.get_paginator("list_clusters")
        for page in paginator.paginate():
            for cluster_arn in page.get("clusterArns", []):
                # Cluster name is the last segment of the ARN
                cluster_name = cluster_arn.split("/")[-1]
                if qualifier.lower() in cluster_name.lower():
                    logger.info(
                        "Found ECS cluster '%s' for qualifier '%s'",
                        cluster_name,
                        qualifier,
                    )
                    return RUNNER_ECS_CONTAINER
        logger.info("No ECS clusters found for qualifier '%s'", qualifier)
    except (ClientError, EndpointResolutionError) as e:
        logger.info("ECS check inconclusive for qualifier '%s': %s", qualifier, str(e))

    return RUNNER_UNKNOWN


def detect_lza_deployment(
    session: boto3.Session,
    region: str,
) -> Dict[str, Any]:
    """Detect the LZA deployment type and enumerate pipeline qualifiers.

    Detection strategy (in order of precedence):
    1. SSM DescribeParameters with BeginsWith /accelerator to find lza-prefix params.
       - Root path /accelerator/lza-prefix → standard management account deployment.
       - Scoped paths /accelerator/{qualifier}/lza-prefix → external pipeline deployment.
    2. For each external pipeline qualifier, check CodePipeline then ECS to determine
       the runner type. Both checks fail gracefully.

    Args:
        session: Active boto3 session with appropriate credentials
        region: AWS region to query

    Returns:
        Dictionary with deployment_type, qualifiers (if external), runner details,
        and next_steps guidance for the LLM/agent.
    """
    logger.info("Starting LZA deployment type detection in region %s", region)

    ssm_client = session.client("ssm", region_name=region)

    # Collect all /accelerator/.../lza-prefix parameter names
    root_lza_prefix_found = False
    qualifier_params: List[str] = []

    try:
        paginator = ssm_client.get_paginator("describe_parameters")
        for page in paginator.paginate(
            ParameterFilters=[
                {
                    "Key": "Name",
                    "Option": "BeginsWith",
                    "Values": [_SSM_PREFIX],
                }
            ]
        ):
            for param in page.get("Parameters", []):
                name: str = param["Name"]
                if name == f"{_SSM_PREFIX}/{_LZA_PREFIX_PARAM_SUFFIX}":
                    root_lza_prefix_found = True
                elif name.endswith(f"/{_LZA_PREFIX_PARAM_SUFFIX}"):
                    qualifier = _extract_qualifier_from_param_name(name)
                    if qualifier:
                        qualifier_params.append(qualifier)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error("SSM DescribeParameters failed: %s", str(e))
        return {
            "success": False,
            "deployment_type": None,
            "error": str(e),
            "error_code": error_code,
            "message": "Failed to query SSM parameters for deployment detection",
            "troubleshooting": [
                "Ensure the IAM role has ssm:DescribeParameters permission",
                f"Resource: arn:aws:ssm:{region}:*:parameter/accelerator/*",
            ],
        }
    except Exception as e:
        logger.error("Unexpected error during SSM query: %s", str(e))
        return {
            "success": False,
            "deployment_type": None,
            "error": str(e),
            "message": "Unexpected error during deployment type detection",
            "troubleshooting": [
                "Check network connectivity to AWS SSM service",
                "Verify AWS region configuration",
            ],
        }

    # Standard deployment: root /accelerator/lza-prefix exists
    if root_lza_prefix_found:
        logger.info("Detected standard management account deployment")
        return {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_STANDARD,
            "message": "Standard LZA deployment detected (management account)",
            "next_steps": [
                "This is a standard LZA deployment running from the management account.",
                "You can use pipeline tools with the default pipeline name.",
            ],
        }

    # External pipeline deployment: only scoped qualifier paths found
    if qualifier_params:
        logger.info(
            "Detected external pipeline deployment with qualifiers: %s",
            qualifier_params,
        )

        # Detect runner type for each qualifier
        qualifier_details = []
        for qualifier in qualifier_params:
            runner = _detect_runner_for_qualifier(session, qualifier, region)
            qualifier_details.append(
                {
                    "qualifier": qualifier,
                    "runner": runner,
                }
            )
            logger.info("Qualifier '%s' uses runner: %s", qualifier, runner)

        qualifiers_list = ", ".join(f"'{q}'" for q in qualifier_params)
        next_steps = [
            f"This is an external pipeline LZA deployment with {len(qualifier_params)} "
            f"qualifier(s) found: [{qualifiers_list}].",
            "Each qualifier represents an independent LZA pipeline environment with its own "
            "infrastructure (pipelines, S3 buckets, SSM parameters).",
            "Ask the user which qualifier they want to work with before proceeding if qualifiers identified.",
            "Once the qualifier is confirmed, pass it to subsequent tools that require it.",
        ]

        return {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
            "qualifiers": qualifier_details,
            "qualifier_names": qualifier_params,
            "message": f"External pipeline LZA deployment detected with {len(qualifier_params)} qualifier(s)",
            "next_steps": next_steps,
        }

    # No LZA SSM parameters found at all
    logger.warning("No LZA deployment SSM parameters found in region %s", region)
    return {
        "success": False,
        "deployment_type": None,
        "message": f"No LZA deployment detected in region {region}",
        "troubleshooting": [
            "Verify LZA has been installed in this AWS account and region",
            f"Check that SSM parameters exist under /accelerator/ in region {region}",
            "Ensure the configured AWS credentials belong to the correct account",
            "For standard deployments: check the management account",
            "For external pipeline deployments: check the pipeline account",
        ],
    }
