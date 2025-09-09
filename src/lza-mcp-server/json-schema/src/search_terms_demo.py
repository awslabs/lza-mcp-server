#!/usr/bin/env python3

"""
Test script for demonstrating different search term formats.
This helps verify the handling of search terms with spaces.
"""

import sys
import os
import json
from schema_search import search_json_schemas


def test_search_terms(schema_path):
    """
    Run tests with different search term formats.
    """
    print("\n=== Testing Different Search Term Formats ===\n")

    # Test 1: Multiple terms in JSON array
    print("Test 1: Multiple terms in JSON array")
    test1_terms = ["vpc", "subnet", "security"]
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=test1_terms,
        search_type="general",
        max_results=2,
        include_schema=False,
    )
    print(f"Search terms array: {test1_terms}")
    print(f"Found {results['total_matches']} matches")
    for i, result in enumerate(results["results"]):
        print(
            f"  Result {i + 1}: {result['path']} (Score: {result['relevance_score']:.2f})"
        )

    # Test 2: Terms with spaces
    print("\nTest 2: Terms with spaces")
    test2_terms = ["security group", "vpc configuration"]
    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=test2_terms,
        search_type="general",
        max_results=2,
        include_schema=False,
    )
    print(f"Search terms: {test2_terms}")
    print(f"Found {results['total_matches']} matches")
    for i, result in enumerate(results["results"]):
        print(
            f"  Result {i + 1}: {result['path']} (Score: {result['relevance_score']:.2f})"
        )

    # Test 3: JSON array format from command line
    # (Simulating how it would be parsed from command line)
    print("\nTest 3: JSON array format from command line")
    json_input = '["security group", "vpc configuration"]'
    try:
        test3_terms = json.loads(json_input)
        results = search_json_schemas(
            schema_path=schema_path,
            search_terms=test3_terms,
            search_type="general",
            max_results=2,
            include_schema=False,
        )
        print(f"Search terms (parsed from JSON): {test3_terms}")
        print(f"Found {results['total_matches']} matches")
        for i, result in enumerate(results["results"]):
            print(
                f"  Result {i + 1}: {result['path']} (Score: {result['relevance_score']:.2f})"
            )
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")

    # Test 4: Compare multiple separate terms vs. a single term with a space
    print("\nTest 4: Comparing ['security', 'group'] vs. ['security group']")

    # First as two separate terms in array
    test4a_terms = ["security", "group"]
    results_a = search_json_schemas(
        schema_path=schema_path,
        search_terms=test4a_terms,
        search_type="general",
        max_results=2,
        include_schema=False,
    )
    print(f"Search terms as separate in array: {test4a_terms}")
    print(f"Found {results_a['total_matches']} matches")

    # Then as a single term with space
    test4b_terms = ["security group"]
    results_b = search_json_schemas(
        schema_path=schema_path,
        search_terms=test4b_terms,
        search_type="general",
        max_results=2,
        include_schema=False,
    )
    print(f"Search terms as one term with space: {test4b_terms}")
    print(f"Found {results_b['total_matches']} matches")

    # Test 5: Space normalization
    print("\nTest 5: Space normalization - comparing 'vpc template' vs 'vpctemplate'")

    # With spaces
    test5a_terms = ["vpc template"]
    results_a = search_json_schemas(
        schema_path=schema_path,
        search_terms=test5a_terms,
        search_type="general",
        max_results=3,
        include_schema=False,
    )
    print(f"Search terms with spaces: {test5a_terms}")
    print(f"Found {results_a['total_matches']} matches")
    if results_a["results"]:
        print(
            f"  First match: {results_a['results'][0]['path']} (Score: {results_a['results'][0]['relevance_score']:.2f})"
        )
        print(f"  Match locations: {results_a['results'][0]['match_locations']}")

    # Without spaces
    test5b_terms = ["vpctemplate"]
    results_b = search_json_schemas(
        schema_path=schema_path,
        search_terms=test5b_terms,
        search_type="general",
        max_results=3,
        include_schema=False,
    )
    print(f"Search terms without spaces: {test5b_terms}")
    print(f"Found {results_b['total_matches']} matches")
    if results_b["results"]:
        print(
            f"  First match: {results_b['results'][0]['path']} (Score: {results_b['results'][0]['relevance_score']:.2f})"
        )
        print(f"  Match locations: {results_b['results'][0]['match_locations']}")

    # Test 6: Space normalization with property search
    print(
        "\nTest 6: Space normalization with property search - 'securitygroup' vs 'security group'"
    )

    # With spaces
    test6a_terms = ["security group"]
    results_a = search_json_schemas(
        schema_path=schema_path,
        search_terms=test6a_terms,
        search_type="property",
        max_results=3,
        include_schema=False,
    )
    print(f"Property search with spaces: {test6a_terms}")
    print(f"Found {results_a['total_matches']} matches")

    # Without spaces
    test6b_terms = ["securitygroup"]
    results_b = search_json_schemas(
        schema_path=schema_path,
        search_terms=test6b_terms,
        search_type="property",
        max_results=3,
        include_schema=False,
    )
    print(f"Property search without spaces: {test6b_terms}")
    print(f"Found {results_b['total_matches']} matches")

    # Test 7: Single term in JSON array
    print("\nTest 7: Single term in JSON array")

    # Single term properly wrapped in a list
    test7_terms = ["vpc"]

    results = search_json_schemas(
        schema_path=schema_path,
        search_terms=test7_terms,
        search_type="general",
        max_results=2,
        include_schema=False,
    )
    print(f"Single term in array: {test7_terms}")
    print(f"Found {results['total_matches']} matches")

    print("\n=== Tests Completed ===")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-combined-json-or-schema-dir>")
        sys.exit(1)

    schema_path = sys.argv[1]
    if not os.path.exists(schema_path):
        print(f"Error: Path '{schema_path}' does not exist")
        sys.exit(1)

    test_search_terms(schema_path)
