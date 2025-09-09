#!/usr/bin/env python3

"""
Examples demonstrating how to use the JSON schema search functionality.
Run this script after processing schemas to see examples of different search types.
"""

import os
import sys
from schema_search import search_json_schemas


def print_results(title, results, detailed=False):
    """
    Print search results in a human-readable format.
    """
    print("\n" + "=" * 80)
    print(f"### {title} ###")
    print("=" * 80)

    print(
        f"Found {results['total_matches']} matches, showing {results['returned_matches']}"
    )

    for i, result in enumerate(results["results"]):
        print(f"\n[{i + 1}] {result['path']} (Score: {result['relevance_score']:.2f})")
        print(f"    Match locations: {', '.join(result['match_locations'])}")

        if detailed and "_metadata" in result:
            metadata = result["_metadata"]
            print("\n    Metadata Summary:")
            print(f"    - Title: {metadata.get('title', 'N/A')}")
            print(f"    - Description: {metadata.get('description', 'N/A')[:100]}...")

            if "statistics" in metadata:
                stats = metadata["statistics"]
                print(f"    - Properties: {stats.get('propertyCount', 0)}")
                print(f"    - Required: {stats.get('requiredCount', 0)}")
                print(f"    - Nesting Depth: {stats.get('nestingDepth', 0)}")

            if (
                "searchIndex" in metadata
                and "requiredProperties" in metadata["searchIndex"]
            ):
                req_props = metadata["searchIndex"]["requiredProperties"]
                if req_props:
                    print(
                        f"    - Required Properties: {', '.join(req_props[:5])}"
                        + ("..." if len(req_props) > 5 else "")
                    )


def run_examples(schema_path):
    """
    Run all search examples.
    """
    # Example 1: General search for "security"
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["security"],
        search_type="general",
        max_results=3,
        include_schema=False,  # Exclude schema for brevity in output
    )
    print_results("General Search for 'security'", results, detailed=True)

    # Example 2: Property search for "vpc" and "subnet"
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["vpc", "subnet"],
        search_type="property",
        max_results=3,
        include_schema=False,
    )
    print_results("Property Search for 'vpc' and 'subnet'", results)

    # Example 3: Pattern search for email fields
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["email"],
        search_type="pattern",
        max_results=3,
        include_schema=False,
    )
    print_results("Pattern Search for 'email'", results)

    # Example 4: Relationship search
    # First find a schema to use as reference
    base_results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["organization"],
        search_type="general",
        max_results=1,
        include_schema=False,
    )

    if base_results["results"]:
        # Get schema name to use as search term
        ref_schema = base_results["results"][0]["path"]
        ref_name = os.path.basename(ref_schema)

        # Now search for schemas related to this one
        results = search_json_schemas(
            schema_path=schema_path,
            search_terms=[ref_name],
            search_type="relationship",
            max_results=3,
            include_schema=False,
        )
        print_results(f"Relationship Search for '{ref_name}'", results)

    # Example 5: Complexity search for complex schemas
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["complex"],
        search_type="complexity",
        max_results=3,
        include_schema=False,
        filters={"min_depth": 3, "min_properties": 10},
    )
    print_results("Complexity Search for Complex Schemas", results, detailed=True)

    # Example 6: Complexity search for simple schemas
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["simple"],
        search_type="complexity",
        max_results=3,
        include_schema=False,
        filters={"max_depth": 2, "max_properties": 5},
    )
    print_results("Complexity Search for Simple Schemas", results, detailed=True)

    # Example 7: Multiple terms in general search
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["network", "security", "configuration"],
        search_type="general",
        max_results=5,
        include_schema=False,
    )
    print_results("Multi-term General Search", results)

    # Example 7.1: Search terms with spaces
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["security group", "vpc configuration"],
        search_type="general",
        max_results=3,
        include_schema=False,
    )
    print_results("Search with Spaces in Terms", results)

    # Example 8: Get the most deeply nested schemas
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=["all"],  # Special term to match all schemas
        search_type="complexity",
        max_results=3,
        include_schema=False,
        filters={"min_depth": 4},  # Only deeply nested schemas
    )
    print_results("Most Deeply Nested Schemas", results, detailed=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-combined-json-or-schema-dir>")
        sys.exit(1)

    schema_path = sys.argv[1]
    if not os.path.exists(schema_path):
        print(f"Error: Path '{schema_path}' does not exist")
        sys.exit(1)

    run_examples(schema_path)
