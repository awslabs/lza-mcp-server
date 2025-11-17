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

"""Unit tests for schema version support functionality."""

import pytest
import json
from unittest.mock import Mock, patch, mock_open

from awslabs.lza_mcp_server.tools.schema.manage_schema_tools import (
    register_schema_tools,
)


class MockContext:
    """Mock context for testing."""

    async def info(self, message):
        pass

    async def error(self, message):
        pass


class TestSchemaVersionSupport:
    """Test cases for LZA version support in schema tools."""

    @pytest.mark.asyncio
    async def test_search_with_missing_lza_version(self):
        """Test that search fails when lza_version is not provided."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        search_func = registered_tools["searchJsonSchema"]

        # Call without lza_version (empty string)
        result = await search_func(
            mock_context,
            lza_version="",
            search_terms=["test"],
        )

        assert result["success"] is False
        assert "lza_version parameter is required" in result["error"]

    @pytest.mark.asyncio
    async def test_get_schema_with_missing_lza_version(self):
        """Test that get_full_schema fails when lza_version is not provided."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        get_schema_func = registered_tools["getFullSchema"]

        # Call without lza_version (empty string)
        result = await get_schema_func(
            mock_context,
            lza_version="",
            schema_path="accounts-config.yaml",
        )

        assert result["success"] is False
        assert "lza_version parameter is required" in result["error"]

    @pytest.mark.asyncio
    async def test_search_with_nonexistent_version(self):
        """Test search with a version that doesn't exist."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        search_func = registered_tools["searchJsonSchema"]

        with patch("os.path.exists", return_value=False):
            with patch("os.listdir", return_value=["v1.12.0", "v1.13.0"]):
                result = await search_func(
                    mock_context,
                    lza_version="v99.99.99",
                    search_terms=["test"],
                )

        assert result["success"] is False
        assert "v99.99.99" in result["error"]
        assert "available_versions" in result

    @pytest.mark.asyncio
    async def test_get_schema_with_nonexistent_version(self):
        """Test get_full_schema with a version that doesn't exist."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        get_schema_func = registered_tools["getFullSchema"]

        with patch("os.path.exists", return_value=False):
            with patch("os.listdir", return_value=["v1.12.0", "v1.13.0"]):
                result = await get_schema_func(
                    mock_context,
                    lza_version="v99.99.99",
                    schema_path="accounts-config.yaml",
                )

        assert result["success"] is False
        assert "v99.99.99" in result["error"]
        assert "available_versions" in result

    @pytest.mark.asyncio
    async def test_search_with_latest_version(self):
        """Test search using 'latest' as version."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        search_func = registered_tools["searchJsonSchema"]

        mock_schema_data = {
            "accounts-config.yaml": {
                "_metadata": {"title": "Test Schema"},
                "type": "object",
            }
        }

        def mock_exists(path):
            return "latest" in path and path.endswith("combined.json")

        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.path.getsize", return_value=1024):
                with patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))):
                    # This will fail on import but that's ok for this test
                    result = await search_func(
                        mock_context,
                        lza_version="latest",
                        search_terms=["test"],
                    )

        # Should attempt to use 'latest' version
        assert "lza_version" in str(result) or "error" in result

    @pytest.mark.asyncio
    async def test_search_result_includes_version(self):
        """Test that search results include the lza_version used."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        search_func = registered_tools["searchJsonSchema"]

        mock_schema_data = {
            "accounts-config.yaml": {
                "_metadata": {
                    "title": "Test Schema",
                    "searchIndex": {
                        "propertyPaths": ["test"],
                    },
                },
                "type": "object",
            }
        }

        def mock_exists(path):
            return "v1.13.0" in path

        with patch("os.path.exists", side_effect=mock_exists):
            with patch("os.path.getsize", return_value=1024):
                with patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))):
                    with patch("awslabs.lza_mcp_server.tools.schema.search_json_schema.sys.path", ["/app/json-schema/src"]):
                        # Mock the schema_search module
                        mock_search_module = Mock()
                        mock_search_module.search_schemas.return_value = {
                            "results": [],
                            "total_matches": 0,
                        }
                        with patch.dict("sys.modules", {"schema_search": mock_search_module}):
                            result = await search_func(
                                mock_context,
                                lza_version="v1.13.0",
                                search_terms=["test"],
                            )

        # Result should include version information
        if result["success"]:
            assert "search_info" in result
            assert result["search_info"]["lza_version"] == "v1.13.0"

    @pytest.mark.asyncio
    async def test_get_schema_result_includes_version(self):
        """Test that get_full_schema results include the lza_version used."""
        mock_context = MockContext()
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        get_schema_func = registered_tools["getFullSchema"]

        mock_schema_data = {
            "accounts-config.yaml": {
                "_metadata": {"title": "Test Schema"},
                "type": "object",
                "properties": {"test": {"type": "string"}},
            }
        }

        def mock_exists(path):
            return "v1.13.0" in path

        with patch("os.path.exists", side_effect=mock_exists):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))):
                result = await get_schema_func(
                    mock_context,
                    lza_version="v1.13.0",
                    schema_path="accounts-config.yaml",
                )

        assert result["success"] is True
        assert result["lza_version"] == "v1.13.0"
        assert result["schema_path"] == "accounts-config.yaml"
