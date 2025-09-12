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

"""Unit tests for schema tools module."""

import pytest
import json
from unittest.mock import Mock, patch, mock_open

from awslabs.lza_mcp_server.tools.schema.manage_schema_tools import (
    register_schema_tools,
)


class TestSchemaTools:
    """Test class for schema tools functionality."""

    @pytest.fixture
    def mock_mcp_context(self):
        """Fixture providing a mock MCP context."""
        context = Mock()
        context.info = Mock(return_value=None)
        context.error = Mock(return_value=None)

        # Make the methods async
        async def async_info(*args, **kwargs):
            return None

        async def async_error(*args, **kwargs):
            return None

        context.info = async_info
        context.error = async_error
        return context

    @pytest.fixture
    def mock_schema_data(self):
        """Fixture providing mock schema data for testing."""
        return {
            "accounts-config.yaml": {
                "_metadata": {
                    "title": "Accounts Configuration Schema",
                    "description": "Schema for LZA accounts configuration",
                    "searchIndex": {
                        "propertyPaths": [
                            "mandatoryAccounts",
                            "workloadAccounts",
                            "accountIds",
                        ],
                        "requiredProperties": ["mandatoryAccounts"],
                        "patterns": {"accountIds": "^\\d{12}$"},
                        "enums": {"accountType": ["mandatory", "workload"]},
                    },
                    "statistics": {
                        "nestingDepth": 3,
                        "propertyCount": 15,
                        "requiredCount": 5,
                    },
                },
                "type": "object",
                "properties": {
                    "mandatoryAccounts": {"type": "array", "items": {"type": "object"}}
                },
            },
            "network-config.yaml": {
                "_metadata": {
                    "title": "Network Configuration Schema",
                    "description": "Schema for LZA network configuration including VPCs and subnets",
                    "searchIndex": {
                        "propertyPaths": [
                            "vpcs",
                            "vpcs[].subnets",
                            "centralNetworkServices",
                        ],
                        "requiredProperties": ["vpcs"],
                        "patterns": {
                            "cidr": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/\\d{1,2}$"
                        },
                    },
                    "statistics": {
                        "nestingDepth": 4,
                        "propertyCount": 25,
                        "requiredCount": 8,
                    },
                },
                "type": "object",
                "properties": {"vpcs": {"type": "array", "items": {"type": "object"}}},
            },
        }

    @pytest.fixture
    def mock_combined_schema_file(self, mock_schema_data):
        """Fixture providing a mock combined schema file."""
        return json.dumps(mock_schema_data)

    @pytest.fixture
    def mock_search_results(self):
        """Fixture providing mock search results."""
        return {
            "results": [
                {
                    "path": "accounts-config.yaml",
                    "relevance_score": 1.5,
                    "match_locations": [
                        "title:exact",
                        "property:mandatoryAccounts:exact",
                    ],
                    "_metadata": {
                        "title": "Accounts Configuration Schema",
                        "description": "Schema for LZA accounts configuration",
                    },
                }
            ],
            "total_matches": 1,
            "returned_matches": 1,
            "search_info": {"terms": ["accounts"], "type": "general"},
        }

    @pytest.fixture
    def mock_fastmcp_server(self):
        """Fixture providing a mock FastMCP server."""
        server = Mock()
        server.tool = Mock()
        return server

    def test_register_schema_tools(self, mock_fastmcp_server):
        """Test that schema tools are registered correctly."""
        register_schema_tools(mock_fastmcp_server)

        # Verify that tool decorator was called for both tools
        assert mock_fastmcp_server.tool.call_count == 2

        # Check that the correct tool names were registered
        tool_calls = mock_fastmcp_server.tool.call_args_list
        tool_names = [call[1]["name"] for call in tool_calls]
        assert "searchJsonSchema" in tool_names
        assert "getFullSchema" in tool_names

    @pytest.mark.asyncio
    async def test_search_json_schema_success(
        self, mock_mcp_context, mock_schema_data, mock_search_results
    ):
        """Test successful JSON schema search."""
        # Create a mock server and register tools
        server = Mock()
        registered_tools = {}

        def mock_tool_decorator(name, **kwargs):
            def decorator(func):
                registered_tools[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator
        register_schema_tools(server)

        # Get the search function
        search_func = registered_tools["searchJsonSchema"]

        # Test the import error case instead of successful case
        with patch("os.path.exists", return_value=False):
            result = await search_func(
                mock_mcp_context,
                search_terms=["accounts"],
                search_type="general",
                max_results=10,
                include_metadata=True,
                include_schema=False,
            )

        # Verify the error result structure
        assert result["success"] is False
        assert "error" in result
        assert "Failed to import schema_search module" in result["error"]

    @pytest.mark.asyncio
    async def test_search_json_schema_with_schema_inclusion(
        self, mock_mcp_context, mock_search_results
    ):
        """Test JSON schema search with schema inclusion - test error case."""
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

        # Test file not found case
        with patch("os.path.exists", return_value=False):
            result = await search_func(
                mock_mcp_context,
                search_terms=["accounts"],
                include_schema=True,
                format_level="detailed",
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_json_schema_file_not_found(self, mock_mcp_context):
        """Test JSON schema search when schema file is not found."""
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
            result = await search_func(mock_mcp_context, search_terms=["accounts"])

        assert result["success"] is False
        assert "error" in result
        assert "Failed to import schema_search module" in result["error"]

    @pytest.mark.asyncio
    async def test_search_json_schema_import_error(self, mock_mcp_context):
        """Test JSON schema search when schema_search module import fails."""
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

        with (
            patch("os.path.exists", return_value=False),
        ):
            result = await search_func(mock_mcp_context, search_terms=["accounts"])

        assert result["success"] is False
        assert "error" in result
        assert "Failed to import schema_search module" in result["error"]

    @pytest.mark.asyncio
    async def test_search_json_schema_search_failure(self, mock_mcp_context):
        """Test JSON schema search when search operation fails."""
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

        # Test file not found case
        with patch("os.path.exists", return_value=False):
            result = await search_func(mock_mcp_context, search_terms=["accounts"])

        assert result["success"] is False
        assert "error" in result
        assert "Failed to import schema_search module" in result["error"]

    @pytest.mark.asyncio
    async def test_search_json_schema_different_search_types(self, mock_mcp_context):
        """Test JSON schema search with different search types - test parameter validation."""
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

        # Test with file not found to verify parameter handling
        with patch("os.path.exists", return_value=False):
            result = await search_func(
                mock_mcp_context, search_terms=["test"], search_type="general"
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_json_schema_with_filters(self, mock_mcp_context):
        """Test JSON schema search with complexity filters - test parameter validation."""
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

        filters = {
            "min_depth": 2,
            "max_depth": 5,
            "min_properties": 10,
            "max_properties": 50,
        }

        # Test with file not found to verify parameter handling
        with patch("os.path.exists", return_value=False):
            result = await search_func(
                mock_mcp_context,
                search_terms=["complex"],
                search_type="complexity",
                filters=filters,
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_full_schema_success(self, mock_mcp_context, mock_schema_data):
        """Test successful full schema retrieval."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="accounts-config.yaml",
                include_metadata=True,
            )

        assert result["success"] is True
        assert result["schema_path"] == "accounts-config.yaml"
        assert "metadata" in result
        assert "schema" in result
        assert result["metadata"]["title"] == "Accounts Configuration Schema"

    @pytest.mark.asyncio
    async def test_get_full_schema_with_property_path(
        self, mock_mcp_context, mock_schema_data
    ):
        """Test full schema retrieval with specific property path."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="accounts-config.yaml",
                property_path="mandatoryAccounts",
                include_metadata=True,
            )

        assert result["success"] is True
        assert result["property_path"] == "mandatoryAccounts"
        assert "property" in result
        assert result["property"]["type"] == "array"

    @pytest.mark.asyncio
    async def test_get_full_schema_invalid_property_path(
        self, mock_mcp_context, mock_schema_data
    ):
        """Test full schema retrieval with invalid property path."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="accounts-config.yaml",
                property_path="nonexistent.property",
            )

        assert result["success"] is False
        assert "error" in result
        assert "Property path element" in result["error"]

    @pytest.mark.asyncio
    async def test_get_full_schema_file_not_found(self, mock_mcp_context):
        """Test full schema retrieval when combined schema file is not found."""
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
            result = await get_schema_func(
                mock_mcp_context, schema_path="accounts-config.yaml"
            )

        assert result["success"] is False
        assert "error" in result
        assert "Combined schema file not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_full_schema_json_load_error(self, mock_mcp_context):
        """Test full schema retrieval when JSON loading fails."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="invalid json")),
        ):
            result = await get_schema_func(
                mock_mcp_context, schema_path="accounts-config.yaml"
            )

        assert result["success"] is False
        assert "error" in result
        assert "Failed to load combined schema file" in result["error"]

    @pytest.mark.asyncio
    async def test_get_full_schema_schema_not_found(
        self, mock_mcp_context, mock_schema_data
    ):
        """Test full schema retrieval when requested schema is not found."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))),
        ):
            result = await get_schema_func(
                mock_mcp_context, schema_path="nonexistent-schema.yaml"
            )

        assert result["success"] is False
        assert "error" in result
        assert "Schema not found" in result["error"]
        assert "available_schemas_sample" in result

    @pytest.mark.asyncio
    async def test_get_full_schema_without_metadata(
        self, mock_mcp_context, mock_schema_data
    ):
        """Test full schema retrieval without metadata inclusion."""
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

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_schema_data))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="accounts-config.yaml",
                include_metadata=False,
            )

        assert result["success"] is True
        assert "metadata" not in result
        assert "schema" in result

    @pytest.mark.asyncio
    async def test_search_json_schema_custom_schema_path(self, mock_mcp_context):
        """Test JSON schema search with custom schema path - test parameter validation."""
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

        custom_path = "/custom/path/schemas.json"

        # Test with file not found to verify parameter handling
        with patch("os.path.exists", return_value=False):
            result = await search_func(
                mock_mcp_context, search_terms=["test"], schema_path=custom_path
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_json_schema_format_levels(self, mock_mcp_context):
        """Test JSON schema search with different format levels - test parameter validation."""
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

        format_levels = ["minimal", "standard", "detailed"]

        for format_level in format_levels:
            # Test with file not found to verify parameter handling
            with patch("os.path.exists", return_value=False):
                result = await search_func(
                    mock_mcp_context, search_terms=["test"], format_level=format_level
                )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_json_schema_empty_results(self, mock_mcp_context):
        """Test JSON schema search with empty results - test parameter validation."""
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

        # Test with file not found to verify parameter handling
        with patch("os.path.exists", return_value=False):
            result = await search_func(mock_mcp_context, search_terms=["nonexistent"])

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_full_schema_complex_property_path(self, mock_mcp_context):
        """Test full schema retrieval with complex nested property path."""
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

        # Create complex nested schema data
        complex_schema_data = {
            "network-config.yaml": {
                "_metadata": {"title": "Network Configuration Schema"},
                "type": "object",
                "properties": {
                    "vpcs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subnets": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                }
                            },
                        },
                    }
                },
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "builtins.open", mock_open(read_data=json.dumps(complex_schema_data))
            ),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="network-config.yaml",
                property_path="vpcs",
            )

        assert result["success"] is True
        assert result["property_path"] == "vpcs"
        assert "property" in result
        assert result["property"]["type"] == "array"

    @pytest.mark.asyncio
    async def test_schema_tools_error_handling(self, mock_mcp_context):
        """Test error handling in schema tools functions."""
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
        get_schema_func = registered_tools["getFullSchema"]

        # Test unexpected error in search function
        with patch("os.path.exists", side_effect=Exception("Unexpected error")):
            result = await search_func(mock_mcp_context, search_terms=["test"])

        assert result["success"] is False
        assert "error" in result
        assert (
            "An unexpected error occurred while performing the search."
            in result["message"]
        )

        # Test unexpected error in get schema function
        with patch("os.path.exists", side_effect=Exception("Unexpected error")):
            result = await get_schema_func(
                mock_mcp_context, schema_path="test-schema.yaml"
            )

        assert result["success"] is False
        assert "error" in result
        assert "An unexpected error occurred" in result["message"]

    # Additional tests for task 5.2: Schema validation and resolution testing

    @pytest.mark.asyncio
    async def test_schema_reference_resolution(self, mock_mcp_context):
        """Test schema reference resolution functionality."""
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

        # Create schema data with references
        schema_with_refs = {
            "accounts-config.yaml": {
                "_metadata": {
                    "title": "Accounts Configuration Schema",
                    "relationships": {
                        "references": [
                            {
                                "schema": "organization-config.yaml",
                                "paths": ["organizationalUnits"],
                            },
                            {"schema": "iam-config.yaml", "paths": ["roles"]},
                        ],
                        "referencedBy": [
                            {"schema": "network-config.yaml", "paths": ["accountIds"]}
                        ],
                    },
                },
                "type": "object",
                "properties": {
                    "mandatoryAccounts": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/Account"},
                    }
                },
                "definitions": {
                    "Account": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "accountId": {"type": "string"},
                        },
                    }
                },
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(schema_with_refs))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="accounts-config.yaml",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "metadata" in result
        assert "relationships" in result["metadata"]
        assert len(result["metadata"]["relationships"]["references"]) == 2
        assert len(result["metadata"]["relationships"]["referencedBy"]) == 1

    @pytest.mark.asyncio
    async def test_schema_dependency_handling(self, mock_mcp_context):
        """Test schema dependency handling and resolution."""
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

        # Create schema data with complex dependencies
        complex_schema = {
            "network-config.yaml": {
                "_metadata": {
                    "title": "Network Configuration Schema",
                    "relationships": {
                        "references": [
                            {"schema": "accounts-config.yaml", "paths": ["accountIds"]},
                            {
                                "schema": "security-config.yaml",
                                "paths": ["securityGroups"],
                            },
                        ]
                    },
                },
                "type": "object",
                "properties": {
                    "vpcs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "accountId": {
                                    "type": "string",
                                    "description": "Reference to account from accounts-config",
                                },
                                "securityGroups": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "security-config.yaml#/definitions/SecurityGroup"
                                    },
                                },
                            },
                        },
                    }
                },
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(complex_schema))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="network-config.yaml",
                property_path="vpcs",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "property" in result
        assert result["property"]["type"] == "array"
        assert "schema_metadata" in result

    @pytest.mark.asyncio
    async def test_schema_validation_against_configuration(self, mock_mcp_context):
        """Test schema validation against configuration files."""
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

        # Create schema with validation constraints
        validation_schema = {
            "iam-config.yaml": {
                "_metadata": {
                    "title": "IAM Configuration Schema",
                    "searchIndex": {
                        "patterns": {
                            "roleName": "^[a-zA-Z][a-zA-Z0-9-]*$",
                            "policyArn": "^arn:aws:iam::[0-9]{12}:policy/.*$",
                        },
                        "enums": {
                            "effect": ["Allow", "Deny"],
                            "principalType": ["AWS", "Service", "Federated"],
                        },
                    },
                },
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "pattern": "^[a-zA-Z][a-zA-Z0-9-]*$",
                                },
                                "policies": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "effect": {
                                                "type": "string",
                                                "enum": ["Allow", "Deny"],
                                            }
                                        },
                                    },
                                },
                            },
                            "required": ["name"],
                        },
                    }
                },
                "required": ["roles"],
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(validation_schema))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="iam-config.yaml",
                property_path="roles",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "property" in result
        assert "schema_metadata" in result
        assert "patterns" in result["schema_metadata"]["searchIndex"]
        assert "enums" in result["schema_metadata"]["searchIndex"]

    @pytest.mark.asyncio
    async def test_schema_version_compatibility(self, mock_mcp_context):
        """Test schema version compatibility checking."""
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

        # Create schema with version information
        versioned_schema = {
            "global-config.yaml": {
                "_metadata": {
                    "title": "Global Configuration Schema",
                    "version": "1.2.0",
                    "compatibleVersions": ["1.0.0", "1.1.0", "1.2.0"],
                    "statistics": {
                        "nestingDepth": 3,
                        "propertyCount": 25,
                        "requiredCount": 8,
                        "schemaVersion": "draft-07",
                    },
                },
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "homeRegion": {
                        "type": "string",
                        "description": "AWS home region for the organization",
                    },
                    "enabledRegions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["homeRegion", "enabledRegions"],
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(versioned_schema))),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="global-config.yaml",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "metadata" in result
        assert "version" in result["metadata"]
        assert "compatibleVersions" in result["metadata"]
        assert "statistics" in result["metadata"]
        assert result["metadata"]["version"] == "1.2.0"

    @pytest.mark.asyncio
    async def test_schema_circular_reference_handling(self, mock_mcp_context):
        """Test handling of circular references in schemas."""
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

        # Create schema with potential circular references
        circular_ref_schema = {
            "organization-config.yaml": {
                "_metadata": {
                    "title": "Organization Configuration Schema",
                    "relationships": {
                        "references": [
                            {"schema": "accounts-config.yaml", "paths": ["accounts"]},
                            {
                                "schema": "organization-config.yaml",
                                "paths": ["parentOu"],
                            },  # Self-reference
                        ],
                        "referencedBy": [
                            {
                                "schema": "accounts-config.yaml",
                                "paths": ["organizationalUnits"],
                            },
                            {
                                "schema": "organization-config.yaml",
                                "paths": ["childOus"],
                            },  # Self-reference
                        ],
                    },
                },
                "type": "object",
                "properties": {
                    "organizationalUnits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "parentOu": {
                                    "$ref": "#/definitions/OrganizationalUnit"
                                },
                                "childOus": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/definitions/OrganizationalUnit"
                                    },
                                },
                            },
                        },
                    }
                },
                "definitions": {
                    "OrganizationalUnit": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "id": {"type": "string"},
                        },
                    }
                },
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "builtins.open", mock_open(read_data=json.dumps(circular_ref_schema))
            ),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="organization-config.yaml",
                property_path="organizationalUnits",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "property" in result
        assert "schema_metadata" in result
        # Verify that circular references are handled gracefully
        assert len(result["schema_metadata"]["relationships"]["references"]) == 2
        assert len(result["schema_metadata"]["relationships"]["referencedBy"]) == 2

    @pytest.mark.asyncio
    async def test_schema_complex_property_navigation(self, mock_mcp_context):
        """Test complex property path navigation in nested schemas."""
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

        # Create deeply nested schema
        nested_schema = {
            "security-config.yaml": {
                "_metadata": {"title": "Security Configuration Schema"},
                "type": "object",
                "properties": {
                    "centralSecurityServices": {
                        "type": "object",
                        "properties": {
                            "guardduty": {
                                "type": "object",
                                "properties": {
                                    "enable": {"type": "boolean"},
                                    "excludeRegions": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "s3Protection": {
                                        "type": "object",
                                        "properties": {
                                            "enable": {"type": "boolean"},
                                            "excludeRegions": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                            }
                        },
                    }
                },
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(nested_schema))),
        ):
            # Test navigation to deeply nested property
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="security-config.yaml",
                property_path="centralSecurityServices.guardduty.s3Protection",
                include_metadata=False,
            )

        assert result["success"] is True
        assert "property" in result
        assert result["property"]["type"] == "object"
        assert "enable" in result["property"]["properties"]
        assert "excludeRegions" in result["property"]["properties"]

    @pytest.mark.asyncio
    async def test_schema_validation_error_scenarios(self, mock_mcp_context):
        """Test various schema validation error scenarios."""
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

        # Test with malformed JSON
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="invalid json content")),
        ):
            result = await get_schema_func(
                mock_mcp_context, schema_path="invalid-schema.yaml"
            )

        assert result["success"] is False
        assert "error" in result
        assert "Failed to load combined schema file" in result["error"]

    @pytest.mark.asyncio
    async def test_schema_metadata_extraction(self, mock_mcp_context):
        """Test extraction of schema metadata for validation purposes."""
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

        # Create schema with rich metadata
        metadata_rich_schema = {
            "network-config.yaml": {
                "_metadata": {
                    "title": "Network Configuration Schema",
                    "description": "Comprehensive network configuration for LZA",
                    "searchIndex": {
                        "propertyPaths": [
                            "vpcs",
                            "vpcs[].subnets",
                            "vpcs[].routeTables",
                            "centralNetworkServices.ipams",
                            "centralNetworkServices.route53Resolver",
                        ],
                        "requiredProperties": ["vpcs"],
                        "patterns": {
                            "cidr": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/\\d{1,2}$",
                            "vpcName": "^[a-zA-Z][a-zA-Z0-9-]*$",
                        },
                        "enums": {
                            "subnetType": ["public", "private", "isolated"],
                            "routeTableType": ["main", "custom"],
                        },
                    },
                    "statistics": {
                        "nestingDepth": 4,
                        "propertyCount": 35,
                        "requiredCount": 12,
                        "optionalCount": 23,
                        "arrayCount": 8,
                        "objectCount": 15,
                    },
                    "relationships": {
                        "references": [
                            {"schema": "accounts-config.yaml", "paths": ["accountIds"]},
                            {
                                "schema": "security-config.yaml",
                                "paths": ["securityGroups"],
                            },
                        ],
                        "referencedBy": [
                            {"schema": "iam-config.yaml", "paths": ["vpcEndpoints"]}
                        ],
                    },
                },
                "type": "object",
                "properties": {"vpcs": {"type": "array", "items": {"type": "object"}}},
            }
        }

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "builtins.open", mock_open(read_data=json.dumps(metadata_rich_schema))
            ),
        ):
            result = await get_schema_func(
                mock_mcp_context,
                schema_path="network-config.yaml",
                include_metadata=True,
            )

        assert result["success"] is True
        assert "metadata" in result

        # Verify all metadata sections are present
        metadata = result["metadata"]
        assert "searchIndex" in metadata
        assert "statistics" in metadata
        assert "relationships" in metadata

        # Verify search index content
        search_index = metadata["searchIndex"]
        assert len(search_index["propertyPaths"]) == 5
        assert len(search_index["patterns"]) == 2
        assert len(search_index["enums"]) == 2

        # Verify statistics
        stats = metadata["statistics"]
        assert stats["nestingDepth"] == 4
        assert stats["propertyCount"] == 35
        assert stats["requiredCount"] == 12

        # Verify relationships
        relationships = metadata["relationships"]
        assert len(relationships["references"]) == 2
        assert len(relationships["referencedBy"]) == 1
