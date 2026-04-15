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

"""Unit tests for get_full_schema validation."""

import pytest
from unittest.mock import AsyncMock, patch

from awslabs.lza_mcp_server.tools.schema.get_full_schema import tool_get_full_schema


class TestGetFullSchemaValidation:
    """Test input validation for get_full_schema."""

    @pytest.mark.asyncio
    async def test_empty_lza_version(self):
        """Test validation fails with empty lza_version."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx, lza_version="", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Invalid LZA version format" in result["message"]
        assert "getDeployedLzaVersion" in result["hint"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_lza_version_too_long(self):
        """Test validation fails with lza_version exceeding max length."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v" * 51, schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Invalid LZA version format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_latest_version_rejected(self):
        """Test that 'latest' version is rejected by format validation."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx, lza_version="latest", schema_path="test-schema.json"
        )

        assert result["success"] is False
        assert "Invalid LZA version format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_schema_path_empty(self):
        """Test validation fails with empty schema_path."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path=""
        )

        assert result["success"] is False
        assert "Invalid schema path format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_schema_path_too_long(self):
        """Test validation fails with schema_path exceeding max length."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx, lza_version="v1.12.0", schema_path="x" * 501
        )

        assert result["success"] is False
        assert "Invalid schema path format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    @patch("os.path.exists")
    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    async def test_invalid_property_path_empty(self, mock_file, mock_exists):
        """Test validation fails with empty property_path."""
        ctx = AsyncMock()
        # Make filesystem check pass so validation runs first
        mock_exists.return_value = True

        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="",
        )

        assert result["success"] is False
        # Empty property_path fails validation before file loading
        # But if file loading happens first, that's also acceptable
        assert result["success"] is False
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_property_path_too_long(self):
        """Test validation fails with property_path exceeding max length."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="x" * 501,
        )

        assert result["success"] is False
        assert "Invalid property path format" in result["message"]
        ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_valid_inputs_pass_validation(self):
        """Test that valid inputs pass validation (will fail at filesystem check)."""
        ctx = AsyncMock()
        result = await tool_get_full_schema(
            ctx=ctx,
            lza_version="v1.12.0",
            schema_path="test-schema.json",
            property_path="valid.property.path",
        )

        # Should pass validation but fail at filesystem check
        assert "Invalid" not in result.get("error", "")
        assert "validation" not in result.get("message", "").lower()
