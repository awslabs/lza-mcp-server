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

"""Unit tests for search_json_schema error handling."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from awslabs.lza_mcp_server.tools.schema.search_json_schema import (
    tool_search_json_schema,
)


class TestSearchJsonSchemaErrors:
    """Test error handling for search_json_schema."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_function_raises_exception(self, mock_exists):
        """Test handling when search function raises an exception."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_func = MagicMock(side_effect=Exception("Search operation failed"))

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
            )

        assert result["success"] is False
        assert "Search failed" in result["error"]
        assert "Search operation failed" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_function_returns_invalid_format(self, mock_exists):
        """Test handling when search function returns unexpected format."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        # Return invalid format (missing required keys)
        mock_search_func = MagicMock(return_value={"invalid": "format"})

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
            )

        # Should handle gracefully and return success with empty results
        assert result["success"] is True
        assert result["search_info"]["total_matches"] == 0
        assert len(result["results"]) == 0

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_main_try_block(self):
        """Test handling of unexpected exceptions in main try block."""
        ctx = AsyncMock()

        # Cause an exception by passing invalid type for lza_version
        with patch(
            "awslabs.lza_mcp_server.tools.schema.search_json_schema.validate_string_input",
            side_effect=Exception("Unexpected validation error"),
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["test"]
            )

        assert result["success"] is False
        assert "Error searching JSON schemas" in result["error"]
        assert "unexpected error occurred" in result["message"].lower()
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_with_none_filters(self, mock_exists):
        """Test that None filters are handled correctly."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {"total_matches": 0, "results": []}
        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                filters=None,
            )

        assert result["success"] is True
        # Verify empty dict was passed to search function
        mock_search_func.assert_called_once()
        call_kwargs = mock_search_func.call_args[1]
        assert call_kwargs["filters"] == {}

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_result_missing_metadata(self, mock_exists):
        """Test handling when result is missing _metadata field."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    # Missing _metadata field
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
                include_metadata=True,
            )

        assert result["success"] is True
        # Should handle missing metadata gracefully
        first_result = result["results"][0]
        assert "path" in first_result
        assert "score" in first_result

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_result_missing_path(self, mock_exists):
        """Test handling when result is missing path field."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    # Missing path field
                    "relevance_score": 0.9,
                    "match_locations": ["property:test"],
                    "_metadata": {"title": "Test", "description": "Test"},
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
        # Should use "unknown" as default
        assert first_result["path"] == "unknown"
        assert first_result["schema_ref"] == "unknown"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_result_missing_relevance_score(self, mock_exists):
        """Test handling when result is missing relevance_score field."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 1,
            "results": [
                {
                    "path": "test-schema.json",
                    # Missing relevance_score
                    "match_locations": ["property:test"],
                    "_metadata": {"title": "Test", "description": "Test"},
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
        # Should use 0 as default
        assert first_result["score"] == 0

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_metadata_missing_title_and_description(self, mock_exists):
        """Test handling when metadata is missing title and description."""
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
                        # Missing title and description
                        "statistics": {"depth": 3}
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
                include_metadata=True,
            )

        assert result["success"] is True
        first_result = result["results"][0]
        # Should use defaults
        assert first_result["title"] == "Untitled Schema"
        assert first_result["description"] == "No description"
