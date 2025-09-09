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

"""Error handling utilities for structured error responses."""

import time
from typing import Dict, Any, List, Optional


def create_structured_error_response(
    error: str,
    category: str,
    error_code: str = None,
    troubleshooting: List[str] = None,
    context: Dict[str, Any] = None,
    operation: str = None,
) -> Dict[str, Any]:
    """
    Create a structured error response with troubleshooting guidance.

    This function ensures consistent error reporting across all operations
    without any fallback mechanisms - clear error reporting only.

    Args:
        error: Specific error message
        category: Error category (connectivity, configuration, s3, integration)
        error_code: AWS or system error code
        troubleshooting: List of actionable troubleshooting steps
        context: Additional context information
        operation: The operation that failed

    Returns:
        Structured error response dictionary
    """
    response = {
        "success": False,
        "error": error,
        "category": category,
        "troubleshooting": troubleshooting or [],
        "context": context or {},
    }

    if error_code:
        response["error_code"] = error_code

    if operation:
        response["operation"] = operation

    # Add timestamp for error tracking
    response["timestamp"] = int(time.time())

    return response


def format_error_response(
    error: str,
    message: str,
    error_code: Optional[str] = None,
    troubleshooting: Optional[list] = None,
) -> Dict[str, Any]:
    """Format an error response with consistent structure and troubleshooting guidance.

    Args:
        error: The specific error that occurred
        message: User-friendly error message
        error_code: AWS error code if applicable
        troubleshooting: List of troubleshooting steps

    Returns:
        Dict containing success=False, error details, and troubleshooting guidance
    """
    response = {"success": False, "error": error, "message": message}

    if error_code:
        response["error_code"] = error_code

    if troubleshooting:
        response["troubleshooting"] = troubleshooting
    else:
        # Default troubleshooting steps
        response["troubleshooting"] = [
            "Ensure AWS credentials are configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)",
            "Check if AWS_REGION is set correctly",
            "Verify IAM permissions for CodePipeline operations",
            "Confirm the pipeline name exists in the specified region",
        ]

    return response
