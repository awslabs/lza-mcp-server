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

"""Shared utilities for the LZA MCP Server."""

import os
import logging
import boto3

logger = logging.getLogger(__name__)

# AWS Configuration
DEFAULT_REGION = "us-east-1"


def get_aws_region():
    """Get AWS region using boto3's default resolution chain."""
    # Try environment variable first
    region = os.environ.get("AWS_REGION")
    if region:
        return region

    # Try AWS_DEFAULT_REGION (used by AWS CLI)
    region = os.environ.get("AWS_DEFAULT_REGION")
    if region:
        return region

    # Try boto3's session default region resolution
    try:
        session = boto3.Session()
        region = session.region_name
        if region:
            return region
    except Exception as e:
        logger.debug(f"Could not determine region from boto3 session: {e}")

    # Fall back to default
    logger.warning(f"No region configured, using default: {DEFAULT_REGION}")
    return DEFAULT_REGION


def get_aws_session():
    """Create an AWS session using boto3's default credential provider chain."""
    region = get_aws_region()
    logger.info(f"Creating AWS session with region: {region}")
    return boto3.Session(region_name=region)


def download_from_s3(bucket: str, key: str, local_path: str) -> bool:
    """
    Download a file from S3 to a local path.

    Args:
        bucket: The S3 bucket name
        key: The S3 object key
        local_path: The local file path to save to

    Returns:
        bool: True if successful, False otherwise
    """
    session = get_aws_session()
    s3_client = session.client("s3")

    try:
        s3_client.download_file(bucket, key, local_path)
        logger.info(f"Successfully downloaded {bucket}/{key} to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {bucket}/{key}: {str(e)}")
        return False
