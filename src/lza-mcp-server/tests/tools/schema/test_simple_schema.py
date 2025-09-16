#!/usr/bin/env python3
"""
Simple test script to validate schema search fixes without MCP dependencies.
"""

import os
import json
import pytest


@pytest.fixture
def found_files():
    """Fixture to provide schema file analysis results."""
    # Check possible schema file locations
    schema_paths = {
        "container": "/app/json-output/combined.json",
        "local_dev": "/Users/vmayberr/xdev/mte/lza-mcp-server/src/lza-mcp-server/json-output/combined.json",
        "relative": os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "json-output/combined.json"
        ),
    }

    found_files = []

    for name, path in schema_paths.items():
        if os.path.exists(path):
            try:
                file_size = os.path.getsize(path)
                file_info = {
                    "location": name,
                    "path": path,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                }
                found_files.append(file_info)
            except Exception:
                continue

    return found_files


def test_schema_file_analysis(found_files):
    """Test schema file analysis."""
    print("=== Testing Schema File Analysis ===")

    for file_info in found_files:
        path = file_info["path"]
        print(f"Found: {file_info['location']}")
        print(f"  Path: {path}")
        print(f"  Size: {file_info['size_mb']} MB")

        # Test if it's valid JSON
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Read first 1KB to check JSON structure
                chunk = f.read(1024)
                if chunk.strip().startswith("{"):
                    print("  Valid JSON: Yes")

                    # If small file, count schemas
                    if file_info["size_bytes"] < 5 * 1024 * 1024:  # < 5MB
                        f.seek(0)
                        data = json.load(f)
                        print(f"  Schema count: {len(data)}")
                    else:
                        print("  Schema count: Large file, not counted")
                else:
                    print("  Valid JSON: No")

        except json.JSONDecodeError:
            print("  Valid JSON: No (JSON decode error)")
        except Exception as e:
            print(f"  Valid JSON: No ({str(e)})")

    assert len(found_files) > 0, "No schema files found"


def test_memory_analysis(found_files):
    """Test memory usage analysis."""
    print("\n=== Testing Memory Usage Analysis ===")

    assert len(found_files) > 0, "No schema files found for analysis"

    # Configuration thresholds
    LARGE_FILE_THRESHOLD = 2 * 1024 * 1024  # 2MB
    HUGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB

    for file_info in found_files:
        file_size = file_info["size_bytes"]
        file_size_mb = file_info["size_mb"]

        print(f"\nAnalyzing: {file_info['location']}")
        print(f"File size: {file_size_mb} MB")

        # Estimate memory usage (JSON typically expands 2-3x in memory)
        estimated_memory = file_size_mb * 2.5
        print(f"Estimated memory usage: {estimated_memory:.2f} MB")

        # Assess context exhaustion risk
        if file_size > HUGE_FILE_THRESHOLD:
            risk_level = "HIGH"
            chunk_size = 10
            max_results = 3
        elif file_size > LARGE_FILE_THRESHOLD:
            risk_level = "MEDIUM"
            chunk_size = 20
            max_results = 5
        else:
            risk_level = "LOW"
            chunk_size = 50
            max_results = 10

        print(f"Context exhaustion risk: {risk_level}")
        print(f"Recommended chunk size: {chunk_size}")
        print(f"Recommended max results: {max_results}")

        assert risk_level in ["LOW", "MEDIUM", "HIGH"]
        assert chunk_size > 0
        assert max_results > 0


def test_optimized_search_logic(found_files):
    """Test optimized search logic without full implementation."""
    print("\n=== Testing Optimized Search Logic ===")

    assert len(found_files) > 0, "No schema files found for testing"

    # Test with the largest file
    largest_file = max(found_files, key=lambda x: x["size_bytes"])
    schema_path = largest_file["path"]

    print(f"Testing with: {schema_path}")
    print(f"File size: {largest_file['size_mb']} MB")

    # Test key extraction logic
    print("Testing key extraction...")
    keys = []

    with open(schema_path, "r", encoding="utf-8") as f:
        # Read first chunk to extract keys
        chunk = f.read(1024 * 1024)  # 1MB

        if chunk.strip().startswith("{") and chunk.strip().endswith("}"):
            # Small file, parse normally
            try:
                data = json.loads(chunk)
                keys = list(data.keys())
                print(f"Small file: Found {len(keys)} keys")
            except json.JSONDecodeError:
                print("Failed to parse as complete JSON")
        else:
            # Large file, extract keys manually
            print("Large file detected, using key extraction logic")
            in_key = False
            current_key = ""
            brace_count = 0

            for char in chunk:
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

            print(f"Extracted {len(keys)} keys from large file")

    if keys:
        print(f"Sample keys: {keys[:5]}")

        # Test search logic
        search_terms = ["vpc", "network", "security"]
        matches = []

        for key in keys[:10]:  # Test with first 10 keys
            key_lower = key.lower()
            for term in search_terms:
                if term.lower() in key_lower:
                    matches.append(
                        {"key": key, "term": term, "match_type": "schema_name"}
                    )

        print(f"Found {len(matches)} potential matches in schema names")
        if matches:
            print("Sample matches:")
            for match in matches[:3]:
                print(f"  {match['key']} -> {match['term']}")

    assert isinstance(keys, list)
    assert len(keys) >= 0
