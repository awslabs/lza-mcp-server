#!/usr/bin/env python3

"""
Metadata generator for JSON schemas to support search capabilities.
This module analyzes JSON schemas and generates structured metadata.
"""

import logging
from typing import Dict, List

# Configure logging
logger = logging.getLogger("metadata_generator")


def generate_metadata(
    schema: Dict, schema_path: str, all_schemas: Dict[str, Dict]
) -> Dict:
    """
    Generate comprehensive metadata for a JSON schema.

    Args:
        schema: The JSON schema to analyze
        schema_path: The file path of the schema (for reference tracking)
        all_schemas: Dictionary of all schemas keyed by path

    Returns:
        A metadata dictionary with search-friendly information
    """
    logger.debug(f"Generating metadata for {schema_path}")

    metadata = {
        "title": extract_title(schema, schema_path),
        "description": extract_description(schema),
        "statistics": calculate_statistics(schema),
        "searchIndex": build_search_index(schema),
        "relationships": analyze_relationships(schema, schema_path, all_schemas),
    }

    return metadata


def extract_title(schema: Dict, schema_path: str) -> str:
    """Extract title from schema or infer from filename."""
    if "title" in schema:
        return schema["title"]
    # Infer from filename
    filename = schema_path.split("/")[-1].replace(".json", "")
    return " ".join(word.capitalize() for word in filename.replace("-", " ").split())


def extract_description(schema: Dict) -> str:
    """Extract description from schema."""
    return schema.get("description", "No description provided")


def calculate_statistics(schema: Dict) -> Dict:
    """Calculate various statistics about the schema."""
    property_count = count_properties(schema)
    required_count = count_required_fields(schema)
    references_count = count_references(schema)
    nesting_depth = calculate_nesting_depth(schema)

    return {
        "propertyCount": property_count,
        "requiredCount": required_count,
        "referencesCount": references_count,
        "nestingDepth": nesting_depth,
    }


def build_search_index(schema: Dict) -> Dict:
    """Build a search index from schema properties."""
    all_properties = extract_top_level_properties(schema)
    required_properties = extract_required_properties(schema)
    property_paths = extract_property_paths(schema)
    property_types = extract_property_types(schema)
    patterns = extract_patterns(schema)
    enums = extract_enums(schema)

    return {
        "allProperties": all_properties,
        "requiredProperties": required_properties,
        "propertyPaths": property_paths,
        "propertyTypes": property_types,
        "patterns": patterns,
        "enums": enums,
    }


def analyze_relationships(
    schema: Dict, schema_path: str, all_schemas: Dict[str, Dict]
) -> Dict:
    """
    Analyze schema relationships - both outbound references and inbound references.
    """
    # Find outbound references from this schema to others
    references = find_outbound_references(schema)

    # Find inbound references from other schemas to this one
    referenced_by = find_inbound_references(schema_path, all_schemas)

    return {"references": references, "referencedBy": referenced_by}


# Helper functions for property extraction


def extract_top_level_properties(schema: Dict) -> List[str]:
    """Extract top-level property names."""
    if "properties" in schema and isinstance(schema["properties"], dict):
        return list(schema["properties"].keys())
    return []


def extract_required_properties(schema: Dict) -> List[str]:
    """Extract required property names."""
    return schema.get("required", [])


def extract_property_paths(schema: Dict) -> List[str]:
    """
    Extract all property paths, including nested properties.
    Example: ["user.name", "user.email", "settings.preferences.theme"]
    """
    paths = []

    def traverse(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return

        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop_name, prop_value in obj["properties"].items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                paths.append(prop_path)
                traverse(prop_value, prop_path)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            array_path = f"{path}[]" if path else "[]"
            traverse(obj["items"], array_path)

    traverse(schema)
    return paths


def extract_property_types(schema: Dict) -> Dict[str, str]:
    """
    Extract mapping of property paths to their types.
    Example: {"user.name": "string", "settings": "object"}
    """
    type_map = {}

    def traverse(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return

        # Get type of current object if specified
        if "type" in obj and path:
            type_map[path] = obj["type"]

        # Process properties
        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop_name, prop_value in obj["properties"].items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                if "type" in prop_value:
                    type_map[prop_path] = prop_value["type"]
                traverse(prop_value, prop_path)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            array_path = f"{path}[]" if path else "[]"
            traverse(obj["items"], array_path)

    traverse(schema)
    return type_map


def extract_patterns(schema: Dict) -> Dict[str, str]:
    """
    Extract regular expression patterns from string properties.
    Example: {"user.email": "^[a-z]+@[a-z]+\\.[a-z]+$"}
    """
    patterns = {}

    def traverse(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return

        # Check for pattern in current object
        if "pattern" in obj and path:
            patterns[path] = obj["pattern"]

        # Process properties
        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop_name, prop_value in obj["properties"].items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                traverse(prop_value, prop_path)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            array_path = f"{path}[]" if path else "[]"
            traverse(obj["items"], array_path)

    traverse(schema)
    return patterns


def extract_enums(schema: Dict) -> Dict[str, List[str]]:
    """
    Extract enum values from properties.
    Example: {"status": ["active", "inactive"]}
    """
    enums = {}

    def traverse(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return

        # Check for enum in current object
        if "enum" in obj and path:
            enums[path] = obj["enum"]

        # Process properties
        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop_name, prop_value in obj["properties"].items():
                prop_path = f"{path}.{prop_name}" if path else prop_name
                traverse(prop_value, prop_path)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            array_path = f"{path}[]" if path else "[]"
            traverse(obj["items"], array_path)

    traverse(schema)
    return enums


# Relationship analysis functions


def find_outbound_references(schema: Dict) -> List[Dict]:
    """
    Find references from this schema to other schemas.
    Returns a list of dictionaries with schema and paths.
    """
    references = {}

    def traverse(obj: Dict, path: str = ""):
        if not isinstance(obj, dict):
            return

        # Check for $ref in current object
        if "$ref" in obj:
            ref_value = obj["$ref"]
            # Only consider external references (file paths)
            if ref_value.startswith("./") or "/" in ref_value:
                ref_schema = extract_schema_from_ref(ref_value)
                if ref_schema not in references:
                    references[ref_schema] = {"schema": ref_schema, "paths": []}
                if path:
                    references[ref_schema]["paths"].append(path)

        # Continue traversing
        for key, value in obj.items():
            if isinstance(value, dict):
                new_path = f"{path}.{key}" if path else key
                traverse(value, new_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        new_path = f"{path}.{key}[{i}]" if path else f"{key}[{i}]"
                        traverse(item, new_path)

    traverse(schema)
    return list(references.values())


def find_inbound_references(
    schema_path: str, all_schemas: Dict[str, Dict]
) -> List[Dict]:
    """
    Find references from other schemas to this schema.
    Returns a list of dictionaries with schema and paths.
    """
    referenced_by = {}
    target_schema = schema_path.split("/")[-1]  # Just the filename

    for path, schema in all_schemas.items():
        if path == schema_path:
            continue  # Skip self

        # Find references to the target schema
        def traverse(obj: Dict, obj_path: str = ""):
            if not isinstance(obj, dict):
                return

            # Check for $ref in current object
            if "$ref" in obj:
                ref_value = obj["$ref"]
                if target_schema in ref_value:
                    if path not in referenced_by:
                        referenced_by[path] = {"schema": path, "paths": []}
                    if obj_path:
                        referenced_by[path]["paths"].append(obj_path)

            # Continue traversing
            for key, value in obj.items():
                if isinstance(value, dict):
                    new_path = f"{obj_path}.{key}" if obj_path else key
                    traverse(value, new_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            new_path = (
                                f"{obj_path}.{key}[{i}]" if obj_path else f"{key}[{i}]"
                            )
                            traverse(item, new_path)

        traverse(schema)

    return list(referenced_by.values())


def extract_schema_from_ref(ref: str) -> str:
    """Extract schema filename from a $ref value."""
    if "#" in ref:
        ref = ref.split("#")[0]
    if "/" in ref:
        ref = ref.split("/")[-1]
    return ref


# Statistical functions


def count_properties(schema: Dict) -> int:
    """Count all properties in the schema including nested ones."""
    count = 0

    def traverse(obj):
        nonlocal count
        if not isinstance(obj, dict):
            return

        if "properties" in obj and isinstance(obj["properties"], dict):
            count += len(obj["properties"])
            for prop in obj["properties"].values():
                traverse(prop)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            traverse(obj["items"])

    traverse(schema)
    return count


def count_required_fields(schema: Dict) -> int:
    """Count all required fields in the schema including nested ones."""
    count = 0

    def traverse(obj):
        nonlocal count
        if not isinstance(obj, dict):
            return

        if "required" in obj and isinstance(obj["required"], list):
            count += len(obj["required"])

        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop in obj["properties"].values():
                traverse(prop)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            traverse(obj["items"])

    traverse(schema)
    return count


def count_references(schema: Dict) -> int:
    """Count all $ref occurrences in the schema."""
    count = 0

    def traverse(obj):
        nonlocal count
        if not isinstance(obj, dict):
            return

        if "$ref" in obj:
            count += 1

        for value in obj.values():
            if isinstance(value, dict):
                traverse(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse(item)

    traverse(schema)
    return count


def calculate_nesting_depth(schema: Dict) -> int:
    """Calculate the maximum nesting depth of the schema."""

    def traverse(obj, current_depth=0):
        if not isinstance(obj, dict):
            return current_depth

        max_depth = current_depth

        if "properties" in obj and isinstance(obj["properties"], dict):
            for prop in obj["properties"].values():
                if isinstance(prop, dict):
                    depth = traverse(prop, current_depth + 1)
                    max_depth = max(max_depth, depth)

        # Handle array items
        if "items" in obj and isinstance(obj["items"], dict):
            depth = traverse(obj["items"], current_depth + 1)
            max_depth = max(max_depth, depth)

        return max_depth

    return traverse(schema)
