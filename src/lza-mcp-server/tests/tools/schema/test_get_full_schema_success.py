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

"""Unit tests for get_full_schema success scenarios."""

import pytest
from unittest.mock import AsyncMock, patch, mock_open
import json

from awslabs.lza_mcp_server.tools.schema.get_full_schema import tool_get_full_schema


class TestGetFullSchemaSuccess:
    """Test successful execution paths for get_full_schema."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_full_schema_success(self, mock_file, mock_exists):
        """Test successfully retrieving a full schema."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        assert result["success"] is True
        assert result["lza_version"] == "v1.12.0"
        assert result["schema_path"] == "test-schema.json"
        assert "schema" in result
        assert result["schema"]["type"] == "object"
        ctx.info.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_schema_with_metadata(self, mock_file, mock_exists):
        """Test retrieving schema with metadata included."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "_metadata": {"version": "1.0", "description": "Test schema"},
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            include_metadata=True,
        )

        assert result["success"] is True
        assert "metadata" in result
        assert result["metadata"]["version"] == "1.0"
        assert "_metadata" not in result["schema"]

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_schema_without_metadata(self, mock_file, mock_exists):
        """Test retrieving schema without metadata."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "_metadata": {"version": "1.0"},
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            include_metadata=False,
        )

        assert result["success"] is True
        assert "metadata" not in result
        assert "schema" in result

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_specific_property_success(self, mock_file, mock_exists):
        """Test successfully retrieving a specific property."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "minLength": 1}},
                    }
                },
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="user.name",
        )

        assert result["success"] is True
        assert result["property_path"] == "user.name"
        assert result["property"]["type"] == "string"
        assert result["property"]["minLength"] == 1

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_nested_property_success(self, mock_file, mock_exists):
        """Test retrieving a deeply nested property."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "properties": {
                    "level1": {
                        "properties": {
                            "level2": {"properties": {"level3": {"type": "string"}}}
                        }
                    }
                }
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="level1.level2.level3",
        )

        assert result["success"] is True
        assert result["property"]["type"] == "string"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_property_with_metadata(self, mock_file, mock_exists):
        """Test retrieving property with schema metadata."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "properties": {"name": {"type": "string"}},
                "_metadata": {"version": "1.0"},
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="name",
            include_metadata=True,
        )

        assert result["success"] is True
        assert "schema_metadata" in result
        assert result["schema_metadata"]["version"] == "1.0"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_retrieve_array_property(self, mock_file, mock_exists):
        """Test retrieving property with array notation."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {
            "test-schema.json": {
                "properties": {"items": {"type": "array", "items": {"type": "string"}}}
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="items",
        )

        assert result["success"] is True
        assert result["property"]["type"] == "array"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_context_logging_full_schema(self, mock_file, mock_exists):
        """Test that context logging is called for full schema retrieval."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": {"type": "object"}}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="test-schema.json"
        )

        # Verify info logging was called
        assert ctx.info.call_count >= 2
        info_calls = [call[0][0] for call in ctx.info.call_args_list]
        assert any("Retrieving schema" in call for call in info_calls)
        assert any("Loaded combined schema" in call for call in info_calls)

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    async def test_context_logging_property_path(self, mock_file, mock_exists):
        """Test that context logging includes property path when specified."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        test_schema = {"test-schema.json": {"properties": {"name": {"type": "string"}}}}
        mock_file.return_value.read.return_value = json.dumps(test_schema)

        await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="name",
        )

        info_calls = [call[0][0] for call in ctx.info.call_args_list]
        assert any("property path" in call for call in info_calls)
