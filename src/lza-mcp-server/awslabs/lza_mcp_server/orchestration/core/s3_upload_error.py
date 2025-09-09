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


import logging
import os
from typing import Dict, Any, List

from awslabs.lza_mcp_server.constants import DEFAULT_REGION

# MCP framework components

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


class S3UploadError(Exception):
    """Custom exception for S3 upload operations with structured error information."""

    def __init__(
        self,
        message: str,
        category: str,
        error_code: str = None,
        troubleshooting: List[str] = None,
        context: Dict[str, Any] = None,
    ):
        """
        Initialize S3UploadError with structured error information.

        Args:
            message: Human-readable error message
            category: Error category (connectivity, configuration, s3, integration)
            error_code: Specific error code for programmatic handling
            troubleshooting: List of troubleshooting steps
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.error_code = error_code
        self.troubleshooting = troubleshooting or []
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to structured dictionary format."""
        return {
            "success": False,
            "error": self.message,
            "error_code": self.error_code,
            "category": self.category,
            "troubleshooting": self.troubleshooting,
            "context": self.context,
        }
