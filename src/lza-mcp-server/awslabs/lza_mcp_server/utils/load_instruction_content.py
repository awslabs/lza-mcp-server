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

"""Instruction content loader for MCP server."""

from pathlib import Path


def load_instruction_content(filename: str) -> str:
    """Load instruction content from a markdown file.

    Args:
        filename: Name of the markdown file (e.g., 'base_instructions.md')

    Returns:
        str: Content of the markdown file

    Raises:
        FileNotFoundError: If the instruction file does not exist
        IOError: If there is an error reading the file
        ValueError: If filename contains path separators or attempts path traversal
    """
    # Validate filename doesn't contain path separators
    if "/" in filename or "\\" in filename:
        raise ValueError(f"Filename must not contain path separators: {filename}")

    # Get the instructions directory (sibling to utils)
    instructions_dir = Path(__file__).parent.parent / "instructions"

    # Construct the full path to the instruction file
    file_path = instructions_dir / filename

    # Resolve and validate the path stays within instructions directory
    resolved_path = file_path.resolve()
    resolved_instructions = instructions_dir.resolve()
    try:
        resolved_path.relative_to(resolved_instructions)
    except ValueError:
        raise ValueError(f"Path traversal detected: {filename}")

    # Check if file exists
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Instruction file not found: {filename}\n"
            f"Expected location: {resolved_path}\n"
            f"Available files: {list(instructions_dir.glob('*.md'))}"
        )

    # Read and return the content
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except OSError as e:
        raise IOError(f"Error reading instruction file '{filename}': {e}") from e
