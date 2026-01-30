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

"""Unit tests for search_json_schema validation."""

import pytest
from unittest.mock import AsyncMock

from awslabs.lza_mcp_server.tools.schema.search_json_schema import (
    tool_search_json_schema,
)


class TestSearchJsonSchemaValidation:
    """Test input validation for search_json_schema."""

    @pytest.mark.asyncio
    async def test_empty_lza_version(self):
        """Test validation fails with empty lza_version."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="", search_terms=["test"]
        )

        assert result["success"] is False
        # Empty string fails validation before the explicit check
        assert "Invalid LZA version format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_lza_version_too_long(self):
        """Test validation fails with lza_version exceeding max length."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v" * 51, search_terms=["test"]
        )

        assert result["success"] is False
        assert "Invalid LZA version format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_latest_version_rejected(self):
        """Test that 'latest' version is explicitly rejected."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="latest", search_terms=["test"]
        )

        assert result["success"] is False
        assert "latest" in result["error"].lower()
        assert "required_action" in result
        assert "getDeployedLzaVersion" in result["required_action"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_empty_search_terms(self):
        """Test validation fails with empty search_terms."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=[]
        )

        assert result["success"] is False
        assert "search_terms must be a non-empty list" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_non_list_search_terms(self):
        """Test validation fails when search_terms is not a list."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms="not_a_list"
        )

        assert result["success"] is False
        assert "search_terms must be a non-empty list" in result["error"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_search_term_too_long(self):
        """Test validation fails with search term exceeding max length."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=["x" * 201]
        )

        assert result["success"] is False
        assert "Invalid search term format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_search_term_empty_string(self):
        """Test validation fails with empty string in search_terms."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=[""]
        )

        assert result["success"] is False
        assert "Invalid search term format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_max_results_too_low(self):
        """Test validation fails with max_results below minimum."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=["test"], max_results=0
        )

        assert result["success"] is False
        assert "max_results must be between 1 and 100" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_max_results_too_high(self):
        """Test validation fails with max_results above maximum."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx, lza_version="v1.12.0", search_terms=["test"], max_results=101
        )

        assert result["success"] is False
        assert "max_results must be between 1 and 100" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_search_type(self):
        """Test validation fails with invalid search_type."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            search_terms=["test"],
            search_type="invalid_type",
        )

        assert result["success"] is False
        assert "Invalid search_type" in result["error"]
        assert "general" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_valid_search_types(self):
        """Test all valid search_types are accepted (validation only)."""
        ctx = AsyncMock()
        valid_types = ["general", "property", "pattern", "relationship", "complexity"]

        for search_type in valid_types:
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                search_type=search_type,
            )
            # Will fail at file system check, but validation should pass
            assert "Invalid search_type" not in result.get("error", "")

    @pytest.mark.asyncio
    async def test_invalid_format_level(self):
        """Test validation fails with invalid format_level."""
        ctx = AsyncMock()
        result = await tool_search_json_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            search_terms=["test"],
            format_level="invalid_level",
        )

        assert result["success"] is False
        assert "Invalid format_level" in result["error"]
        assert "minimal" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_valid_format_levels(self):
        """Test all valid format_levels are accepted (validation only)."""
        ctx = AsyncMock()
        valid_levels = ["minimal", "standard", "detailed"]

        for format_level in valid_levels:
            result = await tool_search_json_schema(
                ctx=ctx,
                lza_version="v1.12.0",
                search_terms=["test"],
                format_level=format_level,
            )
            # Will fail at file system check, but validation should pass
            assert "Invalid format_level" not in result.get("error", "")
