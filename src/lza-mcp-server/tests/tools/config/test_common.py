# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for config/common.py error categorization."""

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from awslabs.lza_mcp_server.tools.config.common import categorize_configuration_error


class TestCategorizeConfigurationError:
    """Test configuration error categorization."""

    def test_not_found_error(self):
        """Test categorization of 'not found' errors."""
        error = Exception("Configuration file not found")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_NOT_FOUND"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0
        assert any("not found" in step.lower() for step in result["troubleshooting"])

    def test_does_not_exist_error(self):
        """Test categorization of 'does not exist' errors."""
        error = Exception("Directory does not exist")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_NOT_FOUND"
        assert "troubleshooting" in result
        assert any("accounts-config.yaml" in step for step in result["troubleshooting"])

    def test_permission_error(self):
        """Test categorization of permission errors."""
        error = Exception("Permission denied accessing configuration")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_ACCESS_DENIED"
        assert "troubleshooting" in result
        assert any("permission" in step.lower() for step in result["troubleshooting"])

    def test_access_error(self):
        """Test categorization of access errors."""
        error = Exception("Access denied to configuration files")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_ACCESS_DENIED"
        assert "troubleshooting" in result
        assert any("read access" in step.lower() for step in result["troubleshooting"])

    def test_yaml_error(self):
        """Test categorization of YAML parsing errors."""
        error = Exception("YAML parsing failed")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_PARSE_ERROR"
        assert "troubleshooting" in result
        assert any("yaml" in step.lower() for step in result["troubleshooting"])

    def test_parse_error(self):
        """Test categorization of generic parse errors."""
        error = Exception("Failed to parse configuration file")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_PARSE_ERROR"
        assert "troubleshooting" in result
        assert any("syntax" in step.lower() for step in result["troubleshooting"])

    def test_syntax_error(self):
        """Test categorization of syntax errors."""
        error = Exception("Syntax error in configuration")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_PARSE_ERROR"
        assert "troubleshooting" in result
        assert any("indentation" in step.lower() for step in result["troubleshooting"])

    def test_zip_error(self):
        """Test categorization of ZIP creation errors."""
        error = Exception("Failed to create ZIP archive")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "ZIP_CREATION_ERROR"
        assert "troubleshooting" in result
        assert any("zip" in step.lower() for step in result["troubleshooting"])

    def test_archive_error(self):
        """Test categorization of archive errors."""
        error = Exception("Archive creation failed")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "ZIP_CREATION_ERROR"
        assert "troubleshooting" in result
        assert any("disk space" in step.lower() for step in result["troubleshooting"])

    def test_generic_validation_error(self):
        """Test categorization of generic validation errors."""
        error = Exception("Configuration validation failed")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_VALIDATION_ERROR"
        assert "troubleshooting" in result
        assert any("validation" in step.lower() for step in result["troubleshooting"])

    def test_unknown_error(self):
        """Test categorization of unknown errors defaults to validation error."""
        error = Exception("Something unexpected happened")
        result = categorize_configuration_error(error)

        assert result["category"] == ErrorCategory.CONFIGURATION
        assert result["error_code"] == "CONFIG_VALIDATION_ERROR"
        assert "troubleshooting" in result
        assert len(result["troubleshooting"]) > 0

    def test_case_insensitive_matching(self):
        """Test that error matching is case-insensitive."""
        # Test uppercase
        error_upper = Exception("FILE NOT FOUND")
        result_upper = categorize_configuration_error(error_upper)
        assert result_upper["error_code"] == "CONFIG_NOT_FOUND"

        # Test mixed case
        error_mixed = Exception("Permission Denied")
        result_mixed = categorize_configuration_error(error_mixed)
        assert result_mixed["error_code"] == "CONFIG_ACCESS_DENIED"

        # Test lowercase
        error_lower = Exception("yaml error")
        result_lower = categorize_configuration_error(error_lower)
        assert result_lower["error_code"] == "CONFIG_PARSE_ERROR"

    def test_multiple_keywords_first_match_wins(self):
        """Test that first matching condition takes precedence."""
        # "not found" should match before generic validation
        error = Exception("Configuration not found and validation failed")
        result = categorize_configuration_error(error)
        assert result["error_code"] == "CONFIG_NOT_FOUND"

    def test_all_results_have_required_fields(self):
        """Test that all error categorizations include required fields."""
        test_errors = [
            Exception("not found"),
            Exception("permission denied"),
            Exception("yaml error"),
            Exception("zip failed"),
            Exception("unknown error"),
        ]

        for error in test_errors:
            result = categorize_configuration_error(error)
            assert "category" in result
            assert "error_code" in result
            assert "troubleshooting" in result
            assert isinstance(result["troubleshooting"], list)
            assert len(result["troubleshooting"]) > 0
            assert result["category"] == ErrorCategory.CONFIGURATION

    def test_troubleshooting_steps_are_actionable(self):
        """Test that troubleshooting steps provide actionable guidance."""
        error = Exception("Configuration not found")
        result = categorize_configuration_error(error)

        # Check that troubleshooting steps are non-empty strings
        for step in result["troubleshooting"]:
            assert isinstance(step, str)
            assert len(step) > 0
            # Steps may have intentional leading whitespace for formatting (e.g., "  - item")
            assert len(step.strip()) > 0

    def test_specific_file_mentions_in_not_found(self):
        """Test that NOT_FOUND errors mention specific required files."""
        error = Exception("Configuration directory not found")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert "accounts-config.yaml" in troubleshooting_text
        assert "organization-config.yaml" in troubleshooting_text

    def test_yaml_validator_mention_in_parse_error(self):
        """Test that PARSE_ERROR mentions YAML validator."""
        error = Exception("YAML syntax error")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert "validator" in troubleshooting_text.lower()
        assert "schema" in troubleshooting_text.lower()

    def test_disk_space_mention_in_zip_error(self):
        """Test that ZIP_ERROR mentions disk space."""
        error = Exception("Failed to create zip archive")
        result = categorize_configuration_error(error)

        troubleshooting_text = " ".join(result["troubleshooting"])
        assert "disk space" in troubleshooting_text.lower()
        assert "zip" in troubleshooting_text.lower()
