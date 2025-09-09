#!/usr/bin/env python3

"""
Helper script to resolve a specific schema file with $ref references
"""

import os
import sys
import argparse
from resolve_refs import load_json_file, save_json_file, process_json_object
from metadata_generator import generate_metadata


def resolve_specific_schema(schema_path, output_path, schemas_dir):
    """
    Resolve a specific schema file with $ref references
    """
    # Load the target schema
    schema_data = load_json_file(schema_path)
    if not schema_data:
        print(f"Error: Could not load schema file {schema_path}")
        return False

    # Load all schemas into a dictionary keyed by file path
    combined_json = {}
    for root, _, files in os.walk(schemas_dir):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                # Make path relative to schemas_dir
                relative_path = os.path.relpath(file_path, schemas_dir)
                json_data = load_json_file(file_path)
                if json_data:
                    combined_json[relative_path] = json_data

    # Get the relative path of the target schema for reference resolution
    schema_relative_path = os.path.relpath(schema_path, schemas_dir)

    # Resolve references in the target schema
    resolved_schema = process_json_object(
        obj=schema_data.copy(),
        combined_json=combined_json,
        current_file=schema_relative_path,
        path=f"#{schema_relative_path}",
    )

    # Generate metadata for the resolved schema
    print(f"Generating metadata for {schema_relative_path}")
    metadata = generate_metadata(
        schema=resolved_schema,
        schema_path=schema_relative_path,
        all_schemas=combined_json,
    )

    # Add metadata to the resolved schema
    enhanced_schema = {
        "_metadata": metadata,
        **resolved_schema,  # Unpack the resolved schema after metadata
    }

    # Save the resolved schema with metadata
    save_json_file(output_path, enhanced_schema)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Resolve $ref references in a specific schema file"
    )
    parser.add_argument(
        "--schema", required=True, help="Path to the schema file to resolve"
    )
    parser.add_argument(
        "--schemas-dir", required=True, help="Directory containing all schema files"
    )
    parser.add_argument(
        "--output", required=True, help="Output path for the resolved schema"
    )
    args = parser.parse_args()

    success = resolve_specific_schema(args.schema, args.output, args.schemas_dir)
    if success:
        print(f"Successfully resolved schema and saved to {args.output}")
    else:
        print("Failed to resolve schema")
        sys.exit(1)


if __name__ == "__main__":
    main()
