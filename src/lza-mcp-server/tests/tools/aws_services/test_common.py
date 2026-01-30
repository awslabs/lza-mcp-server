# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for aws_services/common.py error categorization."""

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.aws_services.common import (
    categorize_aws_error,
    categorize_configuration_error,
)


class TestCategorizeAwsError:
    """Test AWS error categorization."""

    def test_bucket_not_found_error(self):
        """Test categorization of NoSuchBucket error."""
        error = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "HeadBucket",
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "BUCKET_NOT_FOUND"
        assert "troubleshooting" in result
        assert any("bucket name" in step.lower() for step in result["troubleshooting"])

    def test_bucket_not_found_alternate_code(self):
        """Test categorization of BucketNotFound error."""
        error = ClientError(
            {"Error": {"Code": "BucketNotFound", "Message": "Bucket not found"}},
            "GetObject",
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "BUCKET_NOT_FOUND"
        assert "troubleshooting" in result

    def test_access_denied_error(self):
        """Test categorization of AccessDenied error."""
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "ACCESS_DENIED"
        assert "troubleshooting" in result
        assert any("iam" in step.lower() for step in result["troubleshooting"])

    def test_forbidden_error(self):
        """Test categorization of Forbidden error."""
        error = ClientError(
            {"Error": {"Code": "Forbidden", "Message": "Forbidden"}}, "GetObject"
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "ACCESS_DENIED"
        assert "troubleshooting" in result
        assert any("permissions" in step.lower() for step in result["troubleshooting"])

    def test_invalid_bucket_name_error(self):
        """Test categorization of InvalidBucketName error."""
        error = ClientError(
            {
                "Error": {
                    "Code": "InvalidBucketName",
                    "Message": "The specified bucket is not valid",
                }
            },
            "CreateBucket",
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "INVALID_BUCKET_NAME"
        assert "troubleshooting" in result
        assert any(
            "naming conventions" in step.lower() for step in result["troubleshooting"]
        )

    def test_generic_client_error(self):
        """Test categorization of generic ClientError."""
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "ListBuckets",
        )
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.S3
        assert result["error_code"] == "ThrottlingException"
        assert "troubleshooting" in result
        assert any("ThrottlingException" in step for step in result["troubleshooting"])

    def test_non_client_error(self):
        """Test categorization of non-ClientError exception."""
        error = Exception("Something unexpected happened")
        result = categorize_aws_error(error)

        assert result["category"] == ErrorCategory.SYSTEM
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "troubleshooting" in result
        assert any(
            "system resources" in step.lower() for step in result["troubleshooting"]
        )

    def test_all_results_have_required_fields(self):
        """Test that all error categorizations include required fields."""
        test_errors = [
            ClientError({"Error": {"Code": "NoSuchBucket", "Message": ""}}, "op"),
            ClientError({"Error": {"Code": "AccessDenied", "Message": ""}}, "op"),
            ClientError({"Error": {"Code": "InvalidBucketName", "Message": ""}}, "op"),
            ClientError({"Error": {"Code": "UnknownError", "Message": ""}}, "op"),
            Exception("Generic error"),
        ]

        for error in test_errors:
            result = categorize_aws_error(error)
            assert "category" in result
            assert "error_code" in result
            assert "troubleshooting" in result
            assert isinstance(result["troubleshooting"], list)
            assert len(result["troubleshooting"]) > 0

    def test_troubleshooting_steps_are_actionable(self):
        """Test that troubleshooting steps provide actionable guidance."""
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "op"
        )
        result = categorize_aws_error(error)

        for step in result["troubleshooting"]:
            assert isinstance(step, str)
            assert len(step) > 0
            assert len(step.strip()) > 0


class TestCategorizeConfigurationError:
    """Test configuration error categorization."""

    def test_file_not_found_error(self):
        """Test categorization of FileNotFoundError."""
        error = FileNotFoundError("Configuration file not found")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "troubleshooting" in result
        assert any("file path" in step.lower() for step in result["troubleshooting"])

    def test_permission_error(self):
        """Test categorization of PermissionError."""
        error = PermissionError("Permission denied")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "PERMISSION_DENIED"
        assert "troubleshooting" in result
        assert any("permissions" in step.lower() for step in result["troubleshooting"])

    def test_os_error(self):
        """Test categorization of OSError."""
        error = OSError("Disk full")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.SYSTEM
        assert result["error_code"] == "SYSTEM_ERROR"
        assert "troubleshooting" in result
        assert any(
            "system resources" in step.lower() for step in result["troubleshooting"]
        )

    def test_generic_error(self):
        """Test categorization of generic error."""
        error = Exception("Unknown configuration error")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIGURATION_ERROR"
        assert "troubleshooting" in result
        assert any(
            "configuration" in step.lower() for step in result["troubleshooting"]
        )

    def test_all_results_have_required_fields(self):
        """Test that all error categorizations include required fields."""
        test_errors = [
            FileNotFoundError("File not found"),
            PermissionError("Permission denied"),
            OSError("OS error"),
            Exception("Generic error"),
        ]

        for error in test_errors:
            result = categorize_configuration_error(error)
            assert "category" in result
            assert "error_code" in result
            assert "troubleshooting" in result
            assert isinstance(result["troubleshooting"], list)
            assert len(result["troubleshooting"]) > 0

    def test_troubleshooting_steps_are_actionable(self):
        """Test that troubleshooting steps provide actionable guidance."""
        error = FileNotFoundError("File not found")
        result = categorize_configuration_error(error)

        for step in result["troubleshooting"]:
            assert isinstance(step, str)
            assert len(step) > 0
            assert len(step.strip()) > 0


class TestErrorCategorizationConsistency:
    """Test consistency across error categorization functions."""

    def test_aws_error_categories_are_valid(self):
        """Test that AWS errors use valid error categories."""
        test_errors = [
            ClientError({"Error": {"Code": "NoSuchBucket", "Message": ""}}, "op"),
            ClientError({"Error": {"Code": "AccessDenied", "Message": ""}}, "op"),
            Exception("Generic error"),
        ]

        for error in test_errors:
            result = categorize_aws_error(error)
            assert result["category"] in [ErrorCategory.S3, ErrorCategory.SYSTEM]

    def test_configuration_error_categories_are_valid(self):
        """Test that configuration errors use valid error categories."""
        test_errors = [
            FileNotFoundError("File not found"),
            PermissionError("Permission denied"),
            OSError("OS error"),
            Exception("Generic error"),
        ]

        for error in test_errors:
            result = categorize_configuration_error(error)
            assert result["category"] in [
                ErrorCategory.CONFIGURATION,
                ErrorCategory.SYSTEM,
            ]

    def test_error_codes_are_uppercase(self):
        """Test that error codes follow uppercase convention."""
        aws_error = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": ""}}, "op"
        )
        config_error = FileNotFoundError("File not found")

        aws_result = categorize_aws_error(aws_error)
        config_result = categorize_configuration_error(config_error)

        assert aws_result["error_code"].isupper() or "_" in aws_result["error_code"]
        assert (
            config_result["error_code"].isupper() or "_" in config_result["error_code"]
        )

    def test_troubleshooting_lists_are_non_empty(self):
        """Test that all troubleshooting lists contain at least one step."""
        aws_error = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": ""}}, "op"
        )
        config_error = FileNotFoundError("File not found")

        aws_result = categorize_aws_error(aws_error)
        config_result = categorize_configuration_error(config_error)

        assert len(aws_result["troubleshooting"]) >= 3
        assert len(config_result["troubleshooting"]) >= 3


class TestSpecificErrorGuidance:
    """Test that specific errors provide relevant guidance."""

    def test_bucket_not_found_mentions_region(self):
        """Test that BUCKET_NOT_FOUND mentions region check."""
        error = ClientError({"Error": {"Code": "NoSuchBucket", "Message": ""}}, "op")
        result = categorize_aws_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert "region" in troubleshooting_text.lower()

    def test_access_denied_mentions_iam(self):
        """Test that ACCESS_DENIED mentions IAM permissions."""
        error = ClientError({"Error": {"Code": "AccessDenied", "Message": ""}}, "op")
        result = categorize_aws_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert (
            "iam" in troubleshooting_text.lower()
            or "permissions" in troubleshooting_text.lower()
        )

    def test_invalid_bucket_name_mentions_conventions(self):
        """Test that INVALID_BUCKET_NAME mentions naming conventions."""
        error = ClientError(
            {"Error": {"Code": "InvalidBucketName", "Message": ""}}, "op"
        )
        result = categorize_aws_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert (
            "naming" in troubleshooting_text.lower() or "3-63" in troubleshooting_text
        )

    def test_file_not_found_mentions_path_verification(self):
        """Test that FILE_NOT_FOUND mentions path verification."""
        error = FileNotFoundError("File not found")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert "path" in troubleshooting_text.lower()

    def test_permission_error_mentions_privileges(self):
        """Test that PERMISSION_DENIED mentions privileges."""
        error = PermissionError("Permission denied")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert (
            "permissions" in troubleshooting_text.lower()
            or "privileges" in troubleshooting_text.lower()
        )

    def test_os_error_mentions_system_resources(self):
        """Test that SYSTEM_ERROR mentions system resources."""
        error = OSError("OS error")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert (
            "system" in troubleshooting_text.lower()
            or "disk" in troubleshooting_text.lower()
        )
