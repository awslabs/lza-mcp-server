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

"""S3 Configuration Upload tools for the LZA MCP Server."""

import asyncio
import logging
import os
from typing import Dict, Any

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import (
    get_aws_session,
    get_aws_account_id,
)
from awslabs.lza_mcp_server.utils.error_handling import (
    create_structured_error_response,
)
from awslabs.lza_mcp_server.constants import (
    DEFAULT_REGION,
    BUCKET_NAME_PATTERN,
    S3_OBJECT_KEY,
    AWS_OPERATION_TIMEOUT,
)
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.common import categorize_aws_error
from awslabs.lza_mcp_server.utils.timeout_utils import with_timeout, TimeoutError

logger = logging.getLogger(__name__)
AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


class S3Manager:
    """Handles S3 operations and bucket management."""

    def __init__(self):
        """Initialize S3Manager with AWS session management."""
        self.logger = logger
        self._session = None
        self._s3_client = None

    def _get_session(self):
        """Get AWS session using existing session management."""
        if self._session is None:
            self._session = get_aws_session()
        return self._session

    def _get_s3_client(self):
        """Get S3 client using existing session management."""
        if self._s3_client is None:
            session = self._get_session()
            self._s3_client = session.client("s3")
        return self._s3_client

    async def determine_bucket_name(
        self, account_id: str = None, region: str = None
    ) -> str:
        """
        Determine the appropriate S3 bucket name using existing AWS functions.

        Constructs bucket name using the pattern: aws-accelerator-config-<accountID>-<region>
        This follows the standard LZA bucket naming convention.

        Args:
            account_id: Optional account ID, will use get_aws_account_id() if not provided
            region: Optional region, will use AWS_REGION if not provided

        Returns:
            Constructed bucket name following LZA pattern

        Raises:
            Exception: If unable to determine account ID or region
        """
        try:
            # Use existing AWS functions to get account ID and region
            if account_id is None:
                account_id = get_aws_account_id()
            if region is None:
                region = AWS_REGION

            # Validate inputs
            if not account_id or not region:
                raise ValueError(
                    f"Invalid AWS context - Account ID: {account_id}, Region: {region}"
                )

            bucket_name = BUCKET_NAME_PATTERN.format(
                account_id=account_id, region=region
            )

            self.logger.info(f"Determined default bucket name: {bucket_name}")
            return bucket_name

        except Exception as e:
            self.logger.error(f"Failed to determine bucket name: {str(e)}")
            raise

    async def verify_bucket_exists(self, bucket_name: str) -> bool:
        """
        Verify that the specified S3 bucket exists and is accessible.

        Timeout Protection (T-005, T-012):
        - Operation timeout: AWS_OPERATION_TIMEOUT (300s)
        - Prevents hanging on unresponsive S3 endpoints

        Args:
            bucket_name: Name of the S3 bucket to verify

        Returns:
            True if bucket exists and is accessible, False otherwise

        Raises:
            S3UploadError: If there's an access issue or other S3 error with structured information
            TimeoutError: If operation exceeds timeout limit
        """
        try:
            s3_client = self._get_s3_client()

            # Wrap S3 operation with timeout protection (T-005, T-012)
            async def _check_bucket():
                return await asyncio.get_event_loop().run_in_executor(
                    None, lambda: s3_client.head_bucket(Bucket=bucket_name)
                )

            await with_timeout(
                _check_bucket(),
                timeout=AWS_OPERATION_TIMEOUT,
                operation_name=f"S3 bucket verification for '{bucket_name}'",
            )

            self.logger.info(f"Bucket exists and is accessible: {bucket_name}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                self.logger.warning(f"Bucket does not exist: {bucket_name}")
                return False
            elif error_code == "403":
                self.logger.error(f"Access denied to bucket: {bucket_name}")
                raise S3UploadError(
                    message=f"Access denied to bucket '{bucket_name}'. Check your AWS permissions.",
                    category=ErrorCategory.S3,
                    error_code="AccessDenied",
                    troubleshooting=[
                        f"Verify you have access permissions to bucket '{bucket_name}'",
                        "Check IAM policies for s3:ListBucket permission",
                        "Ensure the bucket exists in your AWS account",
                        "Verify the bucket is in the same region as your AWS session",
                    ],
                    context={
                        "bucket_name": bucket_name,
                        "operation": "bucket_verification",
                    },
                )
            else:
                error_info = categorize_aws_error(e)
                self.logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
                raise S3UploadError(
                    message=f"Failed to verify bucket '{bucket_name}': {str(e)}",
                    category=error_info["category"],
                    error_code=error_info["error_code"],
                    troubleshooting=error_info["troubleshooting"],
                    context={
                        "bucket_name": bucket_name,
                        "operation": "bucket_verification",
                    },
                )

        except TimeoutError as e:
            # Handle timeout errors specifically (T-005, T-012)
            self.logger.error(
                f"Bucket verification timed out for {bucket_name}: {str(e)}"
            )
            raise S3UploadError(
                message=f"Bucket verification timed out after {AWS_OPERATION_TIMEOUT} seconds for '{bucket_name}'",
                category=ErrorCategory.S3,
                error_code="BUCKET_VERIFICATION_TIMEOUT",
                troubleshooting=[
                    "Check network connectivity to AWS S3",
                    "Verify the bucket name is correct",
                    "Check if AWS S3 service is experiencing issues",
                    "Try again with a shorter timeout or better network connection",
                ],
                context={
                    "bucket_name": bucket_name,
                    "operation": "bucket_verification",
                    "timeout_seconds": AWS_OPERATION_TIMEOUT,
                },
            )

        except Exception as e:
            self.logger.error(
                f"Unexpected error checking bucket {bucket_name}: {str(e)}"
            )
            raise S3UploadError(
                message=f"Unexpected error verifying bucket '{bucket_name}': {str(e)}",
                category=ErrorCategory.S3,
                error_code="UNEXPECTED_BUCKET_ERROR",
                troubleshooting=[
                    "Check network connectivity to AWS S3",
                    "Verify AWS credentials are properly configured",
                    "Ensure the bucket name follows AWS S3 naming conventions",
                    "Check system resources and try again",
                ],
                context={
                    "bucket_name": bucket_name,
                    "operation": "bucket_verification",
                    "error_type": type(e).__name__,
                },
            )

    async def validate_custom_bucket_name(self, bucket_name: str) -> Dict[str, Any]:
        """
        Validate a custom bucket name provided by the user.

        This method checks if the provided bucket name is valid and accessible,
        following AWS S3 naming rules and verifying permissions.

        Args:
            bucket_name: Custom bucket name provided by user

        Returns:
            Dictionary with validation results and any errors
        """
        try:
            # Basic bucket name validation (AWS S3 rules)
            if not bucket_name:
                return {
                    "valid": False,
                    "error": "Bucket name cannot be empty",
                    "error_type": "validation",
                }

            if len(bucket_name) < 3 or len(bucket_name) > 63:
                return {
                    "valid": False,
                    "error": "Bucket name must be between 3 and 63 characters long",
                    "error_type": "validation",
                }

            if not bucket_name.islower():
                return {
                    "valid": False,
                    "error": "Bucket name must be lowercase",
                    "error_type": "validation",
                }

            # Check if bucket exists and is accessible
            bucket_exists = await self.verify_bucket_exists(bucket_name)

            if not bucket_exists:
                return {
                    "valid": False,
                    "error": f"Bucket '{bucket_name}' does not exist or is not accessible",
                    "error_type": "access",
                    "troubleshooting": [
                        f"Verify the bucket '{bucket_name}' exists in your AWS account",
                        "Check that you have access permissions to the bucket",
                        "Ensure the bucket is in the same region as your AWS session",
                    ],
                }

            # If we get here, the bucket is valid and accessible
            self.logger.info(
                f"Custom bucket name validated successfully: {bucket_name}"
            )
            return {
                "valid": True,
                "bucket_name": bucket_name,
                "message": f"Bucket '{bucket_name}' is valid and accessible",
            }

        except Exception as e:
            self.logger.error(
                f"Error validating custom bucket name '{bucket_name}': {str(e)}"
            )
            return {
                "valid": False,
                "error": f"Failed to validate bucket name: {str(e)}",
                "error_type": "unexpected",
                "troubleshooting": [
                    "Check your AWS credentials and permissions",
                    "Verify network connectivity to AWS S3",
                    "Ensure the bucket name follows AWS S3 naming conventions",
                ],
            }

    async def prompt_for_custom_bucket_name(
        self, default_bucket_name: str, account_id: str, region: str
    ) -> Dict[str, Any]:
        """
        Generate a structured response to prompt user for custom bucket name.

        This method returns a structured response that indicates the user needs to provide
        a custom bucket name since the default bucket doesn't exist. The calling system
        (like Kiro) will handle the actual user interaction.

        Args:
            default_bucket_name: The default bucket name that doesn't exist
            account_id: AWS account ID for context
            region: AWS region for context

        Returns:
            Dictionary with prompt information and guidance for the user
        """
        return {
            "action_required": "user_input",
            "input_type": "bucket_name",
            "prompt": f"The default S3 bucket '{default_bucket_name}' does not exist. Please provide a custom bucket name:",
            "context": {
                "default_bucket": default_bucket_name,
                "account_id": account_id,
                "region": region,
                "bucket_pattern": BUCKET_NAME_PATTERN,
            },
            "guidance": [
                f"The default bucket '{default_bucket_name}' was not found in your AWS account",
                "You can either:",
                f"  1. Create the bucket '{default_bucket_name}' in region {region}",
                "  2. Provide an existing bucket name that you have write access to",
                "  3. Use a different bucket that follows your organization's naming convention",
            ],
            "validation_requirements": [
                "Bucket name must be globally unique",
                "Bucket must exist in the same region as your AWS session",
                "You must have s3:PutObject permission for the bucket",
                "Bucket name must follow AWS S3 naming rules (lowercase, no spaces, etc.)",
            ],
            "suggested_actions": [
                f"Create bucket: aws s3 mb s3://{default_bucket_name} --region {region}",
                "Or provide an existing bucket name when prompted",
            ],
        }

    async def upload_zip_file(
        self, zip_path: str, bucket_name: str, key: str = S3_OBJECT_KEY
    ) -> Dict[str, Any]:
        """
        Upload ZIP file to S3 bucket with progress reporting and upload verification.

        Timeout Protection (T-005, T-012):
        - Operation timeout: AWS_OPERATION_TIMEOUT (300s)
        - Prevents hanging on large file uploads or slow connections
        - Ensures responsive behavior even with network issues

        Args:
            zip_path: Local path to the ZIP file
            bucket_name: Target S3 bucket name
            key: S3 object key (defaults to standard LZA key)

        Returns:
            Dictionary with upload results including success status and details

        Raises:
            ClientError: If S3 upload fails
            FileNotFoundError: If ZIP file doesn't exist
            TimeoutError: If operation exceeds timeout limit
        """
        import time
        import hashlib

        try:
            # Verify ZIP file exists
            if not os.path.exists(zip_path):
                raise FileNotFoundError(f"ZIP file not found: {zip_path}")

            # Get file size for progress reporting
            file_size = os.path.getsize(zip_path)
            self.logger.info(
                f"Preparing to upload {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)"
            )

            # Calculate SHA-256 hash for verification
            self.logger.info("Calculating file checksum for verification...")
            sha256_hash = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            local_sha256 = sha256_hash.hexdigest()
            self.logger.info(f"Local file SHA-256: {local_sha256}")

            # Upload using existing S3 client
            s3_client = self._get_s3_client()

            self.logger.info(
                f"Starting upload of {zip_path} to s3://{bucket_name}/{key}"
            )
            start_time = time.time()

            # Perform the upload with metadata and timeout protection (T-005, T-012)
            extra_args = {
                "Metadata": {
                    "original-filename": os.path.basename(zip_path),
                    "upload-timestamp": str(int(time.time())),
                    "file-size": str(file_size),
                    "sha256-checksum": local_sha256,
                }
            }

            # Wrap S3 upload with timeout protection
            async def _upload_file():
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: s3_client.upload_file(
                        zip_path, bucket_name, key, ExtraArgs=extra_args
                    ),
                )

            await with_timeout(
                _upload_file(),
                timeout=AWS_OPERATION_TIMEOUT,
                operation_name=f"S3 upload to s3://{bucket_name}/{key}",
            )

            upload_time = time.time() - start_time
            upload_speed = file_size / upload_time if upload_time > 0 else 0

            self.logger.info(
                f"Upload completed in {upload_time:.2f} seconds ({upload_speed / 1024 / 1024:.2f} MB/s)"
            )

            # Verify upload by checking object existence and size with timeout protection
            self.logger.info("Verifying upload...")
            try:
                # Wrap verification with timeout
                async def _verify_upload():
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: s3_client.head_object(Bucket=bucket_name, Key=key)
                    )

                response = await with_timeout(
                    _verify_upload(),
                    timeout=AWS_OPERATION_TIMEOUT,
                    operation_name=f"S3 upload verification for s3://{bucket_name}/{key}",
                )
                uploaded_size = response["ContentLength"]
                uploaded_etag = response["ETag"].strip('"')

                # Verify file size matches
                if uploaded_size != file_size:
                    raise ValueError(
                        f"Size mismatch: local={file_size}, uploaded={uploaded_size}"
                    )

                # For single-part uploads, ETag is the MD5 hash (AWS limitation)
                # We store SHA-256 in metadata but can only compare size for verification
                self.logger.info("Upload verification successful - file size matches")
                verification_status = "size_verified"

            except ClientError as verify_error:
                self.logger.warning(f"Upload verification failed: {verify_error}")
                verification_status = "upload_completed_verification_failed"

            self.logger.info(
                f"Successfully uploaded {file_size} bytes to s3://{bucket_name}/{key}"
            )

            return {
                "success": True,
                "bucket_name": bucket_name,
                "object_key": key,
                "file_size": file_size,
                "upload_time": upload_time,
                "upload_speed_mbps": upload_speed / 1024 / 1024,
                "verification_status": verification_status,
                "local_sha256": local_sha256,
                "uploaded_etag": uploaded_etag if "uploaded_etag" in locals() else None,
                "message": f"Successfully uploaded configuration to s3://{bucket_name}/{key}",
            }

        except TimeoutError as e:
            # Handle timeout errors specifically (T-005, T-012)
            error_message = (
                f"S3 upload timed out after {AWS_OPERATION_TIMEOUT} seconds: {str(e)}"
            )
            self.logger.error(error_message)

            error_response = create_structured_error_response(
                error=error_message,
                category=ErrorCategory.S3,
                error_code="S3_UPLOAD_TIMEOUT",
                troubleshooting=[
                    "Check network connectivity to AWS S3",
                    "Verify the file size is reasonable for upload",
                    "Consider using multipart upload for large files",
                    "Check if AWS S3 service is experiencing issues",
                    "Try again with a better network connection",
                ],
                context={
                    "bucket_name": bucket_name,
                    "object_key": key,
                    "file_size": file_size if "file_size" in locals() else None,
                    "operation": "s3_upload",
                    "timeout_seconds": AWS_OPERATION_TIMEOUT,
                },
                operation="s3_upload",
            )

            return error_response

        except ClientError as e:
            error_info = categorize_aws_error(e)
            error_message = f"S3 upload failed: {str(e)}"
            self.logger.error(error_message)

            # Create structured error response
            error_response = create_structured_error_response(
                error=error_message,
                category=error_info["category"],
                error_code=error_info["error_code"],
                troubleshooting=error_info["troubleshooting"],
                context={
                    "bucket_name": bucket_name,
                    "object_key": key,
                    "file_size": file_size if "file_size" in locals() else None,
                    "operation": "s3_upload",
                },
                operation="s3_upload",
            )

            return error_response

        except FileNotFoundError as e:
            error_message = f"ZIP file not found: {str(e)}"
            self.logger.error(error_message)

            error_response = create_structured_error_response(
                error=error_message,
                category=ErrorCategory.CONFIGURATION,
                error_code="ZIP_FILE_NOT_FOUND",
                troubleshooting=[
                    "Verify the ZIP file path is correct",
                    "Ensure the ZIP file was created successfully",
                    "Check file system permissions",
                    "Verify the configuration ZIP creation process completed",
                ],
                context={"zip_path": zip_path, "operation": "s3_upload"},
                operation="s3_upload",
            )

            return error_response

        except Exception as e:
            error_message = f"Unexpected error during upload: {str(e)}"
            self.logger.error(error_message)

            error_response = create_structured_error_response(
                error=error_message,
                category=ErrorCategory.S3,
                error_code="UNEXPECTED_UPLOAD_ERROR",
                troubleshooting=[
                    "Check system resources and disk space",
                    "Verify network connectivity to AWS S3",
                    "Check AWS credentials configuration",
                    "Ensure the ZIP file is not corrupted",
                    "Try the upload operation again",
                ],
                context={
                    "bucket_name": bucket_name,
                    "object_key": key,
                    "zip_path": zip_path,
                    "operation": "s3_upload",
                    "error_type": type(e).__name__,
                },
                operation="s3_upload",
            )

            return error_response
