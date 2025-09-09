#!/usr/bin/env python3

"""
Search utility for LZA JSON schemas.
This script allows searching through the processed JSON schemas.
"""

import sys
import json
import argparse
from schema_search import search_json_schemas


def main():
    parser = argparse.ArgumentParser(description="Search LZA JSON schemas")
    parser.add_argument(
        "schema_path", help="Path to combined JSON file or directory containing schemas"
    )
    parser.add_argument(
        "--terms",
        required=True,
        help='Search terms in JSON array format (e.g., \'["vpc", "subnet"]\') - must be a valid JSON array',
    )
    parser.add_argument(
        "--type",
        default="general",
        choices=["general", "property", "pattern", "relationship", "complexity"],
        help="Type of search to perform",
    )
    parser.add_argument(
        "--max-results", type=int, default=5, help="Maximum number of results to return"
    )
    parser.add_argument("--output", help="Output file for search results (JSON format)")
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
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Print a human-readable summary of results",
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

    # Parse search terms - require strict JSON array format
    try:
        # Verify that input is a proper JSON array
        if not (args.terms.startswith("[") and args.terms.endswith("]")):
            raise ValueError("Search terms must be provided as a JSON array")

        search_terms = json.loads(args.terms)

        # Verify that the parsed result is a list
        if not isinstance(search_terms, list):
            raise ValueError("Search terms must be a JSON array, not a single value")

        print(f"Parsed search terms: {search_terms}")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: {str(e)}")
        print('Search terms must be in JSON array format, e.g.: \'["term1", "term2"]\'')
        print("For a single term, use: '[\"term\"]'")
        sys.exit(1)

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

    # Output results
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Search results saved to {args.output}")

    if args.summarize or not args.output:
        print(
            f"\n=== Search Results: {args.type.title()} search for {', '.join(search_terms)} ==="
        )
        print(
            f"Found {results['total_matches']} matches, showing {results['returned_matches']}"
        )

        for i, result in enumerate(results["results"]):
            print(
                f"\n[{i + 1}] {result['path']} (Score: {result['relevance_score']:.2f})"
            )
            print(f"    Match locations: {', '.join(result['match_locations'])}")

            # If metadata is included, show key information
            if args.include_metadata and "_metadata" in result:
                metadata = result["_metadata"]
                print(f"    Title: {metadata.get('title', 'N/A')}")
                if "statistics" in metadata:
                    stats = metadata["statistics"]
                    print(
                        f"    Properties: {stats.get('propertyCount', 0)}, "
                        + f"Required: {stats.get('requiredCount', 0)}, "
                        + f"Depth: {stats.get('nestingDepth', 0)}"
                    )

    # If not summarizing or outputting to file, print raw JSON
    if not args.summarize and not args.output:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
