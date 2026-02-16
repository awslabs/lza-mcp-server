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

"""Unit tests for load_instruction_content error scenarios."""

import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.utils.load_instruction_content import (
    load_instruction_content,
)


class TestLoadInstructionContentErrors:
    """Test error handling in instruction content loading."""

    def test_file_not_found_raises_error(self):
        """Test loading non-existent file raises FileNotFoundError."""
        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_instruction_content("nonexistent_file.md")

        # Verify error message is helpful
        error_message = str(exc_info.value)
        assert "nonexistent_file.md" in error_message
        assert "not found" in error_message.lower()
        assert "Expected location:" in error_message

    def test_file_not_found_shows_available_files(self):
        """Test FileNotFoundError shows available markdown files."""
        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_instruction_content("missing.md")

        # Verify error shows available files
        error_message = str(exc_info.value)
        assert "Available files:" in error_message

    def test_file_not_found_shows_expected_location(self):
        """Test FileNotFoundError shows expected file location."""
        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_instruction_content("test.md")

        # Verify error shows expected path
        error_message = str(exc_info.value)
        assert "Expected location:" in error_message
        assert "instructions" in error_message

    @patch("builtins.open", side_effect=IOError("Permission denied"))
    def test_io_error_during_read(self, mock_file):
        """Test IOError is raised when file cannot be read."""
        # Act & Assert
        with pytest.raises(IOError) as exc_info:
            load_instruction_content("base_instructions.md")

        # Verify error message includes filename and original error
        error_message = str(exc_info.value)
        assert "base_instructions.md" in error_message
        assert "Permission denied" in error_message

    @patch("builtins.open", side_effect=PermissionError("Access denied"))
    def test_permission_error_during_read(self, mock_file):
        """Test PermissionError is wrapped in IOError."""
        # Act & Assert
        with pytest.raises(IOError) as exc_info:
            load_instruction_content("base_instructions.md")

        # Verify error is wrapped
        error_message = str(exc_info.value)
        assert "base_instructions.md" in error_message
        assert "Access denied" in error_message

    def test_empty_filename_raises_error(self):
        """Test empty filename raises appropriate error."""
        # Act & Assert - Empty filename results in directory path
        with pytest.raises((FileNotFoundError, IOError)):
            load_instruction_content("")

    def test_filename_with_path_traversal(self):
        """Test filename with path traversal attempts raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("../../../etc/passwd")

        # Verify error message
        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

    def test_filename_without_extension(self):
        """Test filename without .md extension raises error."""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            load_instruction_content("base_instructions")
