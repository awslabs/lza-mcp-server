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

"""Unit tests for search_json_schema result formatting."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from awslabs.lza_mcp_server.tools.schema.search_json_schema import (
    tool_search_json_schema,
)


class TestSearchJsonSchemaFormatting:
    """Test result formatting at different levels."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_minimal_format_level(self, mock_exists):
        """Test formatting with minimal detail level."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                        "statistics": {"depth": 3, "properties": 10},
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level="minimal",
                include_metadata=True,
            )

        assert result["success"] is True
        first_result = result["results"][0]
        assert "title" in first_result
        assert "description" in first_result
        # Statistics should not be included in minimal format
        assert "statistics" not in first_result

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_standard_format_level(self, mock_exists):
        """Test formatting with standard detail level."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                        "statistics": {"depth": 3, "properties": 10},
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level="standard",
                include_metadata=True,
            )

        assert result["success"] is True
        first_result = result["results"][0]
        assert "title" in first_result
        assert "description" in first_result
        # Statistics should not be included in standard format
        assert "statistics" not in first_result

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_detailed_format_level_with_statistics(self, mock_exists):
        """Test formatting with detailed level includes statistics."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                        "statistics": {"depth": 3, "properties": 10},
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level="detailed",
                include_metadata=True,
            )

        assert result["success"] is True
        first_result = result["results"][0]
        assert "title" in first_result
        assert "description" in first_result
        assert "statistics" in first_result
        assert first_result["statistics"]["depth"] == 3
        assert first_result["statistics"]["properties"] == 10

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_include_schema_only_with_detailed_format(self, mock_exists):
        """Test that schema is only included with detailed format level."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                    },
                    "schema": mock_schema,
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            # Test with detailed format - should include schema
            result_detailed = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level="detailed",
                include_schema=True,
            )

            assert result_detailed["success"] is True
            assert "schema" in result_detailed["results"][0]
            assert result_detailed["results"][0]["schema"] == mock_schema

            # Verify search function was called with include_schema=True
            mock_search_func.assert_called_once()
            call_kwargs = mock_search_func.call_args[1]
            assert call_kwargs["include_schema"] is True

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_include_schema_false_with_standard_format(self, mock_exists):
        """Test that schema is not included with standard format even if requested."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level="standard",
                include_schema=True,
            )

            assert result["success"] is True
            # Schema should not be in results with standard format
            assert "schema" not in result["results"][0]

            # Verify search function was called with include_schema=False
            mock_search_func.assert_called_once()
            call_kwargs = mock_search_func.call_args[1]
            assert call_kwargs["include_schema"] is False

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_metadata_excluded_when_disabled(self, mock_exists):
        """Test that metadata is excluded when include_metadata=False."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                include_metadata=False,
            )

        assert result["success"] is True
        first_result = result["results"][0]
        # Metadata fields should not be present
        assert "title" not in first_result
        assert "description" not in first_result
        # But basic fields should still be present
        assert "path" in first_result
        assert "score" in first_result

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_result_ranking(self, mock_exists):
        """Test that results are properly ranked."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 3,
            "results": [
                {
                    "path": "schema-1.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {"title": "Schema 1", "description": "First"},
                },
                {
                    "path": "schema-2.json",
                    "relevance_score": 0.7,
                    "match_locations": ["property:test"],
                    "_metadata": {"title": "Schema 2", "description": "Second"},
                },
                {
                    "path": "schema-3.json",
                    "relevance_score": 0.5,
                    "match_locations": ["property:test"],
                    "_metadata": {"title": "Schema 3", "description": "Third"},
                },
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
            )

        assert result["success"] is True
        assert len(result["results"]) == 3
        # Verify ranking
        assert result["results"][0]["rank"] == 1
        assert result["results"][1]["rank"] == 2
        assert result["results"][2]["rank"] == 3

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_schema_ref_field_present(self, mock_exists):
        """Test that schema_ref field is always present in results."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {
                        "title": "Test Schema",
                        "description": "Test description",
                    },
                }
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
            )

        assert result["success"] is True
        first_result = result["results"][0]
        assert "schema_ref" in first_result
        assert first_result["schema_ref"] == "test-schema.json"
