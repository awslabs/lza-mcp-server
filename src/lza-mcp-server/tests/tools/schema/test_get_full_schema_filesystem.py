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

"""Unit tests for get_full_schema filesystem operations."""

import pytest
from unittest.mock import AsyncMock, patch, mock_open

from awslabs.lza_mcp_server.tools.schema.get_full_schema import tool_get_full_schema


class TestGetFullSchemaFilesystem:
    """Test filesystem operations for get_full_schema."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_version_directory_not_found(self, mock_exists):
        """Test error when version directory doesn't exist."""
        ctx = AsyncMock()
        mock_exists.side_effect = lambda path: False

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.99.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "v1.99.0" in result["message"]
        assert "available_versions" in result
        assert "getDeployedLzaVersion" in result["hint"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("os.listdir")
    async def test_version_directory_not_found_with_available_versions(
        self, mock_listdir, mock_isdir, mock_exists
    ):
        """Test error message includes available versions."""
        ctx = AsyncMock()

        def exists_side_effect(path):
            # Only /app/json-schemas exists, not the version directory
            return path == "/app/json-schemas"

        def isdir_side_effect(path):
            # Mark directories as directories
            if path == "/app/json-schemas":
                return True
            if "v1.12.0" in path or "v1.13.0" in path or "v1.14.0" in path:
                return True
            return False

        mock_exists.side_effect = exists_side_effect
        mock_isdir.side_effect = isdir_side_effect
        mock_listdir.return_value = ["v1.12.0", "v1.13.0", "v1.14.0"]

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.99.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "available_versions" in result
        assert "v1.12.0" in result["available_versions"]
        assert "v1.13.0" in result["available_versions"]

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_combined_json_not_found(self, mock_exists):
        """Test error when combined.json doesn't exist but version directory does."""
        ctx = AsyncMock()

        def exists_side_effect(path):
            if "v1.12.0" in path and path.endswith("v1.12.0"):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Combined schema file not found" in result["error"]
        assert "combined.json" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"invalid json": }',
    )
    async def test_invalid_json_in_combined_file(self, mock_file, mock_exists):
        """Test error when combined.json contains invalid JSON."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Failed to load combined schema file" in result["error"]
        assert "Error loading combined schema file" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    async def test_permission_error_reading_file(self, mock_file, mock_exists):
        """Test error when permission denied reading combined.json."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Failed to load combined schema file" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"other-schema.json": {"type": "object"}}',
    )
    async def test_schema_not_found_in_combined_file(self, mock_file, mock_exists):
        """Test error when requested schema not in combined.json."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="missing-schema.json"
        )

        assert result["success"] is False
        assert "Schema not found" in result["error"]
        assert "missing-schema.json" in result["error"]
        assert "available_schemas_sample" in result
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"schema1.json": {}, "schema2.json": {}, "schema3.json": {}}',
    )
    async def test_schema_not_found_shows_sample(self, mock_file, mock_exists):
        """Test that available schemas sample is provided when schema not found."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="missing.json"
        )

        assert result["success"] is False
        assert "available_schemas_sample" in result
        assert len(result["available_schemas_sample"]) <= 5
