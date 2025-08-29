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

"""Unit tests for pipeline_tools module."""

from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
    validate_pipeline_name,
    validate_execution_id,
    validate_aws_region,
    format_success_response,
    get_stage_description,
    get_action_description,
    extract_create_failed_error,
    extract_error_line,
    truncate_logs,
)


class TestValidationFunctions:
    """Test input validation functions."""

    def test_validate_execution_id_valid(self):
        """Test execution ID validation with valid IDs."""
        is_valid, error = validate_execution_id("12345678-1234-1234-1234-123456789012")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_execution_id("abcdef12-3456-7890-abcd-ef1234567890")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_execution_id("ABCDEF12-3456-7890-ABCD-EF1234567890")
        assert is_valid is True
        assert error == ""

    def test_validate_execution_id_invalid(self):
        """Test execution ID validation with invalid IDs."""
        is_valid, error = validate_execution_id("")
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_execution_id("invalid-id")
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id(
            "12345678-1234-1234-1234-12345678901"
        )  # Too short
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id(
            "12345678-1234-1234-1234-1234567890123"
        )  # Too long
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id(
            "12345678-1234-1234-1234-123456789012-extra"
        )  # Extra chars
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id(None)
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_execution_id(123)
        assert is_valid is False
        assert "must be a string" in error

    def test_validate_aws_region_valid(self):
        """Test AWS region validation with valid regions."""
        is_valid, error = validate_aws_region("us-east-1")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_aws_region("eu-west-1")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_aws_region("ap-southeast-2")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_aws_region("ca-central-1")
        assert is_valid is True
        assert error == ""

    def test_validate_aws_region_invalid(self):
        """Test AWS region validation with invalid regions."""
        is_valid, error = validate_aws_region("")
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_aws_region("invalid-region")
        assert is_valid is False
        assert "Invalid AWS region format" in error

        is_valid, error = validate_aws_region("us-east")  # Missing number
        assert is_valid is False
        assert "Invalid AWS region format" in error

        is_valid, error = validate_aws_region("us-east-1-extra")  # Extra parts
        assert is_valid is False
        assert "Invalid AWS region format" in error

        is_valid, error = validate_aws_region("US-EAST-1")  # Wrong case
        assert is_valid is False
        assert "Invalid AWS region format" in error

        is_valid, error = validate_aws_region(None)
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_aws_region(123)
        assert is_valid is False
        assert "must be a string" in error


class TestPipelineToolsCore:
    """Test core utility functions in pipeline_tools."""

    def test_validate_pipeline_name_valid(self):
        """Test pipeline name validation with valid names."""
        is_valid, error = validate_pipeline_name("AWSAccelerator-Pipeline")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name("test-pipeline")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name("pipeline_123")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name("pipeline.test")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name("a")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name("a" * 100)
        assert is_valid is True
        assert error == ""

    def test_validate_pipeline_name_invalid(self):
        """Test pipeline name validation with invalid names."""
        is_valid, error = validate_pipeline_name("")
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_pipeline_name("a" * 101)
        assert is_valid is False
        assert "too long" in error

        is_valid, error = validate_pipeline_name("pipeline with spaces")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name("pipeline@test")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name("pipeline#test")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name(None)
        assert is_valid is False
        assert "cannot be empty" in error

    def test_format_success_response(self):
        """Test success response formatting."""
        data = {"execution_id": "12345", "pipeline_name": "test"}
        message = "Success"

        result = format_success_response(data, message)

        assert result["success"] is True
        assert result["message"] == message
        assert result["execution_id"] == "12345"
        assert result["pipeline_name"] == "test"


class TestUtilityFunctions:
    """Test utility functions for pipeline operations."""

    def test_truncate_logs_no_truncation_needed(self):
        """Test log truncation when content is within limits."""
        short_content = "This is a short log message"
        result = truncate_logs(short_content)

        assert result == short_content
        assert "[TRUNCATED:" not in result

    def test_truncate_logs_with_truncation(self):
        """Test log truncation when content exceeds limits."""
        # Create content larger than default max size
        large_content = "x" * 60000
        result = truncate_logs(large_content, max_size=1000)

        assert len(result) < len(large_content)
        assert "[TRUNCATED:" in result
        assert "characters removed" in result

    def test_get_stage_description(self):
        """Test stage description retrieval."""
        # Test known stage
        desc = get_stage_description("Source")
        assert "Retrieves LZA source code" in desc

        # Test unknown stage
        desc = get_stage_description("UnknownStage")
        assert "Stage: UnknownStage" in desc

    def test_get_action_description(self):
        """Test action description retrieval."""
        # Test known action
        desc = get_action_description("Network_Prepare")
        assert "Transit Gateway" in desc

        # Test unknown action
        desc = get_action_description("UnknownAction")
        assert "Action: UnknownAction" in desc


class TestErrorSummaryGeneration:
    """Test error summary generation functionality."""

    def test_extract_create_failed_error_found(self):
        """Test extracting CREATE_FAILED error when present in logs."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing CloudFormation stack
        AWSAccelerator-OrganizationsStack-222634393892-eu-north-1 | 0/8 | 10:26:03 AM | CREATE_FAILED | Custom::CreatePolicy | AWSAccelerator-BackupPolicy/Resource/Default
        [2024-01-15 10:31:00] Deployment failed
        """

        error = extract_create_failed_error(logs_content)

        assert error is not None
        assert "CREATE_FAILED" in error
        assert "AWSAccelerator-OrganizationsStack" in error
        assert "Custom::CreatePolicy" in error

    def test_extract_create_failed_error_not_found(self):
        """Test extracting CREATE_FAILED error when not present in logs."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        [2024-01-15 10:31:00] Some other error occurred
        [2024-01-15 10:31:30] Deployment failed
        """

        error = extract_create_failed_error(logs_content)

        assert error is None

    def test_extract_create_failed_error_empty_logs(self):
        """Test extracting CREATE_FAILED error from empty logs."""
        error = extract_create_failed_error("")
        assert error is None

        error = extract_create_failed_error(None)
        assert error is None

    def test_extract_error_line_found(self):
        """Test extracting | error | pattern when present in logs."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        2024-01-15T10:31:00.000Z | error | Failed to validate account configuration
        [2024-01-15 10:31:30] Deployment failed
        """

        error = extract_error_line(logs_content)

        assert error is not None
        assert "| error |" in error
        assert "Failed to validate account configuration" in error

    def test_extract_error_line_not_found(self):
        """Test extracting | error | pattern when not present in logs."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        [2024-01-15 10:31:00] Some other issue occurred
        [2024-01-15 10:31:30] Deployment failed
        """

        error = extract_error_line(logs_content)

        assert error is None

    def test_extract_error_line_empty_logs(self):
        """Test extracting | error | pattern from empty logs."""
        error = extract_error_line("")
        assert error is None

        error = extract_error_line(None)
        assert error is None

    def test_extract_error_line_multiple_errors_returns_first(self):
        """Test that extract_error_line returns the first | error | pattern found."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        2024-01-15T10:30:30.000Z | error | First error message
        [2024-01-15 10:31:00] Continuing processing
        2024-01-15T10:31:30.000Z | error | Second error message
        [2024-01-15 10:32:00] Deployment failed
        """

        error = extract_error_line(logs_content)

        assert error is not None
        assert "First error message" in error
        assert "Second error message" not in error

    def test_error_detection_fallback_logic(self):
        """Test the fallback logic: CloudFormation first, then | error | pattern."""
        # Test case 1: CloudFormation error present - should return CloudFormation error
        logs_with_cf_error = """
        [2024-01-15 10:30:00] Starting deployment
        2024-01-15T10:30:30.000Z | error | Some general error
        AWSAccelerator-Stack | CREATE_FAILED | Resource creation failed
        [2024-01-15 10:31:00] Deployment failed
        """

        cf_error = extract_create_failed_error(logs_with_cf_error)
        general_error = extract_error_line(logs_with_cf_error)

        assert cf_error is not None
        assert "CREATE_FAILED" in cf_error
        assert general_error is not None
        assert "| error |" in general_error

        # Test case 2: No CloudFormation error, but | error | pattern present
        logs_with_general_error = """
        [2024-01-15 10:30:00] Starting deployment
        2024-01-15T10:30:30.000Z | error | Configuration validation failed
        [2024-01-15 10:31:00] Deployment failed
        """

        cf_error = extract_create_failed_error(logs_with_general_error)
        general_error = extract_error_line(logs_with_general_error)

        assert cf_error is None
        assert general_error is not None
        assert "Configuration validation failed" in general_error

        # Test case 3: Neither error pattern present
        logs_without_specific_errors = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Some processing step
        [2024-01-15 10:31:00] Deployment failed
        """

        cf_error = extract_create_failed_error(logs_without_specific_errors)
        general_error = extract_error_line(logs_without_specific_errors)

        assert cf_error is None
        assert general_error is None
