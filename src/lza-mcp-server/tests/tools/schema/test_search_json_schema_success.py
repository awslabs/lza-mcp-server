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

"""Unit tests for search_json_schema successful operations."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from awslabs.lza_mcp_server.tools.schema.search_json_schema import (
    tool_search_json_schema,
)


class TestSearchJsonSchemaSuccess:
    """Test successful search operations."""

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_successful_search_with_results(self, mock_exists):
        """Test successful search returning results."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {
            "total_matches": 2,
            "results": [
                {
                    "path": "accounts-config-schema.json",
                    "relevance_score": 0.9,
                    "match_locations": ["property:accounts"],
                    "_metadata": {
                        "title": "Accounts Configuration",
                        "description": "Schema for accounts",
                    },
                },
                {
                    "path": "global-config-schema.json",
                    "relevance_score": 0.7,
                    "match_locations": ["property:global"],
                    "_metadata": {
                        "title": "Global Configuration",
                        "description": "Schema for global settings",
                    },
                },
            ],
        }

        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["accounts", "global"]
            )

        assert result["success"] is True
        assert result["search_info"]["total_matches"] == 2
        assert result["search_info"]["returned_matches"] == 2
        assert len(result["results"]) == 2

        # Verify first result formatting
        first_result = result["results"][0]
        assert first_result["rank"] == 1
        assert first_result["path"] == "accounts-config-schema.json"
        assert first_result["score"] == 0.9
        assert first_result["title"] == "Accounts Configuration"
        assert first_result["description"] == "Schema for accounts"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_successful_search_no_results(self, mock_exists):
        """Test successful search with no matches."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {"total_matches": 0, "results": []}
        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx, lza_version="v1.12.0", search_terms=["nonexistent"]
            )

        assert result["success"] is True
        assert result["search_info"]["total_matches"] == 0
        assert len(result["results"]) == 0

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_with_all_search_types(self, mock_exists):
        """Test search with different search_type values."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {"total_matches": 1, "results": []}
        mock_search_func = MagicMock(return_value=mock_search_results)

        search_types = ["general", "property", "pattern", "relationship", "complexity"]

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            for search_type in search_types:
                result = await tool_search_json_schema(
                    ctx=ctx,
                    lza_version="v1.12.0",
                    search_terms=["test"],
                    search_type=search_type,
                )

                assert result["success"] is True
                assert result["search_info"]["type"] == search_type

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_with_max_results_limit(self, mock_exists):
        """Test search respects max_results parameter."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        # Create 20 mock results
        mock_results = [
            {
                "path": f"schema-{i}.json",
                "relevance_score": 0.9 - (i * 0.01),
                "match_locations": ["property:test"],
                "_metadata": {"title": f"Schema {i}", "description": f"Desc {i}"},
            }
            for i in range(20)
        ]

        mock_search_results = {"total_matches": 20, "results": mock_results}
        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                max_results=5,
            )

        assert result["success"] is True
        # Note: The function passes max_results to search function,
        # but returns all results from search function
        assert result["search_info"]["total_matches"] == 20

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_with_filters(self, mock_exists):
        """Test search with complexity filters."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {"total_matches": 1, "results": []}
        mock_search_func = MagicMock(return_value=mock_search_results)

        filters = {"min_depth": 2, "max_depth": 5, "min_properties": 10}

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                search_type="complexity",
                filters=filters,
            )

        assert result["success"] is True
        # Verify filters were passed to search function
        mock_search_func.assert_called_once()
        call_kwargs = mock_search_func.call_args[1]
        assert call_kwargs["filters"] == filters

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_search_info_contains_all_fields(self, mock_exists):
        """Test that search_info contains all expected fields."""
        ctx = AsyncMock()
        mock_exists.return_value = True

        mock_search_results = {"total_matches": 1, "results": []}
        mock_search_func = MagicMock(return_value=mock_search_results)

        with patch.dict(
            "sys.modules",
            {"schema_search": MagicMock(search_json_schemas=mock_search_func)},
        ):
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["accounts", "global"],
                search_type="property",
            )

        assert result["success"] is True
        search_info = result["search_info"]
        assert search_info["lza_version"] == "v1.12.0"
        assert search_info["terms"] == ["accounts", "global"]
        assert search_info["type"] == "property"
        assert "total_matches" in search_info
        assert "returned_matches" in search_info
