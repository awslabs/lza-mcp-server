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

"""Unit tests for diagnose_deployment_errors helper functions."""

from awslabs.lza_mcp_server.tools.pipeline.diagnose_deployment_errors import (
    _extract_ecs_error_line,
    _extract_codebuild_error_line,
)
from awslabs.lza_mcp_server.tools.pipeline.common import validate_qualifier


class TestExtractEcsErrorLine:
    """Test the _extract_ecs_error_line helper function."""

    def test_extract_error_pipe_pattern(self):
        """Test extracting '| error |' pattern."""
        logs = "Starting\n| error | Something went wrong\nDone"
        result = _extract_ecs_error_line(logs)
        assert result == "| error | Something went wrong"

    def test_extract_error_colon_pattern(self):
        """Test extracting 'Error:' pattern."""
        logs = "Starting\nError: Configuration invalid\nDone"
        result = _extract_ecs_error_line(logs)
        assert result == "Error: Configuration invalid"

    def test_extract_failed_pattern(self):
        """Test extracting 'FAILED' pattern."""
        logs = "Starting\nStack deployment FAILED\nDone"
        result = _extract_ecs_error_line(logs)
        assert result == "Stack deployment FAILED"

    def test_extract_error_bracket_pattern(self):
        """Test extracting '[ERROR]' pattern."""
        logs = "Starting\n[ERROR] Something broke\nDone"
        result = _extract_ecs_error_line(logs)
        assert result == "[ERROR] Something broke"

    def test_no_error_found(self):
        """Test when no error patterns are present."""
        logs = "Starting\nAll good\nDone"
        result = _extract_ecs_error_line(logs)
        assert result is None

    def test_empty_logs(self):
        """Test with empty logs."""
        result = _extract_ecs_error_line("")
        assert result is None

    def test_none_logs(self):
        """Test with None logs."""
        result = _extract_ecs_error_line(None)
        assert result is None


class TestValidateQualifier:
    """Test the validate_qualifier helper function."""

    def test_valid_qualifier(self):
        """Test valid qualifier."""
        is_valid, error = validate_qualifier("container-dev-1")
        assert is_valid is True
        assert error == ""

    def test_valid_qualifier_alphanumeric(self):
        """Test valid alphanumeric qualifier."""
        is_valid, error = validate_qualifier("myenv123")
        assert is_valid is True

    def test_empty_qualifier(self):
        """Test empty qualifier."""
        is_valid, error = validate_qualifier("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_none_qualifier(self):
        """Test None qualifier."""
        is_valid, error = validate_qualifier(None)
        assert is_valid is False

    def test_qualifier_with_special_chars(self):
        """Test qualifier with invalid characters."""
        is_valid, error = validate_qualifier("test@env!")
        assert is_valid is False
        assert "letters, numbers, and hyphens" in error

    def test_qualifier_too_long(self):
        """Test qualifier exceeding max length."""
        is_valid, error = validate_qualifier("a" * 101)
        assert is_valid is False
        assert "too long" in error.lower()


class TestExtractCodebuildErrorLine:
    """Test the _extract_codebuild_error_line helper function."""

    def test_extract_error_line_found(self):
        """Test extracting error line when present."""
        logs = "Some log line\nAnother line\n| error | Something went wrong\nMore logs"
        result = _extract_codebuild_error_line(logs)
        assert result == "| error | Something went wrong"

    def test_extract_error_line_not_found(self):
        """Test when no error line is present."""
        logs = "Some log line\nAnother line\nNo errors here"
        result = _extract_codebuild_error_line(logs)
        assert result == ""

    def test_extract_error_line_empty_logs(self):
        """Test with empty logs."""
        result = _extract_codebuild_error_line("")
        assert result == ""

    def test_extract_error_line_none_logs(self):
        """Test with None logs."""
        result = _extract_codebuild_error_line(None)
        assert result == ""
