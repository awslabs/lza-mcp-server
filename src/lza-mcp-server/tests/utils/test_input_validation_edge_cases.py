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

"""Tests for edge cases in input validation to improve coverage."""

from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    validate_s3_bucket_name,
    validate_s3_key,
    validate_file_path,
    validate_session_id,
    validate_lza_version,
    validate_email,
    validate_url,
    validate_integer_range,
    validate_dict_input,
    sanitize_command_argument,
    validate_json_schema_path,
    validate_account_id,
    validate_pipeline_name,
    validate_execution_id,
    VALIDATORS,
)


class TestStringValidationEdgeCases:
    """Test edge cases for string validation."""

    def test_empty_string_allowed_with_pattern(self):
        """Test that empty string with allow_empty=True skips pattern validation."""
        # Line 53: Early return when empty is allowed
        is_valid, msg = validate_string_input(
            "", "field", allow_empty=True, pattern=r"^[a-z]+$"
        )
        assert is_valid
        assert msg == ""

    def test_none_with_allow_empty(self):
        """Test None value with allow_empty=True."""
        # Line 53: None with allow_empty should return True
        is_valid, msg = validate_string_input(None, "field", allow_empty=True)
        assert is_valid
        assert msg == ""


class TestS3BucketNameEdgeCases:
    """Test edge cases for S3 bucket name validation."""

    def test_non_string_bucket_name(self):
        """Test non-string bucket name."""
        # Line 118: Non-string type check
        is_valid, msg = validate_s3_bucket_name(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_bucket_name_with_uppercase_letters(self):
        """Test bucket name with uppercase letters."""
        is_valid, msg = validate_s3_bucket_name("MyBucket")
        assert not is_valid
        assert "lowercase" in msg


class TestS3KeyEdgeCases:
    """Test edge cases for S3 key validation."""

    def test_non_string_s3_key(self):
        """Test non-string S3 key."""
        # Line 165: Non-string type check
        is_valid, msg = validate_s3_key(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_s3_key_max_size(self):
        """Test S3 key at maximum size."""
        # Create a key that's exactly 1024 bytes
        key = "a" * 1024
        is_valid, msg = validate_s3_key(key)
        assert is_valid


class TestFilePathEdgeCases:
    """Test edge cases for file path validation."""

    def test_non_string_file_path(self):
        """Test non-string file path."""
        # Line 201: Non-string type check
        is_valid, msg = validate_file_path(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_file_path_with_windows_drive_letter(self):
        """Test file path with Windows drive letter."""
        is_valid, msg = validate_file_path("C:\\path\\to\\file", allow_absolute=False)
        assert not is_valid
        assert "Absolute paths are not allowed" in msg


class TestSessionIdEdgeCases:
    """Test edge cases for session ID validation."""

    def test_non_string_session_id(self):
        """Test non-string session ID."""
        # Line 225: Non-string type check
        is_valid, msg = validate_session_id(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_session_id_with_invalid_date_format(self):
        """Test session ID with invalid date format."""
        # Line 226-227: Pattern matching
        is_valid, msg = validate_session_id("uc-session-2024-01-01-120000")
        assert not is_valid
        assert "Invalid session ID format" in msg


class TestLzaVersionEdgeCases:
    """Test edge cases for LZA version validation."""

    def test_non_string_lza_version(self):
        """Test non-string LZA version."""
        # Line 245: Non-string type check
        is_valid, msg = validate_lza_version(1.9)
        assert not is_valid
        assert "must be a string" in msg

    def test_lza_version_with_patch_only(self):
        """Test LZA version with only patch number."""
        is_valid, msg = validate_lza_version("1.9")
        assert not is_valid
        assert "Invalid LZA version format" in msg


class TestEmailEdgeCases:
    """Test edge cases for email validation."""

    def test_non_string_email(self):
        """Test non-string email."""
        # Line 269: Non-string type check
        is_valid, msg = validate_email(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_email_at_max_length(self):
        """Test email at maximum length (254 characters)."""
        # Create an email that's exactly 254 characters
        local_part = "a" * 64
        domain_part = "b" * (254 - 64 - 1 - 4)  # -1 for @, -4 for .com
        email = f"{local_part}@{domain_part}.com"
        is_valid, msg = validate_email(email)
        assert is_valid


class TestUrlEdgeCases:
    """Test edge cases for URL validation."""

    def test_non_string_url(self):
        """Test non-string URL."""
        # Line 296: Non-string type check
        is_valid, msg = validate_url(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_url_with_s3_scheme_no_netloc(self):
        """Test S3 URL without netloc."""
        is_valid, msg = validate_url("s3://bucket/key", allowed_schemes=["s3"])
        assert is_valid


class TestIntegerRangeEdgeCases:
    """Test edge cases for integer range validation."""

    def test_integer_at_min_boundary(self):
        """Test integer at minimum boundary."""
        # Line 326: Boundary check
        is_valid, msg = validate_integer_range(10, "field", min_value=10)
        assert is_valid

    def test_integer_at_max_boundary(self):
        """Test integer at maximum boundary."""
        is_valid, msg = validate_integer_range(100, "field", max_value=100)
        assert is_valid


class TestDictValidationEdgeCases:
    """Test edge cases for dict validation."""

    def test_dict_with_list_nesting(self):
        """Test dict with nested lists."""
        # Line 346-347: List nesting depth check
        nested_dict = {"items": [{"nested": [{"deep": "value"}]}]}
        is_valid, msg = validate_dict_input(nested_dict, "field", max_depth=5)
        assert is_valid

    def test_dict_with_empty_list(self):
        """Test dict with empty list."""
        nested_dict = {"items": []}
        is_valid, msg = validate_dict_input(nested_dict, "field")
        assert is_valid


class TestCommandArgumentSanitizationEdgeCases:
    """Test edge cases for command argument sanitization."""

    def test_sanitize_non_string_argument(self):
        """Test sanitizing non-string argument."""
        # Line 416: Non-string conversion
        result = sanitize_command_argument(123)
        assert result == "123"

    def test_sanitize_argument_with_parentheses(self):
        """Test sanitizing argument with parentheses."""
        result = sanitize_command_argument("arg(command)")
        assert "(" not in result
        assert ")" not in result


class TestJsonSchemaPathEdgeCases:
    """Test edge cases for JSON schema path validation."""

    def test_non_string_schema_path(self):
        """Test non-string schema path."""
        # Line 435: Non-string type check
        is_valid, msg = validate_json_schema_path(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_schema_path_with_numbers_only(self):
        """Test schema path with only numbers."""
        is_valid, msg = validate_json_schema_path("12345")
        assert is_valid


class TestAccountIdEdgeCases:
    """Test edge cases for account ID validation."""

    def test_non_string_account_id(self):
        """Test non-string account ID."""
        # Line 459: Non-string type check
        is_valid, msg = validate_account_id(123456789012)
        assert not is_valid
        assert "must be a string" in msg

    def test_account_id_with_leading_zeros(self):
        """Test account ID with leading zeros."""
        is_valid, msg = validate_account_id("000000000001")
        assert is_valid


class TestPipelineNameEdgeCases:
    """Test edge cases for pipeline name validation."""

    def test_non_string_pipeline_name(self):
        """Test non-string pipeline name."""
        # Line 487: Non-string type check
        is_valid, msg = validate_pipeline_name(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_pipeline_name_with_periods(self):
        """Test pipeline name with periods."""
        is_valid, msg = validate_pipeline_name("My.Pipeline.Name")
        assert is_valid


class TestExecutionIdEdgeCases:
    """Test edge cases for execution ID validation."""

    def test_non_string_execution_id(self):
        """Test non-string execution ID."""
        # Line 509: Non-string type check
        is_valid, msg = validate_execution_id(123)
        assert not is_valid
        assert "must be a string" in msg

    def test_execution_id_with_uppercase_hex(self):
        """Test execution ID with uppercase hex characters."""
        # Line 517: UUID pattern matching with uppercase
        is_valid, msg = validate_execution_id("ABCDEF12-3456-7890-ABCD-EF1234567890")
        assert is_valid


class TestValidatorsRegistry:
    """Test the VALIDATORS registry."""

    def test_validators_registry_contains_all_functions(self):
        """Test that VALIDATORS registry contains all validation functions."""
        # Line 547: VALIDATORS registry
        expected_validators = [
            "string",
            "s3_bucket",
            "s3_key",
            "file_path",
            "session_id",
            "lza_version",
            "email",
            "url",
            "integer_range",
            "dict",
            "schema_path",
            "account_id",
            "pipeline_name",
            "execution_id",
        ]

        for validator_name in expected_validators:
            assert validator_name in VALIDATORS
            assert callable(VALIDATORS[validator_name])

    def test_validators_registry_string_validator(self):
        """Test using validator from registry."""
        validator = VALIDATORS["string"]
        is_valid, msg = validator("test", "field")
        assert is_valid

    def test_validators_registry_s3_bucket_validator(self):
        """Test S3 bucket validator from registry."""
        validator = VALIDATORS["s3_bucket"]
        is_valid, msg = validator("my-bucket-name")
        assert is_valid
