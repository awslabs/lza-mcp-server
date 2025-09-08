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

"""S3 upload tools and error categorization utilities."""

from typing import Dict, Any
from botocore.exceptions import ClientError
from awslabs.lza_mcp_server.error_categories import ErrorCategory


def categorize_aws_error(error: Exception) -> Dict[str, Any]:
    """Categorize AWS errors for structured error handling.

    Args:
        error: The AWS error to categorize

    Returns:
        Dictionary with error category, code, and troubleshooting information
    """
    if isinstance(error, ClientError):
        error_code = error.response["Error"]["Code"]

        if error_code in ["NoSuchBucket", "BucketNotFound"]:
            return {
                "category": ErrorCategory.S3,
                "error_code": "BUCKET_NOT_FOUND",
                "troubleshooting": [
                    "Verify the bucket name is correct",
                    "Check that the bucket exists in your AWS account",
                    "Ensure the bucket is in the same region as your AWS session",
                ],
            }
        elif error_code in ["AccessDenied", "Forbidden"]:
            return {
                "category": ErrorCategory.S3,
                "error_code": "ACCESS_DENIED",
                "troubleshooting": [
                    "Check IAM permissions for S3 operations",
                    "Verify bucket policies allow your access",
                    "Ensure you have the required S3 permissions",
                ],
            }
        elif error_code in ["InvalidBucketName"]:
            return {
                "category": ErrorCategory.S3,
                "error_code": "INVALID_BUCKET_NAME",
                "troubleshooting": [
                    "Check bucket name follows AWS S3 naming conventions",
                    "Bucket names must be 3-63 characters long",
                    "Use only lowercase letters, numbers, periods, and hyphens",
                ],
            }
        else:
            return {
                "category": ErrorCategory.S3,
                "error_code": error_code,
                "troubleshooting": [
                    f"AWS S3 error: {error_code}",
                    "Check AWS documentation for this error code",
                    "Verify your AWS credentials and permissions",
                ],
            }
    else:
        return {
            "category": ErrorCategory.SYSTEM,
            "error_code": "UNEXPECTED_ERROR",
            "troubleshooting": [
                "Check system resources and network connectivity",
                "Verify AWS credentials are properly configured",
                "Try the operation again",
            ],
        }


def categorize_configuration_error(error: Exception) -> Dict[str, Any]:
    """Categorize configuration-related errors for structured error handling.

    Args:
        error: The configuration error to categorize

    Returns:
        Dictionary with error category, code, and troubleshooting information
    """
    if isinstance(error, FileNotFoundError):
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "FILE_NOT_FOUND",
            "troubleshooting": [
                "Verify the file path is correct",
                "Check that the file exists and is accessible",
                "Ensure proper file permissions",
            ],
        }
    elif isinstance(error, PermissionError):
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "PERMISSION_DENIED",
            "troubleshooting": [
                "Check file and directory permissions",
                "Ensure you have read/write access to the configuration files",
                "Run with appropriate user privileges",
            ],
        }
    elif isinstance(error, OSError):
        return {
            "category": ErrorCategory.SYSTEM,
            "error_code": "SYSTEM_ERROR",
            "troubleshooting": [
                "Check system resources and disk space",
                "Verify file system integrity",
                "Check for system-level issues",
            ],
        }
    else:
        return {
            "category": ErrorCategory.CONFIGURATION,
            "error_code": "CONFIGURATION_ERROR",
            "troubleshooting": [
                "Check configuration file format and syntax",
                "Verify all required configuration files are present",
                "Review configuration documentation",
            ],
        }
