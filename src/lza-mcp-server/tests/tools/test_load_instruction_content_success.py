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

"""Unit tests for load_instruction_content success scenarios."""

from awslabs.lza_mcp_server.utils.load_instruction_content import (
    load_instruction_content,
)


class TestLoadInstructionContentSuccess:
    """Test successful instruction content loading."""

    def test_load_base_instructions(self):
        """Test loading base_instructions.md successfully."""
        # Act
        content = load_instruction_content("base_instructions.md")

        # Assert
        assert isinstance(content, str)
        assert len(content) > 0
        assert "AWS Landing Zone Accelerator (LZA) MCP Server" in content

    def test_load_uc_merge_instructions(self):
        """Test loading uc_merge_instructions.md successfully."""
        # Act
        content = load_instruction_content("uc_merge_instructions.md")

        # Assert
        assert isinstance(content, str)
        assert len(content) > 0
        assert "UC Merge Tools" in content

    def test_load_workflow_instructions(self):
        """Test loading workflow_instructions.md successfully."""
        # Act
        content = load_instruction_content("workflow_instructions.md")

        # Assert
        assert isinstance(content, str)
        assert len(content) > 0
        assert "Typical Workflows" in content

    def test_content_not_empty(self):
        """Test loaded content is not empty."""
        # Act
        content = load_instruction_content("base_instructions.md")

        # Assert
        assert content.strip() != ""
        assert len(content) > 100  # Should have substantial content

    def test_content_preserves_formatting(self):
        """Test loaded content preserves markdown formatting."""
        # Act
        content = load_instruction_content("base_instructions.md")

        # Assert
        assert "#" in content  # Markdown headers
        assert "-" in content  # Markdown lists
        assert "\n" in content  # Line breaks preserved

    def test_multiple_loads_return_same_content(self):
        """Test loading same file multiple times returns identical content."""
        # Act
        content1 = load_instruction_content("base_instructions.md")
        content2 = load_instruction_content("base_instructions.md")

        # Assert
        assert content1 == content2

    def test_content_is_utf8_encoded(self):
        """Test content is properly UTF-8 encoded."""
        # Act
        content = load_instruction_content("base_instructions.md")

        # Assert - Should not raise encoding errors
        assert isinstance(content, str)
        # Verify we can encode/decode without errors
        encoded = content.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert decoded == content
