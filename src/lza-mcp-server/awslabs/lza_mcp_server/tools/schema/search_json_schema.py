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

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import Context
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    validate_integer_range,
)

logger = logging.getLogger(__name__)


async def tool_search_json_schema(
    ctx: Context,
    lza_version: str,
    search_terms: List[str],
    search_type: str = "general",
    max_results: int = 10,
    include_metadata: bool = True,
    include_schema: bool = False,
    filters: Optional[Dict] = None,
    format_level: str = "standard",
) -> Dict[str, Any]:
    """Search JSON schemas using different search strategies.

    This tool searches ACROSS ALL SCHEMAS for the specified LZA version. To retrieve a
    specific schema or property within a schema, use getFullSchema instead.

    RECOMMENDED WORKFLOW: Call getDeployedLzaVersion() first to get the correct lza_version
    parameter that matches your deployed environment.

    The tool supports multiple search strategies:

    1. **General Search**: Searches across all metadata fields including titles, descriptions,
       and property names. Most comprehensive search type for general exploration.

    2. **Property Search**: Specifically finds schemas that contain properties matching the
       search terms. Useful when looking for schemas with specific data fields.

    3. **Pattern Search**: Finds schemas that use specific validation patterns (like regular
       expressions). Great for finding schemas with specific data format validations.

    4. **Relationship Search**: Discovers schemas based on their relationships with other
       schemas. Helps map dependencies between different schema components.

    5. **Complexity Search**: Finds schemas based on complexity metrics like nesting depth
       or property count. Useful for identifying the most complex or simplest schemas.

    Results can be formatted at different detail levels (minimal, standard, detailed) and
    can optionally include full schema content for detailed analysis.

    Args:
        lza_version (str): LZA version to search (e.g., 'v1.12.0', 'v1.13.0'). Call getDeployedLzaVersion() to get the correct version.
        search_terms (List[str]): List of search terms to look for in the schemas
        search_type (str, optional): Type of search (general, property, pattern, relationship, complexity). Default: general
        max_results (int, optional): Maximum number of results to return. Default: 10
        include_metadata (bool, optional): Whether to include metadata in results. Default: True
        include_schema (bool, optional): Whether to include the full schema in results. Default: False
        filters (Dict, optional): Additional filters for complexity search (min/max depth, properties, required fields)
        format_level (str, optional): Detail level for results (minimal, standard, detailed). Default: standard

    Returns:
        Dictionary containing search results with matching schemas, relevance scores, and match locations

    Note:
        This tool does NOT support schema_path parameter. It always searches across all schemas
        for the specified LZA version. For schema-specific queries, use getFullSchema with the
        schema_path parameter instead.
    """
    try:
        # Validate LZA version parameter
        is_valid, validation_error = validate_string_input(
            lza_version, "lza_version", min_length=1, max_length=50
        )
        if not is_valid:
            await ctx.error(validation_error)
            return {
                "success": False,
                "error": validation_error,
                "message": "Invalid LZA version format",
                "hint": "Call getDeployedLzaVersion() first to get the correct version for your environment",
            }

        if not lza_version:
            error_message = "lza_version parameter is required"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Please specify an LZA version (e.g., 'v1.12.0', 'v1.13.0')",
                "hint": "Call getDeployedLzaVersion() first to get the correct version for your environment",
            }

        # Validate search_terms
        if not search_terms or not isinstance(search_terms, list):
            error_message = "search_terms must be a non-empty list"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Please provide search terms as a list of strings",
            }

        for term in search_terms:
            is_valid, validation_error = validate_string_input(
                term, "search_term", min_length=1, max_length=200
            )
            if not is_valid:
                await ctx.error(validation_error)
                return {
                    "success": False,
                    "error": validation_error,
                    "message": "Invalid search term format",
                }

        # Validate max_results
        is_valid, validation_error = validate_integer_range(
            max_results, "max_results", min_value=1, max_value=100
        )
        if not is_valid:
            await ctx.error(validation_error)
            return {
                "success": False,
                "error": validation_error,
                "message": "max_results must be between 1 and 100",
            }

        # Validate search_type
        valid_search_types = [
            "general",
            "property",
            "pattern",
            "relationship",
            "complexity",
        ]
        if search_type not in valid_search_types:
            error_message = f"Invalid search_type: {search_type}. Must be one of: {', '.join(valid_search_types)}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": f"search_type must be one of: {', '.join(valid_search_types)}",
            }

        # Validate format_level
        valid_format_levels = ["minimal", "standard", "detailed"]
        if format_level not in valid_format_levels:
            error_message = f"Invalid format_level: {format_level}. Must be one of: {', '.join(valid_format_levels)}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": f"format_level must be one of: {', '.join(valid_format_levels)}",
            }

        # Reject "latest" to ensure version-specific searches
        if lza_version.lower() == "latest":
            error_message = "The 'latest' version is not allowed for schema searches"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Schema searches must use a specific LZA version to ensure accuracy with your deployed environment.",
                "required_action": "Call getDeployedLzaVersion() to get the currently deployed LZA version, then use that version string",
                "example": "If getDeployedLzaVersion() returns 'v1.12.0', use lza_version='v1.12.0'",
            }

        # Use version-specific path (schema_path parameter removed)
        schema_file_path = os.path.join(
            "/app/json-schemas", lza_version, "combined.json"
        )
        await ctx.info(f"Using version-specific schema path: {schema_file_path}")

        # Check if schema file exists
        if not os.path.exists(schema_file_path):
            # Check if version directory exists to provide better error message
            version_dir = os.path.join("/app/json-schemas", lza_version)
            if not os.path.exists(version_dir):
                available_versions = []
                schemas_base = "/app/json-schemas"
                if os.path.exists(schemas_base):
                    available_versions = [
                        d
                        for d in os.listdir(schemas_base)
                        if os.path.isdir(os.path.join(schemas_base, d))
                    ]

                error_message = f"LZA version '{lza_version}' not found"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": f"The specified LZA version '{lza_version}' is not available.",
                    "available_versions": available_versions
                    if available_versions
                    else ["No versions found"],
                    "hint": "Call getDeployedLzaVersion() to get the correct version, or use listLzaSupportedVersions() to see all available versions",
                }
            else:
                error_message = f"Schema file not found for version '{lza_version}': {schema_file_path}"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": f"Version directory exists but combined.json not found for '{lza_version}'",
                }

        await ctx.info(
            f"Searching JSON schemas (version: {lza_version}) for terms: {search_terms}, type: {search_type}"
        )

        # Import schema_search module
        # Try multiple import strategies to handle different deployment scenarios
        search_json_schemas = None

        # Strategy 1: Try direct import (works if schema_search is in PYTHONPATH)
        try:
            from schema_search import search_json_schemas

            await ctx.info("Successfully imported schema_search module (direct import)")
        except ImportError:
            pass

        # Strategy 2: Try relative to this file's location
        if search_json_schemas is None:
            try:
                json_schema_dir = os.path.join(
                    os.path.dirname(__file__), "../../../json-schema/src"
                )
                json_schema_dir_abs = os.path.abspath(json_schema_dir)
                if json_schema_dir_abs not in sys.path:
                    sys.path.insert(0, json_schema_dir_abs)
                from schema_search import search_json_schemas

                await ctx.info(f"Imported schema_search from {json_schema_dir_abs}")
            except ImportError:
                pass

        # Strategy 3: Try relative to package root
        if search_json_schemas is None:
            try:
                # Get package root (awslabs/lza_mcp_server)
                package_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(__file__))
                )
                json_schema_dir = os.path.join(package_root, "../../json-schema/src")
                json_schema_dir_abs = os.path.abspath(json_schema_dir)
                if json_schema_dir_abs not in sys.path:
                    sys.path.insert(0, json_schema_dir_abs)
                from schema_search import search_json_schemas

                await ctx.info(
                    f"Imported schema_search from package root: {json_schema_dir_abs}"
                )
            except ImportError:
                pass

        # If all strategies failed, return error
        if search_json_schemas is None:
            error_message = (
                "Failed to import schema_search module after trying multiple strategies"
            )
            await ctx.error(error_message)
            await ctx.error(f"Current sys.path: {sys.path}")
            await ctx.error(f"Current __file__: {__file__}")
            return {
                "success": False,
                "error": error_message,
                "message": "Module import failed. Please check if schema_search.py is available in json-schema/src directory.",
                "troubleshooting": [
                    "Verify that json-schema/src/schema_search.py exists",
                    "Check that the MCP server has access to the json-schema directory",
                    "Ensure the package structure is intact after installation",
                ],
            }

        # Use the schema_file_path for the search
        schema_path_for_search = schema_file_path

        # Prepare filters for complexity search
        if filters is None:
            filters = {}

        # Perform the search
        try:
            include_schema_actual = include_schema and format_level == "detailed"

            search_result = search_json_schemas(
                schema_path=schema_path_for_search,
                search_terms=search_terms,
                search_type=search_type,
                max_results=max_results,
                include_metadata=include_metadata,
                include_schema=include_schema_actual,
                filters=filters,
            )

            await ctx.info(
                f"Search completed. Found {search_result.get('total_matches', 0)} matches."
            )

            # Format the results based on format_level
            formatted_results = []
            for i, result in enumerate(search_result.get("results", [])):
                formatted_result = {
                    "rank": i + 1,
                    "path": result.get("path", "unknown"),
                    "score": result.get("relevance_score", 0),
                    "match_locations": result.get("match_locations", []),
                    "schema_ref": result.get("path", "unknown"),
                }

                # Add metadata fields when available and requested
                if include_metadata and "_metadata" in result:
                    metadata = result.get("_metadata", {})
                    formatted_result["title"] = metadata.get("title", "Untitled Schema")
                    formatted_result["description"] = metadata.get(
                        "description", "No description"
                    )

                    if format_level == "detailed" and "statistics" in metadata:
                        formatted_result["statistics"] = metadata.get("statistics", {})

                # Include schema only for detailed format and when explicitly requested
                if include_schema_actual and "schema" in result:
                    formatted_result["schema"] = result.get("schema")

                formatted_results.append(formatted_result)

            return {
                "success": True,
                "message": f"Found {search_result.get('total_matches', 0)} matches for '{', '.join(search_terms)}' (showing {len(formatted_results)})",
                "search_info": {
                    "lza_version": lza_version,
                    "terms": search_terms,
                    "type": search_type,
                    "total_matches": search_result.get("total_matches", 0),
                    "returned_matches": len(formatted_results),
                },
                "results": formatted_results,
            }

        except Exception as e:
            error_message = f"Search failed: {str(e)}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Search operation failed. Please check the search parameters and try again.",
            }

    except Exception as e:
        error_message = f"Error searching JSON schemas: {str(e)}"
        await ctx.error(error_message)
        return {
            "success": False,
            "error": error_message,
            "message": "An unexpected error occurred while performing the search.",
        }
