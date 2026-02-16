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

"""Unit tests for load_instruction_content validation."""

import pytest

from awslabs.lza_mcp_server.utils.load_instruction_content import (
    load_instruction_content,
)


class TestLoadInstructionContentValidation:
    """Test input validation for instruction content loading."""

    def test_accepts_valid_markdown_filename(self):
        """Test function accepts valid .md filename."""
        # Act - Should not raise
        content = load_instruction_content("base_instructions.md")

        # Assert
        assert content is not None

    def test_filename_must_be_string(self):
        """Test filename parameter must be a string."""
        # Act & Assert
        with pytest.raises((TypeError, AttributeError)):
            load_instruction_content(None)

        with pytest.raises((TypeError, AttributeError)):
            load_instruction_content(123)

        with pytest.raises((TypeError, AttributeError)):
            load_instruction_content(["base_instructions.md"])

    def test_rejects_absolute_paths(self):
        """Test function rejects absolute file paths."""
        # Act & Assert - Absolute paths contain path separators
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("/etc/passwd")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

        with pytest.raises(ValueError):
            load_instruction_content("/tmp/nonexistent_test_file.md")

    def test_rejects_relative_path_traversal(self):
        """Test function rejects relative path traversal."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("../test.md")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

        with pytest.raises(ValueError):
            load_instruction_content("../../test.md")

    def test_accepts_only_filename(self):
        """Test function only accepts filename without path."""
        # Valid - just filename
        content = load_instruction_content("base_instructions.md")
        assert content is not None

        # Invalid - with subdirectory
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("subdir/test.md")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

    def test_case_sensitive_filename(self):
        """Test filename is case-sensitive on case-sensitive filesystems."""
        # This should work
        content = load_instruction_content("base_instructions.md")
        assert content is not None

        # This should fail on case-sensitive filesystems (wrong case)
        # On case-insensitive filesystems (like macOS default), this may succeed
        try:
            load_instruction_content("Base_Instructions.md")
            # If it succeeds, we're on a case-insensitive filesystem
        except FileNotFoundError:
            # Expected on case-sensitive filesystems
            pass

    def test_whitespace_in_filename(self):
        """Test handling of whitespace in filename."""
        # Act & Assert - Should fail as file doesn't exist
        with pytest.raises(FileNotFoundError):
            load_instruction_content(" base_instructions.md")

        with pytest.raises(FileNotFoundError):
            load_instruction_content("base_instructions.md ")

        with pytest.raises(FileNotFoundError):
            load_instruction_content("base instructions.md")


class TestLoadInstructionContentPathTraversal:
    """Test path traversal security validation."""

    def test_rejects_unix_path_separator(self):
        """Test function rejects Unix-style path separators."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("../base_instructions.md")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()
        assert "../base_instructions.md" in error_message

    def test_rejects_windows_path_separator(self):
        """Test function rejects Windows-style path separators."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("..\\base_instructions.md")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

    def test_rejects_multiple_parent_directory_traversal(self):
        """Test function rejects multiple parent directory traversal attempts."""
        # Act & Assert
        with pytest.raises(ValueError):
            load_instruction_content("../../../etc/passwd")

        with pytest.raises(ValueError):
            load_instruction_content("..\\..\\..\\windows\\system32\\config\\sam")

    def test_rejects_mixed_path_separators(self):
        """Test function rejects mixed Unix and Windows path separators."""
        # Act & Assert
        with pytest.raises(ValueError):
            load_instruction_content("../subdir\\file.md")

        with pytest.raises(ValueError):
            load_instruction_content("..\\subdir/file.md")

    def test_rejects_subdirectory_paths(self):
        """Test function rejects paths with subdirectories."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("subdir/file.md")

        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()

        with pytest.raises(ValueError):
            load_instruction_content("subdir\\file.md")

    def test_rejects_absolute_unix_paths(self):
        """Test function rejects absolute Unix paths."""
        # Act & Assert
        with pytest.raises(ValueError):
            load_instruction_content("/etc/passwd")

        with pytest.raises(ValueError):
            load_instruction_content("/tmp/test.md")

        with pytest.raises(ValueError):
            load_instruction_content("/var/log/system.log")

    def test_rejects_absolute_windows_paths(self):
        """Test function rejects absolute Windows paths."""
        # Act & Assert
        with pytest.raises(ValueError):
            load_instruction_content("C:\\Windows\\System32\\config\\sam")

        with pytest.raises(ValueError):
            load_instruction_content("D:\\data\\file.md")

    def test_rejects_current_directory_with_slash(self):
        """Test function rejects current directory notation with slash."""
        # Act & Assert
        with pytest.raises(ValueError):
            load_instruction_content("./base_instructions.md")

        with pytest.raises(ValueError):
            load_instruction_content(".\\base_instructions.md")

    def test_rejects_hidden_path_traversal(self):
        """Test function rejects hidden path traversal attempts."""
        # Act & Assert - Various obfuscation attempts
        with pytest.raises(ValueError):
            load_instruction_content("instructions/../../../etc/passwd")

        with pytest.raises(ValueError):
            load_instruction_content("test/../../base_instructions.md")

    def test_rejects_url_encoded_path_separators(self):
        """Test function behavior with URL-encoded characters in filename."""
        # Note: The function does NOT decode URL encoding, so %2F is treated
        # as literal characters in the filename. This is correct behavior.
        # The file simply won't exist with that name.
        try:
            load_instruction_content("..%2Ftest.md")
        except FileNotFoundError:
            # Expected - file with literal %2F in name doesn't exist
            pass
        except ValueError:
            # Also acceptable if implementation adds URL decode detection
            pass

        # Filename with URL-encoded characters but no actual path separators
        # should fail with FileNotFoundError (file doesn't exist)
        try:
            load_instruction_content("test%2Emd")
        except FileNotFoundError:
            # Expected - file doesn't exist
            pass
        except ValueError:
            # Should not raise ValueError for URL-encoded chars without path separators
            pytest.fail(
                "Should not raise ValueError for URL-encoded non-separator chars"
            )

    def test_accepts_valid_filename_with_dots(self):
        """Test function accepts valid filenames containing dots."""
        # Valid filenames with dots (but no path separators) should work
        # if the file exists
        try:
            # This will fail with FileNotFoundError since file doesn't exist
            # but should NOT fail with ValueError
            load_instruction_content("test.file.name.md")
        except FileNotFoundError:
            # Expected - file doesn't exist
            pass
        except ValueError:
            # Should not raise ValueError for dots without path separators
            pytest.fail("Should not raise ValueError for dots in filename")

    def test_accepts_valid_filename_with_underscores_and_hyphens(self):
        """Test function accepts valid filenames with underscores and hyphens."""
        # These are valid filename characters
        try:
            load_instruction_content("test-file_name.md")
        except FileNotFoundError:
            # Expected - file doesn't exist
            pass
        except ValueError:
            pytest.fail("Should not raise ValueError for hyphens and underscores")

    def test_path_traversal_validation_order(self):
        """Test that path separator validation happens before file existence check."""
        # Path separator validation should happen first, so we get ValueError
        # not FileNotFoundError
        with pytest.raises(ValueError) as exc_info:
            load_instruction_content("../nonexistent.md")

        # Verify it's the path separator error, not file not found
        error_message = str(exc_info.value)
        assert "path separators" in error_message.lower()
        assert "not found" not in error_message.lower()
