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
import json
import logging
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


class OptimizedSchemaSearcher:
    """Optimized schema searcher that handles large files efficiently."""

    def __init__(self, schema_path: str):
        self.schema_path = schema_path
        self._schema_keys = None

    def _get_schema_keys(self) -> List[str]:
        """Get list of schema keys without loading full content."""
        if self._schema_keys is None:
            try:
                with open(self.schema_path, "r", encoding="utf-8") as f:
                    # Read just enough to get the keys
                    content = f.read(1024 * 1024)  # Read first 1MB
                    if content.endswith("}"):
                        # Small file, parse normally
                        data = json.loads(content)
                        self._schema_keys = list(data.keys())
                    else:
                        # Large file, extract keys manually
                        self._schema_keys = self._extract_keys_from_large_file()
            except Exception as e:
                logger.error(f"Failed to get schema keys: {e}")
                self._schema_keys = []
        return self._schema_keys

    def _extract_keys_from_large_file(self) -> List[str]:
        """Extract schema keys from large JSON file without full parsing."""
        keys = []
        try:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                in_key = False
                current_key = ""
                brace_count = 0

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Look for top-level keys (at brace_count == 1)
                    for char in line:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                        elif char == '"' and brace_count == 1:
                            if not in_key:
                                in_key = True
                                current_key = ""
                            else:
                                in_key = False
                                if current_key and current_key not in keys:
                                    keys.append(current_key)
                        elif in_key and brace_count == 1:
                            current_key += char

                    # Stop after reasonable number of keys to avoid memory issues
                    if len(keys) > 1000:
                        break

        except Exception as e:
            logger.error(f"Failed to extract keys from large file: {e}")

        return keys

    def search_schemas_chunked(
        self, search_terms: List[str], max_results: int = 10, chunk_size: int = 50
    ) -> Dict[str, Any]:
        """Search schemas in chunks to avoid memory issues."""
        results = []
        total_processed = 0

        schema_keys = self._get_schema_keys()

        # Process in chunks
        for i in range(0, len(schema_keys), chunk_size):
            chunk_keys = schema_keys[i : i + chunk_size]
            chunk_results = self._search_chunk(chunk_keys, search_terms)
            results.extend(chunk_results)
            total_processed += len(chunk_keys)

            # Stop if we have enough results
            if len(results) >= max_results:
                results = results[:max_results]
                break

        return {
            "total_matches": len(results),
            "results": results,
            "processed_schemas": total_processed,
        }

    def _search_chunk(
        self, schema_keys: List[str], search_terms: List[str]
    ) -> List[Dict[str, Any]]:
        """Search a chunk of schemas."""
        results = []

        try:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                content = f.read()
                data = json.loads(content)

                for key in schema_keys:
                    if key in data:
                        schema = data[key]
                        matches = self._check_schema_matches(key, schema, search_terms)
                        if matches:
                            results.append(matches)

        except Exception as e:
            logger.error(f"Failed to search chunk: {e}")

        return results

    def _check_schema_matches(
        self, schema_key: str, schema: Dict[str, Any], search_terms: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if a schema matches search terms."""
        match_locations = []
        relevance_score = 0.0

        # Convert search terms to lowercase for case-insensitive search
        search_terms_lower = [term.lower() for term in search_terms]

        # Check schema key
        schema_key_lower = schema_key.lower()
        for term in search_terms_lower:
            if term in schema_key_lower:
                match_locations.append(f"schema_name:{term}")
                relevance_score += 0.8

        # Check metadata if available
        if "_metadata" in schema:
            metadata = schema["_metadata"]

            # Check title
            title = metadata.get("title", "").lower()
            for term in search_terms_lower:
                if term in title:
                    match_locations.append(f"title:{term}")
                    relevance_score += 0.6

            # Check description
            description = metadata.get("description", "").lower()
            for term in search_terms_lower:
                if term in description:
                    match_locations.append(f"description:{term}")
                    relevance_score += 0.4

        # Check properties (limited to avoid memory issues)
        if "properties" in schema:
            properties = schema["properties"]
            prop_count = 0
            for prop_name, prop_def in properties.items():
                if prop_count > 20:  # Limit property checking
                    break

                prop_name_lower = prop_name.lower()
                for term in search_terms_lower:
                    if term in prop_name_lower:
                        match_locations.append(f"property:{prop_name}")
                        relevance_score += 0.5

                prop_count += 1

        if match_locations:
            return {
                "path": schema_key,
                "relevance_score": min(relevance_score, 1.0),
                "match_locations": match_locations[:5],  # Limit match locations
                "_metadata": schema.get("_metadata", {}),
            }

        return None


async def tool_search_json_schema_optimized(
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
    """Optimized JSON schema search that handles large files efficiently."""

    try:
        await ctx.info(f"Starting optimized search for terms: {search_terms}")

        # Determine schema path
        if schema_path is None:
            schema_path = os.path.join("/app/json-output", "combined.json")

        # Check if file exists
        if not os.path.exists(schema_path):
            # Try local path for development
            local_schema_path = "/Users/vmayberr/xdev/mte/lza-mcp-server/src/lza-mcp-server/json-output/combined.json"
            if os.path.exists(local_schema_path):
                schema_path = local_schema_path
            else:
                return {
                    "success": False,
                    "error": f"Schema file not found: {schema_path}",
                    "message": "Schema file not available for search.",
                }

        # Check file size and warn if large
        file_size = os.path.getsize(schema_path)
        await ctx.info(f"Schema file size: {file_size / (1024 * 1024):.1f}MB")

        if file_size > 10 * 1024 * 1024:  # 10MB
            await ctx.info("Large schema file detected, using chunked processing")

        # Initialize optimized searcher
        searcher = OptimizedSchemaSearcher(schema_path)

        # Perform chunked search
        chunk_size = (
            20 if file_size > 5 * 1024 * 1024 else 50
        )  # Smaller chunks for large files
        search_result = searcher.search_schemas_chunked(
            search_terms=search_terms, max_results=max_results, chunk_size=chunk_size
        )

        await ctx.info(
            f"Search completed. Found {search_result.get('total_matches', 0)} matches from {search_result.get('processed_schemas', 0)} schemas."
        )

        # Format results
        formatted_results = []
        for i, result in enumerate(search_result.get("results", [])):
            formatted_result = {
                "rank": i + 1,
                "path": result.get("path", "unknown"),
                "score": result.get("relevance_score", 0),
                "match_locations": result.get("match_locations", []),
                "schema_ref": result.get("path", "unknown"),
            }

            # Add metadata if requested and available
            if include_metadata and "_metadata" in result:
                metadata = result.get("_metadata", {})
                formatted_result["title"] = metadata.get("title", "Untitled Schema")
                formatted_result["description"] = (
                    metadata.get("description", "No description")[:200] + "..."
                    if len(metadata.get("description", "")) > 200
                    else metadata.get("description", "No description")
                )

            formatted_results.append(formatted_result)

        return {
            "success": True,
            "message": f"Found {search_result.get('total_matches', 0)} matches for '{', '.join(search_terms)}' (showing {len(formatted_results)})",
            "search_info": {
                "terms": search_terms,
                "type": search_type,
                "total_matches": search_result.get("total_matches", 0),
                "returned_matches": len(formatted_results),
                "processed_schemas": search_result.get("processed_schemas", 0),
                "file_size_mb": round(file_size / (1024 * 1024), 1),
            },
            "results": formatted_results,
        }

    except Exception as e:
        error_message = f"Optimized search failed: {str(e)}"
        await ctx.error(error_message)
        return {
            "success": False,
            "error": error_message,
            "message": "Search operation failed. The schema file may be too large or corrupted.",
        }
