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

"""Additional tests for load_instruction_content to cover path traversal resolution."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from awslabs.lza_mcp_server.utils.load_instruction_content import (
    load_instruction_content,
)


class TestLoadInstructionContentPathTraversalResolution:
    """Test the resolved path traversal check (lines 49-50)."""

    @patch("awslabs.lza_mcp_server.utils.load_instruction_content.Path")
    def test_resolved_path_escapes_instructions_dir(self, mock_path_cls):
        """Test path traversal detected via resolved path check."""
        # Create mock path objects
        mock_instructions_dir = MagicMock(spec=Path)
        mock_file_path = MagicMock(spec=Path)
        mock_resolved_path = MagicMock(spec=Path)
        mock_resolved_instructions = MagicMock(spec=Path)

        # Set up the chain: Path(__file__).parent.parent / "instructions"
        mock_path_instance = MagicMock(spec=Path)
        mock_path_cls.return_value = mock_path_instance
        mock_path_instance.parent = MagicMock(spec=Path)
        mock_path_instance.parent.parent = MagicMock(spec=Path)
        mock_path_instance.parent.parent.__truediv__ = MagicMock(
            return_value=mock_instructions_dir
        )

        # instructions_dir / filename
        mock_instructions_dir.__truediv__ = MagicMock(return_value=mock_file_path)

        # resolve() calls
        mock_file_path.resolve.return_value = mock_resolved_path
        mock_instructions_dir.resolve.return_value = mock_resolved_instructions

        # Make relative_to raise ValueError (path escapes directory)
        mock_resolved_path.relative_to.side_effect = ValueError("not relative")

        with pytest.raises(ValueError, match="Path traversal detected"):
            load_instruction_content("sneaky_file.md")
