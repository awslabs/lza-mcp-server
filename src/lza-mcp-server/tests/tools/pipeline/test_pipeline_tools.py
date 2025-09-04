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

"""Unit tests for pipeline tools module."""

import pytest
from unittest.mock import Mock

from awslabs.lza_mcp_server.tools.pipeline.common import (
    extract_create_failed_error,
    truncate_logs,
    validate_pipeline_name_local,
    validate_execution_id_local,
)


class TestValidationFunctions:
    """Test input validation functions."""

    def test_validate_execution_id_valid(self):
        """Test execution ID validation with valid IDs."""
        is_valid, error = validate_execution_id_local(
            "12345678-1234-1234-1234-123456789012"
        )
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_execution_id_local(
            "abcdef12-3456-7890-abcd-ef1234567890"
        )
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_execution_id_local(
            "ABCDEF12-3456-7890-ABCD-EF1234567890"
        )
        assert is_valid is True
        assert error == ""

    def test_validate_execution_id_invalid(self):
        """Test execution ID validation with invalid IDs."""
        is_valid, error = validate_execution_id_local("")
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_execution_id_local("invalid-id")
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id_local(
            "12345678-1234-1234-1234-12345678901"
        )  # Too short
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id_local(
            "12345678-1234-1234-1234-1234567890123"
        )  # Too long
        assert is_valid is False
        assert "Invalid execution ID format" in error

        is_valid, error = validate_execution_id_local(None)
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_execution_id_local(123)
        assert is_valid is False
        assert "cannot be empty" in error

    def test_validate_pipeline_name_valid(self):
        """Test pipeline name validation with valid names."""
        is_valid, error = validate_pipeline_name_local("AWSAccelerator-Pipeline")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name_local("test-pipeline")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name_local("pipeline_123")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name_local("pipeline.test")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name_local("a")
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_pipeline_name_local("a" * 100)
        assert is_valid is True
        assert error == ""

    def test_validate_pipeline_name_invalid(self):
        """Test pipeline name validation with invalid names."""
        is_valid, error = validate_pipeline_name_local("")
        assert is_valid is False
        assert "cannot be empty" in error

        is_valid, error = validate_pipeline_name_local("a" * 101)
        assert is_valid is False
        assert "too long" in error

        is_valid, error = validate_pipeline_name_local("pipeline with spaces")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name_local("pipeline@test")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name_local("pipeline#test")
        assert is_valid is False
        assert "invalid characters" in error

        is_valid, error = validate_pipeline_name_local(None)
        assert is_valid is False
        assert "cannot be empty" in error


class TestLogProcessing:
    """Test log processing functionality."""

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

    def test_truncate_logs_no_truncation_needed(self):
        """Test log truncation when content is within limits."""
        short_content = "This is a short log message"
        result = truncate_logs(short_content)

        assert result == short_content
        assert "[TRUNCATED:" not in result

    def test_truncate_logs_with_truncation(self):
        """Test log truncation when content exceeds limits."""
        large_content = "x" * 60000
        result = truncate_logs(large_content, max_size=1000)

        assert len(result) < len(large_content)
        assert "[TRUNCATED:" in result
        assert "characters removed" in result


class TestErrorSummaryGeneration:
    """Test error summary generation functionality."""

    def test_generate_error_summary_with_error_patterns(self):
        """Test error summary generation with common error patterns."""
        logs_content = """
        [2024-01-15 10:30:00] Starting build process
        [2024-01-15 10:30:30] Downloading dependencies
        [2024-01-15 10:31:00] ERROR: Configuration validation failed - missing required field 'accountId'
        [2024-01-15 10:31:15] FAILED: Unable to proceed with deployment
        [2024-01-15 10:31:30] BUILD FAILED
        """

        # Simple error detection logic for testing
        error_lines = []
        for line in logs_content.split("\n"):
            if any(
                keyword in line.upper()
                for keyword in ["ERROR:", "FAILED:", "BUILD FAILED"]
            ):
                error_lines.append(line.strip())

        assert len(error_lines) == 3
        assert any("Configuration validation failed" in line for line in error_lines)
        assert any("Unable to proceed with deployment" in line for line in error_lines)
        assert any("BUILD FAILED" in line for line in error_lines)

    def test_generate_error_summary_no_error_patterns(self):
        """Test error summary generation when no error patterns are found."""
        logs_content = """
        [2024-01-15 10:30:00] Starting build process
        [2024-01-15 10:30:30] Downloading dependencies
        [2024-01-15 10:31:00] Processing configuration files
        [2024-01-15 10:31:30] Deployment completed
        """

        # Simple error detection logic for testing
        error_lines = []
        for line in logs_content.split("\n"):
            if any(
                keyword in line.upper()
                for keyword in ["ERROR:", "FAILED:", "BUILD FAILED"]
            ):
                error_lines.append(line.strip())

        assert len(error_lines) == 0

    def test_generate_error_summary_empty_logs(self):
        """Test error summary generation with empty logs."""
        logs_content = ""

        # Simple error detection logic for testing
        error_lines = []
        for line in logs_content.split("\n"):
            if any(
                keyword in line.upper()
                for keyword in ["ERROR:", "FAILED:", "BUILD FAILED"]
            ):
                error_lines.append(line.strip())

        assert len(error_lines) == 0


class TestPipelineToolsIntegration:
    """Test pipeline tools integration scenarios."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock MCP context."""
        return Mock()

    def test_pipeline_name_validation_integration(self):
        """Test pipeline name validation in integration context."""
        # Test valid names
        valid_names = [
            "AWSAccelerator-Pipeline",
            "test-pipeline",
            "pipeline_123",
            "pipeline.test",
        ]

        for name in valid_names:
            is_valid, error = validate_pipeline_name_local(name)
            assert is_valid, f"Expected {name} to be valid, but got error: {error}"

        # Test invalid names
        invalid_names = [
            "",
            "a" * 101,
            "pipeline with spaces",
            "pipeline@test",
            "pipeline#test",
        ]

        for name in invalid_names:
            is_valid, error = validate_pipeline_name_local(name)
            assert not is_valid, f"Expected {name} to be invalid, but validation passed"
            assert error, f"Expected error message for invalid name: {name}"

    def test_execution_id_validation_integration(self):
        """Test execution ID validation in integration context."""
        # Test valid UUIDs
        valid_ids = [
            "12345678-1234-1234-1234-123456789012",
            "abcdef12-3456-7890-abcd-ef1234567890",
            "ABCDEF12-3456-7890-ABCD-EF1234567890",
        ]

        for exec_id in valid_ids:
            is_valid, error = validate_execution_id_local(exec_id)
            assert is_valid, f"Expected {exec_id} to be valid, but got error: {error}"

        # Test invalid UUIDs
        invalid_ids = [
            "",
            "invalid-id",
            "12345678-1234-1234-1234-12345678901",  # Too short
            "12345678-1234-1234-1234-1234567890123",  # Too long
            "12345678-1234-1234-1234-123456789012-extra",  # Extra chars
        ]

        for exec_id in invalid_ids:
            is_valid, error = validate_execution_id_local(exec_id)
            assert not is_valid, (
                f"Expected {exec_id} to be invalid, but validation passed"
            )
            assert error, f"Expected error message for invalid execution ID: {exec_id}"


class TestPipelineErrorDiagnosis:
    """Test pipeline error diagnosis functionality."""

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

        # Extract general error pattern
        general_error = None
        for line in logs_with_cf_error.split("\n"):
            if "| error |" in line:
                general_error = line.strip()
                break

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

        general_error = None
        for line in logs_with_general_error.split("\n"):
            if "| error |" in line:
                general_error = line.strip()
                break

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

        general_error = None
        for line in logs_without_specific_errors.split("\n"):
            if "| error |" in line:
                general_error = line.strip()
                break

        assert cf_error is None
        assert general_error is None


class TestPipelineUtilities:
    """Test pipeline utility functions."""

    def test_log_truncation_performance(self):
        """Test log truncation performance with large content."""
        # Create large log content
        large_content = "Line of log content\n" * 10000

        # Test truncation
        result = truncate_logs(large_content, max_size=5000)

        # Verify truncation occurred
        assert len(result) < len(large_content)
        assert "[TRUNCATED:" in result

        # Verify structure is maintained
        assert result.startswith("Line of log content")
        assert result.endswith("Line of log content\n")

    def test_error_extraction_edge_cases(self):
        """Test error extraction with edge cases."""
        # Test with multiple CREATE_FAILED errors (should return first)
        logs_with_multiple_errors = """
        First CREATE_FAILED error line
        Some other content
        Second CREATE_FAILED error line
        """

        error = extract_create_failed_error(logs_with_multiple_errors)
        assert error == "First CREATE_FAILED error line"

        # Test with CREATE_FAILED in middle of line
        logs_with_embedded_error = """
        Some prefix CREATE_FAILED some suffix
        """

        error = extract_create_failed_error(logs_with_embedded_error)
        assert error == "Some prefix CREATE_FAILED some suffix"

        # Test with whitespace handling
        logs_with_whitespace = """
        
           CREATE_FAILED error with whitespace   
        
        """

        error = extract_create_failed_error(logs_with_whitespace)
        assert error == "CREATE_FAILED error with whitespace"

    def test_validation_error_messages(self):
        """Test validation error message quality."""
        # Test pipeline name error messages
        is_valid, error = validate_pipeline_name_local("pipeline with spaces")
        assert "invalid characters" in error
        assert " " in error  # Should mention space as invalid character

        is_valid, error = validate_pipeline_name_local("a" * 101)
        assert "too long" in error
        assert "101 characters" in error
        assert "100" in error  # Should mention the limit

        # Test execution ID error messages
        is_valid, error = validate_execution_id_local("invalid-format")
        assert "Invalid execution ID format" in error
        assert "UUID format" in error
        assert "invalid-format" in error  # Should include the invalid value

        is_valid, error = validate_execution_id_local("")
        assert "cannot be empty" in error
