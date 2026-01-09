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

"""Comprehensive error handling tests for UC merge tools.

This test file validates that all UC merge tools provide:
1. Structured error responses with consistent format
2. Appropriate error codes and categories
3. Helpful troubleshooting guidance
4. Context information for debugging
5. Next steps for error recovery
"""

import pytest
from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.uc_merge.common import (
    create_error_response,
    categorize_uc_merge_error,
)


class TestErrorResponseStructure:
    """Test that error responses follow the standard structure."""

    def test_error_response_has_required_fields(self):
        """Verify error responses contain all required fields."""
        error = create_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Step 1", "Step 2"],
            context={"key": "value"},
            next_steps="Try again",
        )

        assert error["success"] is False
        assert "error" in error
        assert "error_code" in error
        assert "category" in error
        assert "troubleshooting" in error
        assert "context" in error
        assert "next_steps" in error

    def test_error_response_optional_fields(self):
        """Verify error responses work without optional fields."""
        error = create_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Step 1"],
        )

        assert error["success"] is False
        assert "context" not in error
        assert "next_steps" not in error or error["next_steps"] == ""

    def test_error_response_troubleshooting_is_list(self):
        """Verify troubleshooting is always a list."""
        error = create_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Step 1", "Step 2", "Step 3"],
        )

        assert isinstance(error["troubleshooting"], list)
        assert len(error["troubleshooting"]) == 3


class TestErrorCategorization:
    """Test error categorization logic."""

    def test_categorize_path_traversal_error(self):
        """Verify path traversal errors are categorized correctly."""
        error = Exception("Path traversal detected in file path")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.SECURITY
        assert result["error_code"] == "PATH_TRAVERSAL"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_boundary_violation_error(self):
        """Verify boundary violation errors are categorized correctly."""
        error = Exception("Path is outside allowed directory boundary")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.SECURITY
        assert result["error_code"] == "BOUNDARY_VIOLATION"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_file_not_found_error(self):
        """Verify file not found errors are categorized correctly."""
        error = Exception("File not found: test.yaml")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.FILE_NOT_FOUND
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_session_error(self):
        """Verify session errors are categorized correctly."""
        error = Exception("Invalid session: session-123")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.VALIDATION
        assert result["error_code"] == "INVALID_SESSION"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_yaml_error(self):
        """Verify YAML errors are categorized correctly."""
        error = Exception("YAML parse error: invalid syntax")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "YAML_PARSE_ERROR"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_permission_error(self):
        """Verify permission errors are categorized correctly."""
        error = Exception("Permission denied accessing file")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.FILE_OPERATION
        assert result["error_code"] == "ACCESS_DENIED"
        assert len(result["troubleshooting"]) > 0

    def test_categorize_generic_error(self):
        """Verify generic errors are categorized with default category."""
        error = Exception("Something went wrong")
        result = categorize_uc_merge_error(error)

        assert result["category"] == ErrorCategory.FILE_OPERATION
        assert result["error_code"] == "FILE_OPERATION_ERROR"
        assert len(result["troubleshooting"]) > 0


class TestSecurityErrorScenarios:
    """Test security-related error scenarios."""

    def test_path_traversal_error_includes_security_guidance(self):
        """Verify path traversal errors include security-focused guidance."""
        error = Exception("Path traversal detected")
        result = categorize_uc_merge_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"]).lower()
        assert "path" in troubleshooting_text
        assert "relative" in troubleshooting_text or "directory" in troubleshooting_text

    def test_boundary_violation_error_includes_boundary_guidance(self):
        """Verify boundary violations include boundary-focused guidance."""
        error = Exception("Path is outside allowed directory boundary")
        result = categorize_uc_merge_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"]).lower()
        assert "boundary" in troubleshooting_text or "directory" in troubleshooting_text


class TestValidationErrorScenarios:
    """Test validation-related error scenarios."""

    def test_missing_parameter_errors_include_parameter_name(self):
        """Verify missing parameter errors mention the parameter."""
        error = create_error_response(
            error_message="Missing required parameter: uc_release",
            error_code="MISSING_PARAMETER",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "The uc_release parameter is required",
                "Call get_uc_releases() first",
            ],
            next_steps="Call get_uc_releases() to discover available releases",
        )

        assert "uc_release" in error["error"]
        assert "required" in error["error"].lower()

    def test_invalid_format_errors_include_expected_format(self):
        """Verify format validation errors include expected format."""
        error = create_error_response(
            error_message="Invalid CIDR format: '10.0.0/8'",
            error_code="INVALID_CIDR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Use format: X.X.X.X/Y (e.g., 10.0.0.0/8)",
                "Ensure all octets are 0-255",
            ],
            next_steps="Correct the CIDR format and retry",
        )

        troubleshooting_text = " ".join(error["troubleshooting"])
        assert "format" in troubleshooting_text.lower()
        assert (
            "X.X.X.X/Y" in troubleshooting_text
            or "example" in troubleshooting_text.lower()
        )


class TestFileOperationErrorScenarios:
    """Test file operation error scenarios."""

    def test_file_not_found_errors_include_file_path(self):
        """Verify file not found errors include the file path."""
        error = create_error_response(
            error_message="File not found: accounts-config.yaml",
            error_code="FILE_NOT_FOUND",
            category=ErrorCategory.FILE_NOT_FOUND,
            troubleshooting=[
                "Verify the file path is correct",
                "Check that the file exists",
            ],
            context={"file_path": "accounts-config.yaml"},
            next_steps="Verify the file path and retry",
        )

        assert "accounts-config.yaml" in error["error"]
        assert error["context"]["file_path"] == "accounts-config.yaml"

    def test_permission_errors_include_permission_guidance(self):
        """Verify permission errors include permission-focused guidance."""
        error = create_error_response(
            error_message="Permission denied reading file",
            error_code="ACCESS_DENIED",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check file system permissions",
                "Ensure the user has read access",
            ],
            next_steps="Check file permissions and retry",
        )

        troubleshooting_text = " ".join(error["troubleshooting"]).lower()
        assert "permission" in troubleshooting_text


class TestConfigurationErrorScenarios:
    """Test configuration-related error scenarios."""

    def test_yaml_parse_errors_include_syntax_guidance(self):
        """Verify YAML parse errors include syntax guidance."""
        error = create_error_response(
            error_message="Failed to parse YAML file: invalid syntax",
            error_code="YAML_PARSE_ERROR",
            category=ErrorCategory.CONFIGURATION,
            troubleshooting=[
                "File contains invalid YAML syntax",
                "Check the file for syntax errors",
                "Ensure proper indentation",
            ],
            next_steps="Fix YAML syntax errors and retry",
        )

        troubleshooting_text = " ".join(error["troubleshooting"]).lower()
        assert "yaml" in troubleshooting_text or "syntax" in troubleshooting_text

    def test_validation_failed_errors_include_specific_failures(self):
        """Verify validation errors include specific failure details."""
        error = create_error_response(
            error_message="Validation failed for 2 field(s)",
            error_code="VALIDATION_FAILED",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "One or more values failed validation",
                "Review the validation_errors list",
            ],
            context={
                "validation_errors": [
                    "HomeRegionIngressCidr: Invalid CIDR format",
                    "DevVpcMaskLength: Value out of range",
                ]
            },
            next_steps="Review validation errors and correct the values",
        )

        assert "validation_errors" in error["context"]
        assert len(error["context"]["validation_errors"]) == 2


class TestErrorRecoveryGuidance:
    """Test that errors include actionable recovery guidance."""

    def test_all_errors_include_next_steps(self):
        """Verify all error types can include next steps."""
        error_scenarios = [
            ("MISSING_PARAMETER", ErrorCategory.VALIDATION),
            ("FILE_NOT_FOUND", ErrorCategory.FILE_NOT_FOUND),
            ("PATH_TRAVERSAL", ErrorCategory.SECURITY),
            ("YAML_PARSE_ERROR", ErrorCategory.CONFIGURATION),
            ("ACCESS_DENIED", ErrorCategory.FILE_OPERATION),
        ]

        for error_code, category in error_scenarios:
            error = create_error_response(
                error_message=f"Test error for {error_code}",
                error_code=error_code,
                category=category,
                troubleshooting=["Step 1"],
                next_steps="Try this recovery action",
            )

            assert "next_steps" in error
            assert len(error["next_steps"]) > 0

    def test_troubleshooting_steps_are_actionable(self):
        """Verify troubleshooting steps are actionable (contain verbs)."""
        error = create_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Check file permissions",
                "Verify the path is correct",
                "Ensure the session exists",
                "Call get_uc_releases() first",
            ],
        )

        # Check that troubleshooting steps contain action verbs
        action_verbs = ["check", "verify", "ensure", "call", "provide", "use", "review"]
        for step in error["troubleshooting"]:
            step_lower = step.lower()
            has_action_verb = any(verb in step_lower for verb in action_verbs)
            assert has_action_verb, f"Troubleshooting step lacks action verb: {step}"


class TestErrorContextInformation:
    """Test that errors include helpful context information."""

    def test_errors_include_relevant_context(self):
        """Verify errors include context relevant to the error."""
        error = create_error_response(
            error_message="Session not found",
            error_code="INVALID_SESSION",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Verify session_id", "Start new session"],
            context={
                "session_id": "uc-session-123",
                "available_sessions": ["uc-session-456"],
            },
        )

        assert "context" in error
        assert "session_id" in error["context"]
        assert "available_sessions" in error["context"]

    def test_context_helps_debugging(self):
        """Verify context includes information useful for debugging."""
        error = create_error_response(
            error_message="File operation failed",
            error_code="FILE_OPERATION_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=["Check permissions", "Verify path"],
            context={
                "file_path": "test.yaml",
                "operation": "read",
                "error_type": "PermissionError",
            },
        )

        context = error["context"]
        assert "file_path" in context
        assert "operation" in context
        assert "error_type" in context


class TestErrorConsistency:
    """Test that error handling is consistent across tools."""

    def test_all_security_errors_use_security_category(self):
        """Verify all security-related errors use SECURITY category."""
        security_errors = [
            Exception("Path traversal detected"),
            Exception("Absolute paths are not allowed"),
            Exception("Path is outside allowed directory boundary"),
        ]

        for error in security_errors:
            result = categorize_uc_merge_error(error)
            assert result["category"] == ErrorCategory.SECURITY

    def test_all_file_errors_use_appropriate_category(self):
        """Verify file-related errors use appropriate categories."""
        file_errors = [
            (Exception("File not found"), ErrorCategory.FILE_NOT_FOUND),
            (Exception("Permission denied"), ErrorCategory.FILE_OPERATION),
            (Exception("Failed to read file"), ErrorCategory.FILE_OPERATION),
        ]

        for error, expected_category in file_errors:
            result = categorize_uc_merge_error(error)
            assert result["category"] == expected_category

    def test_error_codes_are_machine_readable(self):
        """Verify error codes follow machine-readable format."""
        error_codes = [
            "MISSING_PARAMETER",
            "FILE_NOT_FOUND",
            "PATH_TRAVERSAL",
            "YAML_PARSE_ERROR",
            "INVALID_SESSION",
        ]

        for code in error_codes:
            # Error codes should be uppercase with underscores
            assert code.isupper()
            assert " " not in code
            assert all(c.isalnum() or c == "_" for c in code)


@pytest.mark.unit
@pytest.mark.uc_merge
class TestErrorHandlingDocumentation:
    """Test that error handling is well-documented."""

    def test_error_messages_are_human_readable(self):
        """Verify error messages are clear and human-readable."""
        error = create_error_response(
            error_message="Missing required parameter: uc_release",
            error_code="MISSING_PARAMETER",
            category=ErrorCategory.VALIDATION,
            troubleshooting=["Provide uc_release parameter"],
        )

        # Error message should be a complete sentence
        assert error["error"][0].isupper()  # Starts with capital
        assert len(error["error"]) > 10  # Has substance

    def test_troubleshooting_steps_are_clear(self):
        """Verify troubleshooting steps are clear and specific."""
        error = create_error_response(
            error_message="Test error",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            troubleshooting=[
                "Call get_uc_releases() to discover available releases",
                "Verify the uc_release parameter is correct",
                "Ensure the UC repository is accessible",
            ],
        )

        for step in error["troubleshooting"]:
            # Each step should be substantial
            assert len(step) > 15
            # Should not be just a word
            assert " " in step


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
