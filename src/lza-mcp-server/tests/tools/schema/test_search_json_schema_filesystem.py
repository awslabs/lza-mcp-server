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

"""Unit tests for search_json_schema file system operations."""

import pytest
from unittest.mock import AsyncMock, patch

from awslabs.lza_mcp_server.tools.schema.search_json_schema import (
    tool_search_json_schema,
)


class TestSearchJsonSchemaFilesystem:
    """Test file system operations for search_json_schema."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_schema_file_not_found_no_version_dir(self, mock_exists):
        """Test error when version directory doesn't exist."""
        ctx = AsyncMock()
        mock_exists.return_value = False

        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v99.99.99", search_terms=["test"]
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "available_versions" in result
        assert "hint" in result
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.isdir")
    @patch("os.path.exists")
    @patch("os.listdir")
    async def test_schema_file_not_found_with_available_versions(
        self, mock_listdir, mock_exists, mock_isdir
    ):
        """Test error message includes available versions."""
        ctx = AsyncMock()

        def exists_side_effect(path):
            if "v99.99.99" in path:
                return False
            if "json-schemas" in path and "v99.99.99" not in path:
                return True
            return False

        mock_exists.side_effect = exists_side_effect
        mock_isdir.return_value = True
        mock_listdir.return_value = ["v1.12.0", "v1.13.0", "v1.14.0"]

        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v99.99.99", search_terms=["test"]
        )

        assert result["success"] is False
        assert result["available_versions"] == ["v1.12.0", "v1.13.0", "v1.14.0"]
        assert "getDeployedLzaVersion" in result["hint"]

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_version_dir_exists_but_no_combined_json(self, mock_exists):
        """Test error when version directory exists but combined.json is missing."""
        ctx = AsyncMock()

        def exists_side_effect(path):
            if "combined.json" in path:
                return False
            if "v1.12.0" in path:
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
        )

        assert result["success"] is False
        assert "Schema file not found" in result["error"]
        assert "combined.json not found" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_schema_path_construction(self, mock_exists):
        """Test that schema path is correctly constructed."""
        ctx = AsyncMock()
        mock_exists.return_value = False

        await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
        )

        # Verify the expected path was checked
        expected_path = "/app/json-schemas/v1.12.0/combined.json"
        mock_exists.assert_any_call(expected_path)
        ctx.info.assert_any_call(f"Using version-specific schema path: {expected_path}")
