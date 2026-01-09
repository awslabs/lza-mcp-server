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

"""Tests for comprehensive input validation and sanitization."""

from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    sanitize_string,
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
)


class TestStringValidation:
    """Test string input validation."""

    def test_valid_string(self):
        is_valid, msg = validate_string_input("test", "field")
        assert is_valid
        assert msg == ""

    def test_empty_string_not_allowed(self):
        is_valid, msg = validate_string_input("", "field", allow_empty=False)
        assert not is_valid
        assert "cannot be empty" in msg

    def test_empty_string_allowed(self):
        is_valid, msg = validate_string_input("", "field", allow_empty=True)
        assert is_valid

    def test_none_value(self):
        is_valid, msg = validate_string_input(None, "field")
        assert not is_valid
        assert "cannot be None" in msg

    def test_non_string_type(self):
        is_valid, msg = validate_string_input(123, "field")
        assert not is_valid
        assert "must be a string" in msg

    def test_min_length(self):
        is_valid, msg = validate_string_input("ab", "field", min_length=3)
        assert not is_valid
        assert "at least 3 characters" in msg

    def test_max_length(self):
        is_valid, msg = validate_string_input("a" * 101, "field", max_length=100)
        assert not is_valid
        assert "exceeds maximum length" in msg

    def test_pattern_match(self):
        is_valid, msg = validate_string_input(
            "test123", "field", pattern=r"^[a-z0-9]+$"
        )
        assert is_valid

    def test_pattern_no_match(self):
        is_valid, msg = validate_string_input(
            "test@123", "field", pattern=r"^[a-z0-9]+$"
        )
        assert not is_valid
        assert "does not match required format" in msg


class TestStringSanitization:
    """Test string sanitization."""

    def test_sanitize_normal_string(self):
        result = sanitize_string("normal text")
        assert result == "normal text"

    def test_sanitize_null_bytes(self):
        result = sanitize_string("test\x00data")
        assert result == "testdata"

    def test_sanitize_control_characters(self):
        result = sanitize_string("test\x01\x02data")
        assert result == "testdata"

    def test_sanitize_keeps_newlines(self):
        result = sanitize_string("line1\nline2")
        assert result == "line1\nline2"

    def test_sanitize_truncates(self):
        result = sanitize_string("a" * 2000, max_length=100)
        assert len(result) == 100

    def test_sanitize_non_string(self):
        result = sanitize_string(123)
        assert result == "123"


class TestS3BucketValidation:
    """Test S3 bucket name validation."""

    def test_valid_bucket_name(self):
        is_valid, msg = validate_s3_bucket_name("my-bucket-123")
        assert is_valid

    def test_empty_bucket_name(self):
        is_valid, msg = validate_s3_bucket_name("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_bucket_name_too_short(self):
        is_valid, msg = validate_s3_bucket_name("ab")
        assert not is_valid
        assert "at least 3 characters" in msg

    def test_bucket_name_too_long(self):
        is_valid, msg = validate_s3_bucket_name("a" * 64)
        assert not is_valid
        assert "exceeds maximum length" in msg

    def test_bucket_name_uppercase(self):
        is_valid, msg = validate_s3_bucket_name("MyBucket")
        assert not is_valid
        assert "lowercase" in msg

    def test_bucket_name_consecutive_periods(self):
        is_valid, msg = validate_s3_bucket_name("my..bucket")
        assert not is_valid
        assert "consecutive periods" in msg

    def test_bucket_name_ip_address(self):
        is_valid, msg = validate_s3_bucket_name("192.168.1.1")
        assert not is_valid
        assert "IP address" in msg

    def test_bucket_name_starts_with_hyphen(self):
        is_valid, msg = validate_s3_bucket_name("-mybucket")
        assert not is_valid

    def test_bucket_name_ends_with_hyphen(self):
        is_valid, msg = validate_s3_bucket_name("mybucket-")
        assert not is_valid


class TestS3KeyValidation:
    """Test S3 object key validation."""

    def test_valid_key(self):
        is_valid, msg = validate_s3_key("path/to/file.txt")
        assert is_valid

    def test_empty_key(self):
        is_valid, msg = validate_s3_key("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_key_with_path_traversal(self):
        is_valid, msg = validate_s3_key("path/../file.txt")
        assert not is_valid
        assert "path traversal" in msg

    def test_key_starts_with_slash(self):
        is_valid, msg = validate_s3_key("/absolute/path")
        assert not is_valid
        assert "cannot start with" in msg

    def test_key_too_long(self):
        is_valid, msg = validate_s3_key("a" * 1025)
        assert not is_valid
        assert "exceeds maximum size" in msg


class TestFilePathValidation:
    """Test file path validation."""

    def test_valid_relative_path(self):
        is_valid, msg = validate_file_path("config/file.yaml")
        assert is_valid

    def test_empty_path(self):
        is_valid, msg = validate_file_path("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_path_with_null_bytes(self):
        is_valid, msg = validate_file_path("file\x00.txt")
        assert not is_valid
        assert "null bytes" in msg

    def test_path_traversal(self):
        is_valid, msg = validate_file_path("../../../etc/passwd")
        assert not is_valid
        assert "path traversal" in msg

    def test_absolute_path_not_allowed(self):
        is_valid, msg = validate_file_path("/etc/passwd", allow_absolute=False)
        assert not is_valid
        assert "Absolute paths are not allowed" in msg

    def test_absolute_path_allowed(self):
        is_valid, msg = validate_file_path("/etc/passwd", allow_absolute=True)
        assert is_valid

    def test_path_within_base_directory(self, tmp_path):
        is_valid, msg = validate_file_path("subdir/file.txt", base_directory=tmp_path)
        assert is_valid

    def test_path_escapes_base_directory(self, tmp_path):
        # This should fail even without .. because resolved path escapes base
        is_valid, msg = validate_file_path("../outside.txt", base_directory=tmp_path)
        assert not is_valid


class TestSessionIdValidation:
    """Test session ID validation."""

    def test_valid_session_id(self):
        is_valid, msg = validate_session_id("uc-session-20250127-143022")
        assert is_valid

    def test_empty_session_id(self):
        is_valid, msg = validate_session_id("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_invalid_format(self):
        is_valid, msg = validate_session_id("invalid-session-id")
        assert not is_valid
        assert "Invalid session ID format" in msg

    def test_wrong_prefix(self):
        is_valid, msg = validate_session_id("session-20250127-143022")
        assert not is_valid

    def test_invalid_date_format(self):
        is_valid, msg = validate_session_id("uc-session-2025-01-27-143022")
        assert not is_valid


class TestLzaVersionValidation:
    """Test LZA version validation."""

    def test_valid_version_with_v(self):
        is_valid, msg = validate_lza_version("v1.9.2")
        assert is_valid

    def test_valid_version_without_v(self):
        is_valid, msg = validate_lza_version("1.9.2")
        assert is_valid

    def test_empty_version(self):
        is_valid, msg = validate_lza_version("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_invalid_format(self):
        is_valid, msg = validate_lza_version("1.9")
        assert not is_valid
        assert "Invalid LZA version format" in msg

    def test_non_numeric_version(self):
        is_valid, msg = validate_lza_version("v1.9.x")
        assert not is_valid


class TestEmailValidation:
    """Test email address validation."""

    def test_valid_email(self):
        is_valid, msg = validate_email("user@example.com")
        assert is_valid

    def test_empty_email(self):
        is_valid, msg = validate_email("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_invalid_format_no_at(self):
        is_valid, msg = validate_email("userexample.com")
        assert not is_valid
        assert "Invalid email address format" in msg

    def test_invalid_format_no_domain(self):
        is_valid, msg = validate_email("user@")
        assert not is_valid

    def test_email_too_long(self):
        is_valid, msg = validate_email("a" * 250 + "@example.com")
        assert not is_valid
        assert "exceeds maximum length" in msg


class TestUrlValidation:
    """Test URL validation."""

    def test_valid_https_url(self):
        is_valid, msg = validate_url("https://example.com")
        assert is_valid

    def test_valid_s3_url(self):
        is_valid, msg = validate_url("s3://bucket/key")
        assert is_valid

    def test_empty_url(self):
        is_valid, msg = validate_url("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_url_without_scheme(self):
        is_valid, msg = validate_url("example.com")
        assert not is_valid
        assert "must include a scheme" in msg

    def test_url_disallowed_scheme(self):
        is_valid, msg = validate_url(
            "ftp://example.com", allowed_schemes=["http", "https"]
        )
        assert not is_valid
        assert "not allowed" in msg

    def test_url_without_host(self):
        is_valid, msg = validate_url("https://")
        assert not is_valid
        assert "must include a domain" in msg


class TestIntegerRangeValidation:
    """Test integer range validation."""

    def test_valid_integer(self):
        is_valid, msg = validate_integer_range(5, "field", min_value=1, max_value=10)
        assert is_valid

    def test_non_integer(self):
        is_valid, msg = validate_integer_range("5", "field")
        assert not is_valid
        assert "must be an integer" in msg

    def test_below_minimum(self):
        is_valid, msg = validate_integer_range(0, "field", min_value=1)
        assert not is_valid
        assert "at least 1" in msg

    def test_above_maximum(self):
        is_valid, msg = validate_integer_range(11, "field", max_value=10)
        assert not is_valid
        assert "at most 10" in msg

    def test_no_range_constraints(self):
        is_valid, msg = validate_integer_range(999999, "field")
        assert is_valid


class TestDictValidation:
    """Test dictionary input validation."""

    def test_valid_dict(self):
        is_valid, msg = validate_dict_input({"key": "value"}, "field")
        assert is_valid

    def test_non_dict(self):
        is_valid, msg = validate_dict_input("not a dict", "field")
        assert not is_valid
        assert "must be a dictionary" in msg

    def test_missing_required_keys(self):
        is_valid, msg = validate_dict_input({"a": 1}, "field", required_keys=["a", "b"])
        assert not is_valid
        assert "missing required keys" in msg
        assert "b" in msg

    def test_all_required_keys_present(self):
        is_valid, msg = validate_dict_input(
            {"a": 1, "b": 2}, "field", required_keys=["a", "b"]
        )
        assert is_valid

    def test_exceeds_max_depth(self):
        # Create deeply nested dict
        deep_dict = {"level": 1}
        current = deep_dict
        for i in range(15):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        is_valid, msg = validate_dict_input(deep_dict, "field", max_depth=10)
        assert not is_valid
        assert "exceeds maximum nesting depth" in msg


class TestCommandArgumentSanitization:
    """Test command argument sanitization."""

    def test_sanitize_normal_argument(self):
        result = sanitize_command_argument("normal-arg")
        assert result == "normal-arg"

    def test_sanitize_pipe(self):
        result = sanitize_command_argument("arg|command")
        assert "|" not in result

    def test_sanitize_semicolon(self):
        result = sanitize_command_argument("arg;command")
        assert ";" not in result

    def test_sanitize_backtick(self):
        result = sanitize_command_argument("arg`command`")
        assert "`" not in result

    def test_sanitize_dollar(self):
        result = sanitize_command_argument("arg$VAR")
        assert "$" not in result

    def test_sanitize_multiple_dangerous_chars(self):
        result = sanitize_command_argument("arg|&;$`")
        assert result == "arg"


class TestJsonSchemaPathValidation:
    """Test JSON schema path validation."""

    def test_valid_schema_path(self):
        is_valid, msg = validate_json_schema_path("accounts-config")
        assert is_valid

    def test_valid_schema_path_with_json_extension(self):
        is_valid, msg = validate_json_schema_path("accounts-config.json")
        assert is_valid

    def test_valid_schema_path_organization_config(self):
        is_valid, msg = validate_json_schema_path("organization-config.json")
        assert is_valid

    def test_empty_schema_path(self):
        is_valid, msg = validate_json_schema_path("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_schema_path_with_uppercase(self):
        is_valid, msg = validate_json_schema_path("Accounts-Config")
        assert not is_valid
        assert "lowercase" in msg

    def test_schema_path_with_special_chars(self):
        is_valid, msg = validate_json_schema_path("accounts_config")
        assert not is_valid

    def test_schema_path_with_invalid_extension(self):
        is_valid, msg = validate_json_schema_path("accounts-config.yaml")
        assert not is_valid

    def test_schema_path_too_long(self):
        is_valid, msg = validate_json_schema_path("a" * 101)
        assert not is_valid
        assert "exceeds maximum length" in msg


class TestAccountIdValidation:
    """Test AWS account ID validation."""

    def test_valid_account_id(self):
        is_valid, msg = validate_account_id("123456789012")
        assert is_valid

    def test_empty_account_id(self):
        is_valid, msg = validate_account_id("")
        assert not is_valid
        assert "cannot be empty" in msg

    def test_account_id_too_short(self):
        is_valid, msg = validate_account_id("12345678901")
        assert not is_valid
        assert "exactly 12 digits" in msg

    def test_account_id_too_long(self):
        is_valid, msg = validate_account_id("1234567890123")
        assert not is_valid
        assert "exactly 12 digits" in msg

    def test_account_id_non_numeric(self):
        is_valid, msg = validate_account_id("12345678901a")
        assert not is_valid
        assert "exactly 12 digits" in msg


class TestPipelineNameValidation:
    """Test AWS CodePipeline name validation."""

    def test_valid_pipeline_name(self):
        is_valid, error = validate_pipeline_name("AWSAccelerator-Pipeline")
        assert is_valid
        assert error == ""

    def test_valid_pipeline_name_with_underscores(self):
        is_valid, error = validate_pipeline_name("My_Pipeline_123")
        assert is_valid
        assert error == ""

    def test_empty_pipeline_name(self):
        is_valid, error = validate_pipeline_name("")
        assert not is_valid
        assert "cannot be empty" in error

    def test_pipeline_name_too_long(self):
        long_name = "a" * 101
        is_valid, error = validate_pipeline_name(long_name)
        assert not is_valid
        assert "exceeds maximum length" in error

    def test_pipeline_name_with_spaces(self):
        is_valid, error = validate_pipeline_name("My Pipeline")
        assert not is_valid
        assert "can only contain" in error

    def test_pipeline_name_with_special_chars(self):
        is_valid, error = validate_pipeline_name("Pipeline@123")
        assert not is_valid
        assert "can only contain" in error


class TestExecutionIdValidation:
    """Test AWS CodePipeline execution ID validation."""

    def test_valid_execution_id(self):
        is_valid, error = validate_execution_id("12345678-1234-1234-1234-123456789012")
        assert is_valid
        assert error == ""

    def test_valid_execution_id_lowercase(self):
        is_valid, error = validate_execution_id("abcdef12-3456-7890-abcd-ef1234567890")
        assert is_valid
        assert error == ""

    def test_empty_execution_id(self):
        is_valid, error = validate_execution_id("")
        assert not is_valid
        assert "cannot be empty" in error

    def test_invalid_execution_id_format(self):
        is_valid, error = validate_execution_id("not-a-uuid")
        assert not is_valid
        assert "valid UUID format" in error

    def test_execution_id_missing_hyphens(self):
        is_valid, error = validate_execution_id("12345678123412341234123456789012")
        assert not is_valid
        assert "valid UUID format" in error

    def test_execution_id_wrong_length(self):
        is_valid, error = validate_execution_id("1234-1234-1234-1234")
        assert not is_valid
        assert "valid UUID format" in error
