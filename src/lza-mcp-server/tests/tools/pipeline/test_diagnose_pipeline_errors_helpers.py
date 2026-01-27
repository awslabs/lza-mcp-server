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

"""Unit tests for diagnose_pipeline_errors helper functions."""

from awslabs.lza_mcp_server.tools.pipeline.diagnose_pipeline_errors import (
    extract_error_line,
)


class TestExtractErrorLine:
    """Test the extract_error_line helper function."""

    def test_extract_error_line_found(self):
        """Test extracting error line when present."""
        logs = """
        Some log line
        Another line
        | error | Something went wrong
        More logs
        """
        result = extract_error_line(logs)
        assert result == "| error | Something went wrong"

    def test_extract_error_line_not_found(self):
        """Test when no error line is present."""
        logs = """
        Some log line
        Another line
        No errors here
        """
        result = extract_error_line(logs)
        assert result == ""

    def test_extract_error_line_empty_logs(self):
        """Test with empty logs."""
        result = extract_error_line("")
        assert result == ""

    def test_extract_error_line_none_logs(self):
        """Test with None logs."""
        result = extract_error_line(None)
        assert result == ""
