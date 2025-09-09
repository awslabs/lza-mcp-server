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

"""Validation utilities for pipeline tools."""

import re
from typing import Tuple


def validate_pipeline_name(pipeline_name: str) -> Tuple[bool, str]:
    """Validate that a pipeline name meets AWS CodePipeline naming requirements.

    Args:
        pipeline_name: The pipeline name to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not pipeline_name:
        return False, "Pipeline name cannot be empty"

    if not isinstance(pipeline_name, str):
        return False, "Pipeline name must be a string"

    # AWS CodePipeline naming rules:
    # - Must be 1-100 characters
    # - Can contain letters, numbers, periods, underscores, and hyphens
    # - Cannot contain spaces or other special characters
    if len(pipeline_name) < 1:
        return False, "Pipeline name cannot be empty"

    if len(pipeline_name) > 100:
        return (
            False,
            f"Pipeline name too long ({len(pipeline_name)} characters). Maximum is 100 characters",
        )

    # Check for valid characters
    if not re.match(r"^[a-zA-Z0-9._-]+$", pipeline_name):
        invalid_chars = set(pipeline_name) - set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        return (
            False,
            f"Pipeline name contains invalid characters: {', '.join(sorted(invalid_chars))}. Only letters, numbers, periods, underscores, and hyphens are allowed",
        )

    return True, ""


def validate_execution_id(execution_id: str) -> Tuple[bool, str]:
    """Validate that an execution ID meets AWS CodePipeline execution ID format.

    Args:
        execution_id: The execution ID to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not execution_id:
        return False, "Execution ID cannot be empty"

    if not isinstance(execution_id, str):
        return False, "Execution ID must be a string"

    # AWS execution IDs are UUIDs (36 characters with hyphens)
    uuid_pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )

    if not re.match(uuid_pattern, execution_id):
        return (
            False,
            f"Invalid execution ID format. Expected UUID format (e.g., 12345678-1234-1234-1234-123456789012), got: {execution_id}",
        )

    return True, ""


def validate_aws_region(region: str) -> Tuple[bool, str]:
    """Validate that an AWS region meets AWS region naming requirements.

    Args:
        region: The AWS region to validate

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not region:
        return False, "AWS region cannot be empty"

    if not isinstance(region, str):
        return False, "AWS region must be a string"

    # AWS region format: us-east-1, eu-west-1, ap-southeast-2, etc.
    region_pattern = r"^[a-z]{2,3}-[a-z]+-[0-9]+$"

    if not re.match(region_pattern, region):
        return (
            False,
            f"Invalid AWS region format. Expected format like 'us-east-1', got: {region}",
        )

    return True, ""
