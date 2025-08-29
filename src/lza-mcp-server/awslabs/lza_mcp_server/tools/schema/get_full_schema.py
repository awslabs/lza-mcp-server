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

logger = logging.getLogger(__name__)


async def tool_search_json_schema(
    ctx: Context,
    search_terms: List[str],
    search_type: str = "general",
    max_results: int = 10,
    include_metadata: bool = True,
    include_schema: bool = False,
    filters: Optional[Dict] = None,
    schema_path: Optional[str] = None,
    format_level: str = "standard",
) -> Dict[str, Any]:
    """Search JSON schemas using different search strategies.

    This tool provides powerful search capabilities across all LZA JSON schemas to help
    users discover configuration options and understand the structure of LZA configurations.

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
        search_terms (List[str]): List of search terms to look for in the schemas
        search_type (str, optional): Type of search (general, property, pattern, relationship, complexity). Default: general
        max_results (int, optional): Maximum number of results to return. Default: 10
        include_metadata (bool, optional): Whether to include metadata in results. Default: True
        include_schema (bool, optional): Whether to include the full schema in results. Default: False
        filters (Dict, optional): Additional filters for complexity search (min/max depth, properties, required fields)
        schema_path (str, optional): Optional path to schema file or directory (uses default if not provided)
        format_level (str, optional): Detail level for results (minimal, standard, detailed). Default: standard

    Returns:
        Dictionary containing search results with matching schemas, relevance scores, and match locations
    """
    try:
        await ctx.info(
            f"Searching JSON schemas for terms: {search_terms}, type: {search_type}"
        )

        # Import schema_search module
        try:
            from schema_search import search_json_schemas

            await ctx.info("Successfully imported schema_search module")
        except ImportError:
            json_schema_dir = os.path.join(
                os.path.dirname(__file__), "../../../json-schema/src"
            )
            sys.path.append(os.path.abspath(json_schema_dir))
            try:
                from schema_search import search_json_schemas

                await ctx.info(f"Imported schema_search from {json_schema_dir}")
            except ImportError as e:
                error_message = f"Failed to import schema_search module: {e}"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": "Module import failed. Please check if schema_search.py is available.",
                }

        # Determine schema path
        if schema_path is None:
            schema_path = os.path.join("/app/json-output", "combined.json")
            await ctx.info(f"Using default schema path: {schema_path}")
        else:
            await ctx.info(f"Using user-provided schema path: {schema_path}")

        # Check if the schema file exists
        if not os.path.exists(schema_path):
            error_message = f"Schema file not found: {schema_path}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Schema file not found. Please provide a valid path or ensure 'combined.json' is available.",
                "troubleshooting": "The schema search function requires a combined.json file that contains all schemas with metadata.",
            }

        # Prepare filters for complexity search
        if filters is None:
            filters = {}

        # Perform the search
        try:
            include_schema_actual = include_schema and format_level == "detailed"

            search_result = search_json_schemas(
                schema_path=schema_path,
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
