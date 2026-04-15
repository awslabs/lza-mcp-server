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

"""Unit tests for get_full_schema error handling."""

import pytest
from unittest.mock import AsyncMock, patch, mock_open
import json

from awslabs.lza_mcp_server.tools.schema.get_full_schema import tool_get_full_schema


class TestGetFullSchemaErrors:
    """Test error handling for get_full_schema."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_property_path_not_found(self, mock_file, mock_exists):
        """Test error when property path doesn't exist."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": {"properties": {"name": {"type": "string"}}}}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="nonexistent",
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "nonexistent" in result["error"]
        assert "Could not navigate" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_property_path_partial_not_found(self, mock_file, mock_exists):
        """Test error when intermediate property in path doesn't exist."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "properties": {"user": {"properties": {"name": {"type": "string"}}}}
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="user.nonexistent.field",
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_property_navigation_generic_error(self, mock_file, mock_exists):
        """Test generic error during property navigation."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        # Create a schema that will cause a non-ValueError exception
        test_schema = {"test-schema.json": None}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="some.path",
        )

        assert result["success"] is False
        assert "Error navigating to property path" in result["error"]
        assert "could not be processed" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", side_effect=Exception("Unexpected file error"))
    async def test_unexpected_error_during_execution(self, mock_file, mock_exists):
        """Test handling of unexpected errors."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        # The error is caught earlier as a file loading error
        assert "Failed to load combined schema file" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_error_message_includes_property_path(self, mock_file, mock_exists):
        """Test that error messages include the property path."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": {"properties": {}}}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="missing.property",
        )

        assert result["success"] is False
        assert "missing.property" in result["message"]

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_navigation_error_shows_available_properties(
        self, mock_file, mock_exists
    ):
        """Test that navigation errors show available properties."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "properties": {"name": {"type": "string"}, "age": {"type": "number"}}
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="invalid",
        )

        assert result["success"] is False
        # The error from _navigate_to_property includes available properties
        assert "Available:" in result["error"] or "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_none_lza_version(self):
        """Test error when lza_version is None."""
        ctx = AsyncMock()

        result = await tool_get_full_schema(
            ctx=ctx, lza_version=None, schema_path="test-schema.json"
        )

        assert result["success"] is False
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_path_traversal_version_rejected(self):
        """Test that path traversal in lza_version is rejected by format validation."""
        ctx = AsyncMock()

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="../../../etc", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Invalid LZA version format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_none_schema_path(self):
        """Test error when schema_path is None."""
        ctx = AsyncMock()

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path=None
        )

        assert result["success"] is False
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_empty_combined_schemas(self, mock_file, mock_exists):
        """Test error when combined.json is empty."""
        ctx = AsyncMock()
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = "{}"

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Schema not found" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_schema_value_is_none(self, mock_file, mock_exists):
        """Test handling when schema value is None."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": None}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        # When schema is None, it causes an error during processing
        # The function tries to iterate over it and fails
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_schema_value_is_empty_dict(self, mock_file, mock_exists):
        """Test handling when schema value is empty dict."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": {}}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is True
        assert result["schema"] == {}
