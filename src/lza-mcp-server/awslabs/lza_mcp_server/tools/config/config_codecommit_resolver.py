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

"""Resolve CodeCommit repository name and branch for LZA configuration.

Centralises the logic that maps a deployment (standard or qualifier-based) to
the correct CodeCommit repository and branch.  Both getLzaConfiguration and
putLzaConfiguration delegate to this module when a CodeCommit source is in use.

Auto-detection strategy:
  When repository_name is not supplied, inspect the CodePipeline source action
  for the relevant pipeline.  If the source action type is "CodeCommit", extract
  the RepositoryName and BranchName from the action configuration.

  Standard pipeline:  AWSAccelerator-Pipeline (or LZA_PREFIX-Pipeline)
  External pipeline:  {qualifier}-pipeline

Note: GetFolder returns at most 1000 entries per call.  For LZA configurations
this limit is never approached in practice, but callers should be aware of it.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.constants import DEFAULT_PIPELINE_NAME, DEFAULT_REGION

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


@dataclass(frozen=True)
class ConfigCodeCommitLocation:
    """Resolved CodeCommit coordinates for an LZA configuration."""

    repository_name: str
    branch: str
    qualifier: Optional[str]


def _get_pipeline_name(qualifier: Optional[str]) -> str:
    """Return the CodePipeline name for the given qualifier (or the default)."""
    if qualifier:
        return f"{qualifier}-pipeline"
    return DEFAULT_PIPELINE_NAME


def _detect_codecommit_source(
    session: Any,
    pipeline_name: str,
    region: str,
) -> Optional[ConfigCodeCommitLocation]:
    """Inspect a CodePipeline definition and return CodeCommit source details.

    Walks the pipeline stages looking for a source action whose provider is
    "CodeCommit".  Returns None if the pipeline does not exist, the source is
    not CodeCommit, or the call fails.

    Args:
        session: Active boto3 session.
        pipeline_name: Name of the CodePipeline to inspect.
        region: AWS region to query.

    Returns:
        ConfigCodeCommitLocation if a CodeCommit source is found, else None.
    """
    try:
        cp_client = session.client("codepipeline", region_name=region)
        response = cp_client.get_pipeline(name=pipeline_name)
        stages = response.get("pipeline", {}).get("stages", [])

        for stage in stages:
            for action in stage.get("actions", []):
                action_type = action.get("actionTypeId", {})
                if (
                    action_type.get("category") == "Source"
                    and action_type.get("provider") == "CodeCommit"
                ):
                    config = action.get("configuration", {})
                    repo_name = config.get("RepositoryName")
                    branch = config.get("BranchName", "main")
                    if repo_name:
                        logger.info(
                            "Auto-detected CodeCommit source: repo=%s branch=%s pipeline=%s",
                            repo_name,
                            branch,
                            pipeline_name,
                        )
                        return ConfigCodeCommitLocation(
                            repository_name=repo_name,
                            branch=branch,
                            qualifier=None,
                        )

        logger.info("No CodeCommit source action found in pipeline '%s'", pipeline_name)
        return None

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "PipelineNotFoundException":
            logger.info("Pipeline '%s' not found during auto-detection", pipeline_name)
        else:
            logger.warning(
                "Error inspecting pipeline '%s' for CodeCommit source: %s",
                pipeline_name,
                str(e),
            )
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error during CodeCommit auto-detection for pipeline '%s': %s",
            pipeline_name,
            str(e),
        )
        return None


def resolve_codecommit_location(
    qualifier: Optional[str] = None,
    repository_name: Optional[str] = None,
    branch: Optional[str] = None,
) -> Optional[ConfigCodeCommitLocation]:
    """Resolve the CodeCommit repository and branch for an LZA configuration.

    Resolution order:
    1. Explicit repository_name (and optional branch) — used as-is.
    2. Auto-detection via CodePipeline source action inspection.
    3. Returns None if neither succeeds (caller should fall back to S3).

    When branch is not supplied and auto-detection is not used, defaults to
    "main".

    Args:
        qualifier: Accelerator Qualifier for external pipeline deployments.
        repository_name: Explicit repository name override.
        branch: Explicit branch name override.  Defaults to "main" when
                repository_name is provided without a branch.

    Returns:
        ConfigCodeCommitLocation, or None if CodeCommit source cannot be
        determined.
    """
    # Explicit repository name — no detection needed
    if repository_name:
        resolved_branch = branch or "main"
        logger.info(
            "Using explicit CodeCommit location: repo=%s branch=%s",
            repository_name,
            resolved_branch,
        )
        return ConfigCodeCommitLocation(
            repository_name=repository_name,
            branch=resolved_branch,
            qualifier=qualifier,
        )

    # Auto-detect from CodePipeline
    session = get_aws_session()
    pipeline_name = _get_pipeline_name(qualifier)
    location = _detect_codecommit_source(session, pipeline_name, AWS_REGION)

    if location and qualifier:
        # Re-attach qualifier to the detected location
        return ConfigCodeCommitLocation(
            repository_name=location.repository_name,
            branch=branch or location.branch,
            qualifier=qualifier,
        )

    if location and branch:
        # Override branch if caller specified one
        return ConfigCodeCommitLocation(
            repository_name=location.repository_name,
            branch=branch,
            qualifier=None,
        )

    return location
