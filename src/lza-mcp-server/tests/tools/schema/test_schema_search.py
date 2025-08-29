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

"""Unit tests for schema_search module."""

from awslabs.lza_mcp_server.tools.schema.schema_search import (
    search_json_schemas,
    search_schemas,
)


class TestSchemaSearch:
    """Test cases for schema search functionality."""

    def test_search_json_schemas_with_terms(self):
        """Test search_json_schemas with specific search terms."""
        search_terms = ["accounts", "global"]
        result = search_json_schemas(search_terms)

        assert "total_matches" in result
        assert "results" in result
        assert result["total_matches"] == 2
        assert len(result["results"]) == 2

        # Check first result
        first_result = result["results"][0]
        assert first_result["path"] == "accounts-config-schema.json"
        assert first_result["relevance_score"] == 0.9
        assert first_result["match_locations"] == ["property:accounts:substring"]
        assert first_result["_metadata"]["title"] == "Accounts Configuration Schema"
        assert (
            first_result["_metadata"]["description"]
            == "Schema for LZA accounts configuration"
        )

    def test_search_json_schemas_no_terms(self):
        """Test search_json_schemas with no search terms."""
        result = search_json_schemas()

        assert result["total_matches"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["path"] == "default-config-schema.json"

    def test_search_json_schemas_empty_list(self):
        """Test search_json_schemas with empty search terms list."""
        result = search_json_schemas([])

        # The function defaults to ['default'] when no terms provided
        assert result["total_matches"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["path"] == "default-config-schema.json"

    def test_search_json_schemas_single_term(self):
        """Test search_json_schemas with single search term."""
        result = search_json_schemas(["network"])

        assert result["total_matches"] == 1
        assert result["results"][0]["path"] == "network-config-schema.json"
        assert (
            result["results"][0]["_metadata"]["title"] == "Network Configuration Schema"
        )

    def test_search_schemas_alias(self):
        """Test that search_schemas is an alias for search_json_schemas."""
        search_terms = ["security"]
        result1 = search_json_schemas(search_terms)
        result2 = search_schemas(search_terms)

        assert result1 == result2

    def test_search_schemas_with_kwargs(self):
        """Test search_schemas with keyword arguments."""
        result = search_schemas(search_terms=["iam"], limit=10)

        assert result["total_matches"] == 1
        assert result["results"][0]["path"] == "iam-config-schema.json"
