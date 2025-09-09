#!/usr/bin/env python3

"""
Schema search module for LZA JSON schemas.
This module enables searching through JSON schemas using their metadata.
"""

import os
import json
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("schema_search")


class SchemaSearcher:
    """
    Main class for searching through JSON schemas with enhanced metadata.
    """

    def __init__(self, schema_path: str):
        """
        Initialize the searcher with the path to the schema file or directory.

        Args:
            schema_path: Path to a combined JSON file or directory containing JSON schemas
        """
        self.schemas = {}
        self.load_schemas(schema_path)

    def load_schemas(self, schema_path: str) -> None:
        """
        Load schemas from file or directory.

        Args:
            schema_path: Path to a combined JSON file or directory containing JSON schemas
        """
        if os.path.isfile(schema_path):
            # Load from combined JSON file
            logger.info(f"Loading schemas from combined file: {schema_path}")
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    self.schemas = json.load(f)
                logger.info(f"Loaded {len(self.schemas)} schemas from combined file")
            except Exception as e:
                logger.warning(f"Error loading schemas from {schema_path}: {str(e)}")
                raise
        elif os.path.isdir(schema_path):
            # Load from directory containing individual schema files
            logger.info(f"Loading schemas from directory: {schema_path}")
            schema_count = 0
            for root, _, files in os.walk(schema_path):
                for file in files:
                    if file.endswith(".json"):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, schema_path)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                schema_data = json.load(f)
                                self.schemas[relative_path] = schema_data
                                schema_count += 1
                        except Exception as e:
                            logger.error(
                                f"Error loading schema from {file_path}: {str(e)}"
                            )
            logger.info(f"Loaded {schema_count} schemas from directory")
        else:
            logger.error(f"Path does not exist: {schema_path}")
            raise FileNotFoundError(f"Schema path not found: {schema_path}")

    def search(
        self,
        search_terms: List[str],
        search_type: str = "general",
        max_results: int = 5,
        include_metadata: bool = True,
        include_schema: bool = True,
        filters: Optional[Dict] = None,
    ) -> Dict:
        """
        Search through schemas based on specified criteria.

        Args:
            search_terms: List of search terms
            search_type: Type of search (general, property, pattern, relationship, complexity)
            max_results: Maximum number of results to return
            include_metadata: Whether to include metadata in results
            include_schema: Whether to include full schema in results
            filters: Additional filters to apply

        Returns:
            Dictionary containing search results
        """
        if not search_terms:
            return {"error": "No search terms provided"}

        # Initialize filters
        if filters is None:
            filters = {}

        # Initialize search function mapping
        search_functions = {
            "general": self._general_search,
            "property": self._property_search,
            "pattern": self._pattern_search,
            "relationship": self._relationship_search,
            "complexity": self._complexity_search,
        }

        if search_type not in search_functions:
            return {
                "error": f"Invalid search type: {search_type}. Valid types: {list(search_functions.keys())}"
            }

        # Perform search
        search_function = search_functions[search_type]
        matches = search_function(search_terms, filters)

        # Format results
        total_matches = len(matches)
        limited_matches = matches[:max_results]

        results = []
        for match in limited_matches:
            result = {
                "path": match["path"],
                "relevance_score": match["score"],
                "match_locations": match["match_locations"],
            }

            # Add metadata if requested
            if include_metadata and "_metadata" in self.schemas[match["path"]]:
                result["_metadata"] = self.schemas[match["path"]]["_metadata"]

            # Add schema if requested
            if include_schema:
                if not include_metadata:
                    # Include whole schema if metadata not included separately
                    result["schema"] = self.schemas[match["path"]]
                else:
                    # Otherwise exclude metadata from schema portion
                    schema_without_metadata = {
                        k: v
                        for k, v in self.schemas[match["path"]].items()
                        if k != "_metadata"
                    }
                    result["schema"] = schema_without_metadata

            results.append(result)

        return {
            "results": results,
            "total_matches": total_matches,
            "returned_matches": len(limited_matches),
            "search_info": {"terms": search_terms, "type": search_type},
        }

    def _general_search(self, search_terms: List[str], filters: Dict) -> List[Dict]:
        """
        Perform a general search across all metadata fields.
        """
        matches = []

        for path, schema in self.schemas.items():
            score = 0
            match_locations = []

            # Only search schemas with metadata
            if "_metadata" not in schema:
                continue

            metadata = schema["_metadata"]

            for term in search_terms:
                term_lower = term.lower()
                # Create a space-normalized version of the term (remove spaces)
                term_no_spaces = term_lower.replace(" ", "")

                # Check title (higher weight)
                if "title" in metadata:
                    title_lower = metadata["title"].lower()
                    title_no_spaces = title_lower.replace(" ", "")

                    if term_lower in title_lower or (
                        len(term_no_spaces) > 2 and term_no_spaces in title_no_spaces
                    ):
                        score += 1.5
                        match_type = (
                            "normalized" if term_lower not in title_lower else "exact"
                        )
                        match_locations.append(f"title:{match_type}")

                # Check description
                if "description" in metadata:
                    desc_lower = metadata["description"].lower()
                    desc_no_spaces = desc_lower.replace(" ", "")

                    if term_lower in desc_lower or (
                        len(term_no_spaces) > 2 and term_no_spaces in desc_no_spaces
                    ):
                        score += 0.8
                        match_type = (
                            "normalized" if term_lower not in desc_lower else "exact"
                        )
                        match_locations.append(f"description:{match_type}")

                # Check property names (exact matches get higher weight)
                if (
                    "searchIndex" in metadata
                    and "propertyPaths" in metadata["searchIndex"]
                ):
                    for prop in metadata["searchIndex"]["propertyPaths"]:
                        prop_name = prop.split(".")[-1]
                        prop_lower = prop_name.lower()
                        prop_no_spaces = prop_lower.replace(" ", "")

                        # Exact full match
                        if term_lower == prop_lower:
                            score += 1.0
                            match_locations.append(f"property:{prop}:exact")
                        # Exact substring match
                        elif term_lower in prop_lower:
                            score += 0.6
                            match_locations.append(f"property:{prop}:substring")
                        # Space-normalized match (only for terms with 3+ chars)
                        elif (
                            len(term_no_spaces) > 2 and term_no_spaces in prop_no_spaces
                        ):
                            score += 0.5
                            match_locations.append(f"property:{prop}:normalized")

                # Check required properties (higher weight)
                if (
                    "searchIndex" in metadata
                    and "requiredProperties" in metadata["searchIndex"]
                ):
                    for prop in metadata["searchIndex"]["requiredProperties"]:
                        prop_lower = prop.lower()
                        prop_no_spaces = prop_lower.replace(" ", "")

                        if term_lower == prop_lower or (
                            len(term_no_spaces) > 2 and term_no_spaces == prop_no_spaces
                        ):
                            score += 1.2
                            match_type = (
                                "normalized" if term_lower != prop_lower else "exact"
                            )
                            match_locations.append(f"required:{prop}:{match_type}")

                # Check patterns
                if "searchIndex" in metadata and "patterns" in metadata["searchIndex"]:
                    for prop_path, pattern in metadata["searchIndex"][
                        "patterns"
                    ].items():
                        pattern_lower = pattern.lower()
                        pattern_no_spaces = pattern_lower.replace(" ", "")

                        if term_lower in pattern_lower or (
                            len(term_no_spaces) > 2
                            and term_no_spaces in pattern_no_spaces
                        ):
                            score += 0.7
                            match_type = (
                                "normalized"
                                if term_lower not in pattern_lower
                                else "exact"
                            )
                            match_locations.append(f"pattern:{prop_path}:{match_type}")

                # Check enums
                if "searchIndex" in metadata and "enums" in metadata["searchIndex"]:
                    for prop_path, enum_values in metadata["searchIndex"][
                        "enums"
                    ].items():
                        for enum_val in enum_values:
                            if isinstance(enum_val, str):
                                enum_lower = enum_val.lower()
                                enum_no_spaces = enum_lower.replace(" ", "")

                                if term_lower in enum_lower or (
                                    len(term_no_spaces) > 2
                                    and term_no_spaces in enum_no_spaces
                                ):
                                    score += 0.9
                                    match_type = (
                                        "normalized"
                                        if term_lower not in enum_lower
                                        else "exact"
                                    )
                                    match_locations.append(
                                        f"enum:{prop_path}:{match_type}"
                                    )

            if score > 0:
                matches.append(
                    {
                        "path": path,
                        "score": score,
                        "match_locations": list(
                            set(match_locations)
                        ),  # Deduplicate locations
                    }
                )

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _property_search(self, search_terms: List[str], filters: Dict) -> List[Dict]:
        """
        Search for schemas with specific properties.
        """
        matches = []

        for path, schema in self.schemas.items():
            if "_metadata" not in schema:
                continue

            metadata = schema["_metadata"]
            if (
                "searchIndex" not in metadata
                or "propertyPaths" not in metadata["searchIndex"]
            ):
                continue

            property_paths = metadata["searchIndex"]["propertyPaths"]
            required_properties = metadata["searchIndex"].get("requiredProperties", [])

            score = 0
            match_locations = []

            for term in search_terms:
                term_lower = term.lower()
                # Create a space-normalized version of the term
                term_no_spaces = term_lower.replace(" ", "")

                # Look for exact and partial property matches
                for prop_path in property_paths:
                    prop_path_lower = prop_path.lower()
                    prop_path_no_spaces = prop_path_lower.replace(" ", "")

                    prop_parts = prop_path.split(".")
                    last_part = prop_parts[-1]
                    last_part_lower = last_part.lower()

                    # Check for array notation and extract property name
                    if "[]" in last_part_lower:
                        last_part_lower = last_part_lower.replace("[]", "")

                    last_part_no_spaces = last_part_lower.replace(" ", "")

                    # Exact match on full property path
                    if term_lower == prop_path_lower:
                        score += 1.5
                        match_locations.append(f"exact_path:{prop_path}")
                    # Space-normalized match on full property path
                    elif (
                        len(term_no_spaces) > 2
                        and term_no_spaces == prop_path_no_spaces
                    ):
                        score += 1.3
                        match_locations.append(f"normalized_path:{prop_path}")

                    # Exact match on property name
                    elif term_lower == last_part_lower:
                        score += 1.2
                        match_locations.append(f"property:{prop_path}")
                    # Space-normalized exact match on property name
                    elif (
                        len(term_no_spaces) > 2
                        and term_no_spaces == last_part_no_spaces
                    ):
                        score += 1.0
                        match_locations.append(f"normalized_property:{prop_path}")

                    # Partial match on property name
                    elif term_lower in last_part_lower:
                        score += 0.8
                        match_locations.append(f"partial:{prop_path}")
                    # Space-normalized partial match
                    elif (
                        len(term_no_spaces) > 2
                        and term_no_spaces in last_part_no_spaces
                    ):
                        score += 0.6
                        match_locations.append(f"normalized_partial:{prop_path}")

                # Give higher score to required properties
                for req_prop in required_properties:
                    req_prop_lower = req_prop.lower()
                    req_prop_no_spaces = req_prop_lower.replace(" ", "")

                    if term_lower == req_prop_lower:
                        score += 0.5  # Additional points for required property
                        match_locations.append(f"required:{req_prop}")
                    elif (
                        len(term_no_spaces) > 2 and term_no_spaces == req_prop_no_spaces
                    ):
                        score += 0.4  # Slightly less for normalized match
                        match_locations.append(f"normalized_required:{req_prop}")

            if score > 0:
                matches.append(
                    {
                        "path": path,
                        "score": score,
                        "match_locations": list(set(match_locations)),
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _pattern_search(self, search_terms: List[str], filters: Dict) -> List[Dict]:
        """
        Search for schemas with specific validation patterns.
        """
        matches = []

        for path, schema in self.schemas.items():
            if "_metadata" not in schema:
                continue

            metadata = schema["_metadata"]
            if (
                "searchIndex" not in metadata
                or "patterns" not in metadata["searchIndex"]
            ):
                continue

            patterns = metadata["searchIndex"]["patterns"]

            score = 0
            match_locations = []

            for term in search_terms:
                term_lower = term.lower()

                # Search in pattern keys (property paths)
                for prop_path in patterns.keys():
                    if term_lower in prop_path.lower():
                        score += 0.8
                        match_locations.append(f"pattern_property:{prop_path}")

                # Search in pattern values (regex patterns)
                for prop_path, pattern in patterns.items():
                    if term_lower in pattern.lower():
                        score += 1.0
                        match_locations.append(f"pattern_value:{prop_path}")

                    # Special case for common pattern types
                    if term_lower == "email" and "@" in pattern:
                        score += 1.2
                        match_locations.append(f"email_pattern:{prop_path}")
                    elif term_lower == "url" and "http" in pattern:
                        score += 1.2
                        match_locations.append(f"url_pattern:{prop_path}")
                    elif term_lower == "ip" and any(
                        x in pattern for x in ["\\d+\\.\\d+", "\\d{1,3}"]
                    ):
                        score += 1.2
                        match_locations.append(f"ip_pattern:{prop_path}")

            if score > 0:
                matches.append(
                    {
                        "path": path,
                        "score": score,
                        "match_locations": list(set(match_locations)),
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _relationship_search(
        self, search_terms: List[str], filters: Dict
    ) -> List[Dict]:
        """
        Search for schemas based on their relationships with other schemas.
        """
        matches = []

        for path, schema in self.schemas.items():
            if "_metadata" not in schema:
                continue

            metadata = schema["_metadata"]
            if "relationships" not in metadata:
                continue

            relationships = metadata["relationships"]
            references = relationships.get("references", [])
            referenced_by = relationships.get("referencedBy", [])

            score = 0
            match_locations = []

            for term in search_terms:
                term_lower = term.lower()

                # Check outbound references
                for ref in references:
                    if "schema" in ref and term_lower in ref["schema"].lower():
                        score += 1.2
                        match_locations.append(f"references:{ref['schema']}")

                    # Check paths where references are used
                    if "paths" in ref:
                        for path_item in ref["paths"]:
                            if term_lower in path_item.lower():
                                score += 0.7
                                match_locations.append(f"reference_path:{path_item}")

                # Check inbound references
                for ref in referenced_by:
                    if "schema" in ref and term_lower in ref["schema"].lower():
                        score += 1.0
                        match_locations.append(f"referenced_by:{ref['schema']}")

                    # Check paths where this schema is referenced
                    if "paths" in ref:
                        for path_item in ref["paths"]:
                            if term_lower in path_item.lower():
                                score += 0.7
                                match_locations.append(
                                    f"referenced_by_path:{path_item}"
                                )

            if score > 0:
                matches.append(
                    {
                        "path": path,
                        "score": score,
                        "match_locations": list(set(match_locations)),
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _complexity_search(self, search_terms: List[str], filters: Dict) -> List[Dict]:
        """
        Search for schemas based on complexity metrics.
        """
        matches = []

        # Extract filter thresholds with defaults
        min_depth = filters.get("min_depth", 0)
        max_depth = filters.get("max_depth", float("inf"))
        min_properties = filters.get("min_properties", 0)
        max_properties = filters.get("max_properties", float("inf"))
        min_required = filters.get("min_required", 0)
        max_required = filters.get("max_required", float("inf"))

        for path, schema in self.schemas.items():
            if "_metadata" not in schema:
                continue

            metadata = schema["_metadata"]
            if "statistics" not in metadata:
                continue

            stats = metadata["statistics"]

            # Check if schema meets complexity thresholds
            nesting_depth = stats.get("nestingDepth", 0)
            property_count = stats.get("propertyCount", 0)
            required_count = stats.get("requiredCount", 0)

            if (
                nesting_depth < min_depth
                or nesting_depth > max_depth
                or property_count < min_properties
                or property_count > max_properties
                or required_count < min_required
                or required_count > max_required
            ):
                continue

            # Calculate complexity score
            # We'll use a weighted score based on metrics
            complexity_score = (
                (nesting_depth * 1.0) + (property_count * 0.2) + (required_count * 0.3)
            )

            # Calculate search term relevance
            term_score = 0
            match_locations = []

            for term in search_terms:
                term_lower = term.lower()

                # Keywords related to complexity
                complexity_keywords = {
                    "complex": nesting_depth > 3 or property_count > 10,
                    "nested": nesting_depth > 2,
                    "deep": nesting_depth > 3,
                    "shallow": nesting_depth <= 2,
                    "simple": nesting_depth <= 2 and property_count <= 5,
                    "large": property_count > 15,
                    "small": property_count <= 5,
                    "restrictive": required_count > 5,
                    "flexible": required_count <= 3,
                }

                # Match against keywords
                if (
                    term_lower in complexity_keywords
                    and complexity_keywords[term_lower]
                ):
                    term_score += 1.0
                    match_locations.append(f"complexity:{term_lower}")

                # Match against schema title and description
                if "title" in metadata and term_lower in metadata["title"].lower():
                    term_score += 0.5
                    match_locations.append("title")

                if (
                    "description" in metadata
                    and term_lower in metadata["description"].lower()
                ):
                    term_score += 0.3
                    match_locations.append("description")

            final_score = complexity_score
            if term_score > 0:
                final_score += term_score
                matches.append(
                    {
                        "path": path,
                        "score": final_score,
                        "match_locations": list(set(match_locations)),
                        "complexity_metrics": {
                            "nesting_depth": nesting_depth,
                            "property_count": property_count,
                            "required_count": required_count,
                        },
                    }
                )
            elif len(search_terms) == 1 and search_terms[0].lower() == "all":
                # Special case: return all schemas sorted by complexity
                matches.append(
                    {
                        "path": path,
                        "score": final_score,
                        "match_locations": ["all_schemas"],
                        "complexity_metrics": {
                            "nesting_depth": nesting_depth,
                            "property_count": property_count,
                            "required_count": required_count,
                        },
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches


def search_json_schemas(
    schema_path: str,
    search_terms: List[str],
    search_type: str = "general",
    max_results: int = 5,
    include_metadata: bool = True,
    include_schema: bool = True,
    filters: Dict = None,
) -> Dict:
    """
    Helper function to search JSON schemas without creating a SchemaSearcher instance.

    Args:
        schema_path: Path to combined JSON file or directory of JSON schemas
        search_terms: List of search terms (must be a list, even for a single term)
        search_type: Type of search (general, property, pattern, relationship, complexity)
        max_results: Maximum number of results to return
        include_metadata: Whether to include metadata in results
        include_schema: Whether to include full schema in results
        filters: Additional filters to apply

    Returns:
        Dictionary containing search results
    """
    searcher = SchemaSearcher(schema_path)
    return searcher.search(
        search_terms=search_terms,
        search_type=search_type,
        max_results=max_results,
        include_metadata=include_metadata,
        include_schema=include_schema,
        filters=filters,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search JSON schemas")
    parser.add_argument(
        "schema_path", help="Path to combined JSON file or directory containing schemas"
    )
    parser.add_argument("--terms", required=True, help="Search terms, comma separated")
    parser.add_argument(
        "--type",
        default="general",
        choices=["general", "property", "pattern", "relationship", "complexity"],
        help="Type of search to perform",
    )
    parser.add_argument(
        "--max-results", type=int, default=5, help="Maximum number of results to return"
    )
    parser.add_argument(
        "--no-metadata",
        action="store_false",
        dest="include_metadata",
        help="Exclude metadata from results",
    )
    parser.add_argument(
        "--no-schema",
        action="store_false",
        dest="include_schema",
        help="Exclude schema from results",
    )

    # Complexity filters
    parser.add_argument("--min-depth", type=int, help="Minimum nesting depth")
    parser.add_argument("--max-depth", type=int, help="Maximum nesting depth")
    parser.add_argument(
        "--min-properties", type=int, help="Minimum number of properties"
    )
    parser.add_argument(
        "--max-properties", type=int, help="Maximum number of properties"
    )
    parser.add_argument(
        "--min-required", type=int, help="Minimum number of required fields"
    )
    parser.add_argument(
        "--max-required", type=int, help="Maximum number of required fields"
    )

    args = parser.parse_args()

    # Build filters dict
    filters = {}
    for filter_name in [
        "min_depth",
        "max_depth",
        "min_properties",
        "max_properties",
        "min_required",
        "max_required",
    ]:
        value = getattr(args, filter_name, None)
        if value is not None:
            filters[filter_name] = value

    # Parse search terms
    search_terms = [term.strip() for term in args.terms.split(",")]

    # Execute search
    results = search_json_schemas(
        schema_path=args.schema_path,
        search_terms=search_terms,
        search_type=args.type,
        max_results=args.max_results,
        include_metadata=args.include_metadata,
        include_schema=args.include_schema,
        filters=filters,
    )

    # Print results
    print(json.dumps(results, indent=2))
