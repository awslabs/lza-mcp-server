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

"""Unit tests for pipeline validation utilities."""

from awslabs.lza_mcp_server.tools.pipeline.validation import (
    validate_pipeline_name,
    validate_execution_id,
    validate_aws_region,
)


class TestValidatePipelineName:
    """Test pipeline name validation."""

    def test_valid_pipeline_names(self):
        """Test validation with valid pipeline names."""
        valid_names = [
            "AWSAccelerator-Pipeline",
            "test-pipeline",
            "pipeline_123",
            "pipeline.test",
            "My-Pipeline_123.test",
            "a",  # Minimum length
            "a" * 100,  # Maximum length
        ]

        for name in valid_names:
            is_valid, error = validate_pipeline_name(name)
            assert is_valid, f"Expected '{name}' to be valid, but got error: {error}"
            assert error == "", f"Expected no error for '{name}', but got: {error}"

    def test_empty_pipeline_name(self):
        """Test validation with empty pipeline name."""
        is_valid, error = validate_pipeline_name("")
        assert not is_valid
        assert "cannot be empty" in error

    def test_none_pipeline_name(self):
        """Test validation with None pipeline name."""
        is_valid, error = validate_pipeline_name(None)
        assert not is_valid
        assert "cannot be empty" in error

    def test_non_string_pipeline_name(self):
        """Test validation with non-string pipeline name."""
        is_valid, error = validate_pipeline_name(123)
        assert not is_valid
        assert "must be a string" in error

        is_valid, error = validate_pipeline_name(["pipeline"])
        assert not is_valid
        assert "must be a string" in error

    def test_pipeline_name_too_long(self):
        """Test validation with pipeline name exceeding maximum length."""
        long_name = "a" * 101
        is_valid, error = validate_pipeline_name(long_name)
        assert not is_valid
        assert "too long" in error
        assert "101 characters" in error
        assert "100 characters" in error

    def test_pipeline_name_with_spaces(self):
        """Test validation with pipeline name containing spaces."""
        is_valid, error = validate_pipeline_name("pipeline with spaces")
        assert not is_valid
        assert "invalid characters" in error
        assert " " in error

    def test_pipeline_name_with_special_characters(self):
        """Test validation with pipeline name containing special characters."""
        invalid_names = [
            "pipeline@test",
            "pipeline#test",
            "pipeline$test",
            "pipeline%test",
            "pipeline&test",
            "pipeline*test",
            "pipeline+test",
            "pipeline=test",
            "pipeline[test]",
            "pipeline{test}",
            "pipeline|test",
            "pipeline\\test",
            "pipeline/test",
            "pipeline:test",
            "pipeline;test",
            "pipeline'test",
            'pipeline"test',
            "pipeline<test>",
            "pipeline?test",
            "pipeline!test",
            "pipeline~test",
            "pipeline`test",
        ]

        for name in invalid_names:
            is_valid, error = validate_pipeline_name(name)
            assert not is_valid, f"Expected '{name}' to be invalid"
            assert "invalid characters" in error
            # Extract the special character from the name
            special_char = next(
                c
                for c in name
                if c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            )
            assert special_char in error, (
                f"Expected error to mention '{special_char}' for '{name}'"
            )

    def test_pipeline_name_with_unicode(self):
        """Test validation with pipeline name containing unicode characters."""
        is_valid, error = validate_pipeline_name("pipeline-\u00e9")
        assert not is_valid
        assert "invalid characters" in error

    def test_pipeline_name_with_newline(self):
        """Test validation with pipeline name containing newline."""
        is_valid, error = validate_pipeline_name("pipeline\ntest")
        assert not is_valid
        assert "invalid characters" in error

    def test_pipeline_name_with_tab(self):
        """Test validation with pipeline name containing tab."""
        is_valid, error = validate_pipeline_name("pipeline\ttest")
        assert not is_valid
        assert "invalid characters" in error

    def test_pipeline_name_error_message_quality(self):
        """Test that error messages are clear and actionable."""
        # Test empty name
        is_valid, error = validate_pipeline_name("")
        assert "cannot be empty" in error

        # Test too long
        is_valid, error = validate_pipeline_name("a" * 101)
        assert "too long" in error
        assert "101" in error
        assert "100" in error

        # Test invalid characters
        is_valid, error = validate_pipeline_name("test@pipeline")
        assert "invalid characters" in error
        assert "@" in error
        assert "letters, numbers, periods, underscores, and hyphens" in error


class TestValidateExecutionId:
    """Test execution ID validation."""

    def test_valid_execution_ids(self):
        """Test validation with valid execution IDs."""
        valid_ids = [
            "12345678-1234-1234-1234-123456789012",
            "abcdef12-3456-7890-abcd-ef1234567890",
            "ABCDEF12-3456-7890-ABCD-EF1234567890",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
        ]

        for exec_id in valid_ids:
            is_valid, error = validate_execution_id(exec_id)
            assert is_valid, f"Expected '{exec_id}' to be valid, but got error: {error}"
            assert error == "", f"Expected no error for '{exec_id}', but got: {error}"

    def test_empty_execution_id(self):
        """Test validation with empty execution ID."""
        is_valid, error = validate_execution_id("")
        assert not is_valid
        assert "cannot be empty" in error

    def test_none_execution_id(self):
        """Test validation with None execution ID."""
        is_valid, error = validate_execution_id(None)
        assert not is_valid
        assert "cannot be empty" in error

    def test_non_string_execution_id(self):
        """Test validation with non-string execution ID."""
        is_valid, error = validate_execution_id(123)
        assert not is_valid
        assert "must be a string" in error

        is_valid, error = validate_execution_id(
            ["12345678-1234-1234-1234-123456789012"]
        )
        assert not is_valid
        assert "must be a string" in error

    def test_invalid_execution_id_format(self):
        """Test validation with invalid execution ID formats."""
        invalid_ids = [
            "invalid-id",
            "12345678-1234-1234-1234",  # Too short
            "12345678-1234-1234-1234-12345678901",  # Last segment too short
            "12345678-1234-1234-1234-1234567890123",  # Last segment too long
            "12345678-1234-1234-1234-123456789012-extra",  # Extra segment
            "1234567-1234-1234-1234-123456789012",  # First segment too short
            "123456789-1234-1234-1234-123456789012",  # First segment too long
            "12345678-123-1234-1234-123456789012",  # Second segment too short
            "12345678-12345-1234-1234-123456789012",  # Second segment too long
            "12345678-1234-123-1234-123456789012",  # Third segment too short
            "12345678-1234-12345-1234-123456789012",  # Third segment too long
            "12345678-1234-1234-123-123456789012",  # Fourth segment too short
            "12345678-1234-1234-12345-123456789012",  # Fourth segment too long
            "12345678_1234_1234_1234_123456789012",  # Wrong separator
            "12345678-1234-1234-1234-12345678901g",  # Invalid character
            "12345678-1234-1234-1234-12345678901 ",  # Trailing space
            " 12345678-1234-1234-1234-123456789012",  # Leading space
        ]

        for exec_id in invalid_ids:
            is_valid, error = validate_execution_id(exec_id)
            assert not is_valid, f"Expected '{exec_id}' to be invalid"
            assert "Invalid execution ID format" in error
            assert "UUID format" in error

    def test_execution_id_missing_hyphens(self):
        """Test validation with execution ID missing hyphens."""
        is_valid, error = validate_execution_id("12345678123412341234123456789012")
        assert not is_valid
        assert "Invalid execution ID format" in error
        assert "UUID format" in error

    def test_execution_id_with_special_characters(self):
        """Test validation with execution ID containing special characters."""
        is_valid, error = validate_execution_id("12345678-1234-1234-1234-12345678901@")
        assert not is_valid
        assert "Invalid execution ID format" in error

    def test_execution_id_error_message_quality(self):
        """Test that error messages are clear and actionable."""
        # Test empty ID
        is_valid, error = validate_execution_id("")
        assert "cannot be empty" in error

        # Test invalid format
        is_valid, error = validate_execution_id("invalid-format")
        assert "Invalid execution ID format" in error
        assert "UUID format" in error
        assert "12345678-1234-1234-1234-123456789012" in error


class TestValidateAwsRegion:
    """Test AWS region validation."""

    def test_valid_aws_regions(self):
        """Test validation with valid AWS regions."""
        valid_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "eu-north-1",
            "ap-south-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-northeast-3",
            "ap-southeast-1",
            "ap-southeast-2",
            "ca-central-1",
            "sa-east-1",
            "af-south-1",
            "me-south-1",
            "cn-north-1",
            "cn-northwest-1",
            "us-gov-east-1",
            "us-gov-west-1",
            # European Sovereign Cloud (ESC) regions
            "eusc-de-east-1",
            "eusc-de-west-1",
        ]

        for region in valid_regions:
            is_valid, error = validate_aws_region(region)
            assert is_valid, f"Expected '{region}' to be valid, but got error: {error}"
            assert error == "", f"Expected no error for '{region}', but got: {error}"

    def test_empty_region(self):
        """Test validation with empty region."""
        is_valid, error = validate_aws_region("")
        assert not is_valid
        assert "cannot be empty" in error

    def test_none_region(self):
        """Test validation with None region."""
        is_valid, error = validate_aws_region(None)
        assert not is_valid
        assert "cannot be empty" in error

    def test_non_string_region(self):
        """Test validation with non-string region."""
        is_valid, error = validate_aws_region(123)
        assert not is_valid
        assert "must be a string" in error

        is_valid, error = validate_aws_region(["us-east-1"])
        assert not is_valid
        assert "must be a string" in error

    def test_invalid_region_format(self):
        """Test validation with invalid region formats."""
        invalid_regions = [
            "us-east",  # Missing number
            "useast1",  # Missing hyphens
            "us_east_1",  # Wrong separator
            "US-EAST-1",  # Uppercase
            "us-east-1a",  # Extra character
            "us-east-01",  # Leading zero
            "us-east-1-extra",  # Extra segment
            "east-1",  # Missing region prefix
            "us-1",  # Missing location
            "1-east-1",  # Invalid prefix
            "us-east-",  # Missing number
            "-us-east-1",  # Leading hyphen
            "us-east-1-",  # Trailing hyphen
            "us--east-1",  # Double hyphen
            "us-east-1 ",  # Trailing space
            " us-east-1",  # Leading space
        ]

        for region in invalid_regions:
            is_valid, error = validate_aws_region(region)
            assert not is_valid, f"Expected '{region}' to be invalid"
            assert "Invalid AWS region format" in error

    def test_region_with_special_characters(self):
        """Test validation with region containing special characters."""
        is_valid, error = validate_aws_region("us-east@1")
        assert not is_valid
        assert "Invalid AWS region format" in error

    def test_region_error_message_quality(self):
        """Test that error messages are clear and actionable."""
        # Test empty region
        is_valid, error = validate_aws_region("")
        assert "cannot be empty" in error

        # Test invalid format
        is_valid, error = validate_aws_region("invalid-region")
        assert "Invalid AWS region format" in error
        assert "us-east-1" in error


class TestValidationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_pipeline_name_boundary_lengths(self):
        """Test pipeline name validation at boundary lengths."""
        # Exactly 1 character (minimum)
        is_valid, error = validate_pipeline_name("a")
        assert is_valid

        # Exactly 100 characters (maximum)
        is_valid, error = validate_pipeline_name("a" * 100)
        assert is_valid

        # Exactly 101 characters (over maximum)
        is_valid, error = validate_pipeline_name("a" * 101)
        assert not is_valid

    def test_execution_id_case_insensitivity(self):
        """Test that execution ID validation is case-insensitive."""
        lowercase_id = "abcdef12-3456-7890-abcd-ef1234567890"
        uppercase_id = "ABCDEF12-3456-7890-ABCD-EF1234567890"
        mixed_case_id = "AbCdEf12-3456-7890-AbCd-Ef1234567890"

        for exec_id in [lowercase_id, uppercase_id, mixed_case_id]:
            is_valid, error = validate_execution_id(exec_id)
            assert is_valid, f"Expected '{exec_id}' to be valid"

    def test_region_with_three_letter_prefix(self):
        """Test region validation with three-letter prefix."""
        # Some regions have 3-letter prefixes (e.g., "gov")
        is_valid, error = validate_aws_region("us-gov-east-1")
        assert is_valid

    def test_validation_with_whitespace(self):
        """Test validation with various whitespace characters."""
        # Pipeline name with whitespace
        for whitespace in [" ", "\t", "\n", "\r", "\v", "\f"]:
            is_valid, error = validate_pipeline_name(f"pipeline{whitespace}test")
            assert not is_valid, (
                f"Pipeline name with whitespace '{repr(whitespace)}' should be invalid"
            )

        # Execution ID with embedded whitespace (should fail)
        is_valid, error = validate_execution_id("12345678-1234-1234-1234-123456789 12")
        assert not is_valid

        # Region with embedded whitespace (should fail)
        is_valid, error = validate_aws_region("us-east -1")
        assert not is_valid


class TestValidationConsistency:
    """Test consistency across validation functions."""

    def test_empty_input_handling(self):
        """Test that all validators handle empty input consistently."""
        validators = [
            (validate_pipeline_name, ""),
            (validate_execution_id, ""),
            (validate_aws_region, ""),
        ]

        for validator, empty_input in validators:
            is_valid, error = validator(empty_input)
            assert not is_valid
            assert "cannot be empty" in error

    def test_none_input_handling(self):
        """Test that all validators handle None input consistently."""
        validators = [
            validate_pipeline_name,
            validate_execution_id,
            validate_aws_region,
        ]

        for validator in validators:
            is_valid, error = validator(None)
            assert not is_valid
            assert "cannot be empty" in error or "must be a string" in error

    def test_non_string_input_handling(self):
        """Test that all validators handle non-string input consistently."""
        validators = [
            validate_pipeline_name,
            validate_execution_id,
            validate_aws_region,
        ]

        for validator in validators:
            is_valid, error = validator(123)
            assert not is_valid
            assert "must be a string" in error

    def test_return_value_structure(self):
        """Test that all validators return consistent tuple structure."""
        validators = [
            (validate_pipeline_name, "valid-pipeline"),
            (validate_execution_id, "12345678-1234-1234-1234-123456789012"),
            (validate_aws_region, "us-east-1"),
        ]

        for validator, valid_input in validators:
            result = validator(valid_input)
            assert isinstance(result, tuple)
            assert len(result) == 2
            is_valid, error = result
            assert isinstance(is_valid, bool)
            assert isinstance(error, str)
            assert is_valid is True
            assert error == ""

    def test_error_message_format(self):
        """Test that error messages follow consistent format."""
        test_cases = [
            (validate_pipeline_name, ""),
            (validate_execution_id, ""),
            (validate_aws_region, ""),
        ]

        for validator, invalid_input in test_cases:
            is_valid, error = validator(invalid_input)
            assert not is_valid
            assert len(error) > 0
            assert error[0].isupper() or error.startswith("AWS")  # Starts with capital
            # Error messages should be descriptive
            assert len(error) > 10
