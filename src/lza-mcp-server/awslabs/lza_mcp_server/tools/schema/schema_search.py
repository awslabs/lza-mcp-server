"""
Mock schema_search module for testing purposes.
This module provides a mock implementation of schema search functionality.
"""


def search_json_schemas(search_terms=None, **kwargs):
    """Mock schema search function that returns realistic test data."""
    if not search_terms:
        search_terms = ["default"]

    results = []
    for term in search_terms:
        results.append(
            {
                "path": f"{term}-config-schema.json",
                "relevance_score": 0.9,
                "match_locations": [f"property:{term}:substring"],
                "_metadata": {
                    "title": f"{term.title()} Configuration Schema",
                    "description": f"Schema for LZA {term} configuration",
                },
            }
        )

    return {"total_matches": len(results), "results": results}


# For backward compatibility
def search_schemas(*args, **kwargs):
    """Alias for search_json_schemas."""
    return search_json_schemas(*args, **kwargs)
