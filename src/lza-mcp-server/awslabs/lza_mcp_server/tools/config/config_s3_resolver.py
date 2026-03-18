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

"""Resolve S3 bucket name and object key for LZA configuration.

Centralises the logic that maps deployment type + qualifier to the correct
S3 coordinates.  Both getLzaConfiguration and putLzaConfiguration delegate
to this module so the naming rules live in one place.

Bucket naming (from LZA installer source):
  Standard (no qualifier):  aws-accelerator-config-{account_id}-{region}
  External pipeline:        {qualifier}-config-{account_id}-{region}

Object key:
  Standard (CodePipeline):  zipped/aws-accelerator-config.zip
  External pipeline (ECS):  lza/aws-accelerator-config.zip
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.constants import (
    BUCKET_NAME_PATTERN,
    DEFAULT_REGION,
    QUALIFIER_BUCKET_NAME_PATTERN,
    QUALIFIER_S3_OBJECT_KEY,
    S3_OBJECT_KEY,
)

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


@dataclass(frozen=True)
class ConfigS3Location:
    """Resolved S3 coordinates for an LZA configuration."""

    bucket_name: str
    object_key: str
    account_id: str
    region: str
    qualifier: Optional[str]


def resolve_config_location(
    account_id: str,
    region: str,
    qualifier: Optional[str] = None,
    bucket_name_override: Optional[str] = None,
) -> ConfigS3Location:
    """Resolve the S3 bucket name and object key for an LZA configuration.

    Args:
        account_id: AWS account ID (12 digits)
        region: AWS region (e.g. us-east-1)
        qualifier: Accelerator Qualifier for external pipeline deployments.
                   When provided, uses qualifier-based bucket and key patterns.
        bucket_name_override: Explicit bucket name that takes precedence over
                              any computed value.

    Returns:
        ConfigS3Location with the resolved bucket, key, and metadata.
    """
    if bucket_name_override:
        # Explicit bucket always wins; infer key from qualifier presence
        object_key = QUALIFIER_S3_OBJECT_KEY if qualifier else S3_OBJECT_KEY
        logger.info(
            "Using explicit bucket override: %s (key=%s)",
            bucket_name_override,
            object_key,
        )
        return ConfigS3Location(
            bucket_name=bucket_name_override,
            object_key=object_key,
            account_id=account_id,
            region=region,
            qualifier=qualifier,
        )

    if qualifier:
        bucket_name = QUALIFIER_BUCKET_NAME_PATTERN.format(
            qualifier=qualifier, account_id=account_id, region=region
        )
        object_key = QUALIFIER_S3_OBJECT_KEY
    else:
        bucket_name = BUCKET_NAME_PATTERN.format(account_id=account_id, region=region)
        object_key = S3_OBJECT_KEY

    logger.info(
        "Resolved config location: s3://%s/%s (qualifier=%s)",
        bucket_name,
        object_key,
        qualifier,
    )
    return ConfigS3Location(
        bucket_name=bucket_name,
        object_key=object_key,
        account_id=account_id,
        region=region,
        qualifier=qualifier,
    )


def get_caller_identity() -> dict:
    """Return account_id and region from the current AWS session."""
    session = get_aws_session()
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    return {
        "account_id": identity["Account"],
        "user_arn": identity["Arn"],
        "region": session.region_name or AWS_REGION,
    }
