#!/usr/bin/env python3

"""
JSON $ref Resolver for LZA JSON files

This script processes JSON files, identifies $ref references,
and resolves them by replacing with the actual content.
"""

import os
import json
import argparse
import glob
import logging
import sys

from metadata_generator import generate_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("json_resolver")


def load_json_file(file_path):
    """Load a JSON file and return its contents."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {file_path}")
        return None
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading {file_path}: {str(e)}")
        return None


def save_json_file(file_path, data):
    """Save data to a JSON file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved resolved JSON to {file_path}")


# This function has been replaced by inline code in main()


def resolve_ref(ref_path, combined_json, current_file):
    """
    Resolve a $ref reference in the JSON.
    Example ref: "$ref": "../../path/to/file.json#/properties/name"
    """
    if not ref_path.startswith("#"):
        # Reference to another file
        parts = ref_path.split("#")
        file_path = parts[0]

        # Handle relative paths
        if file_path.startswith(".."):
            # Convert relative path to absolute based on current file
            current_dir = os.path.dirname(current_file)
            file_path = os.path.normpath(os.path.join(current_dir, file_path))
            # Make it relative to the JSON root directory
            # (this depends on how your files are structured)

        if file_path not in combined_json:
            logger.warning(f"Referenced file not found: {file_path}")
            return None

        target_json = combined_json[file_path]

        # If there's a JSON path component, navigate to it
        if len(parts) > 1 and parts[1]:
            json_path = parts[1].lstrip("/")
            path_parts = json_path.split("/")

            for part in path_parts:
                if part and part in target_json:
                    target_json = target_json[part]
                else:
                    logger.warning(f"JSON path not found: {json_path} in {file_path}")
                    return None

        return target_json
    else:
        # Reference within the same file
        json_path = ref_path[1:].lstrip("/")
        target_json = combined_json[current_file]
        path_parts = json_path.split("/")

        for part in path_parts:
            if part and part in target_json:
                target_json = target_json[part]
            else:
                logger.warning(f"JSON path not found: {json_path} in {current_file}")
                return None

        return target_json


def process_json_object(
    obj, combined_json, current_file, processed_refs=None, path="root"
):
    """
    Recursively process a JSON object, resolving any $ref references.

    Args:
        obj: The JSON object to process
        combined_json: Dictionary of all JSON files keyed by file path
        current_file: The current file being processed
        processed_refs: Set of references already processed in this branch
        path: Current JSON path for better error reporting
    """
    if processed_refs is None:
        processed_refs = set()

    if isinstance(obj, dict):
        # Copy to avoid modifying during iteration
        items = list(obj.items())

        for key, value in items:
            if key == "$ref":
                if value in processed_refs:
                    logger.warning(
                        f"⚠️ Circular reference detected and skipped: {value}"
                    )
                    logger.warning(f"   In file: {current_file}")
                    logger.warning(f"   At path: {path}")
                    logger.warning(f"   Reference chain: {', '.join(processed_refs)}")
                    # Keep the $ref in place when circular
                    continue

                processed_refs.add(value)
                resolved = resolve_ref(value, combined_json, current_file)

                if resolved is not None:
                    # Remove the $ref key
                    del obj["$ref"]

                    # If resolved is a dict, merge its keys with the current object
                    if isinstance(resolved, dict):
                        for k, v in resolved.items():
                            if k not in obj:  # Don't overwrite existing keys
                                obj[k] = process_json_object(
                                    v,
                                    combined_json,
                                    current_file,
                                    processed_refs.copy(),
                                )
                    else:
                        # If resolved is not a dict, replace the current object with resolved
                        return resolved

            elif isinstance(value, (dict, list)):
                obj[key] = process_json_object(
                    value,
                    combined_json,
                    current_file,
                    processed_refs.copy(),
                    f"{path}.{key}" if path else key,
                )

    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = process_json_object(
                obj[i],
                combined_json,
                current_file,
                processed_refs.copy(),
                f"{path}[{i}]",
            )

    return obj


def resolve_references_with_metadata(combined_json):
    """
    Resolve all $ref references in the combined JSON and generate metadata.
    """
    # First pass: resolve all references
    resolved_json = {}

    for file_path, json_data in combined_json.items():
        logger.info(f"Resolving references in {file_path}")
        resolved_data = process_json_object(
            obj=json_data.copy(),  # Create a copy to not modify the original
            combined_json=combined_json,
            current_file=file_path,
            path=f"#{file_path}",  # Start path with the file name
        )
        resolved_json[file_path] = resolved_data

    # Second pass: generate metadata for each schema
    logger.info("Generating metadata for all schemas...")
    enhanced_json = {}

    for file_path, resolved_data in resolved_json.items():
        # Generate metadata for this schema
        metadata = generate_metadata(
            schema=resolved_data, schema_path=file_path, all_schemas=resolved_json
        )

        # Add metadata to the resolved schema
        enhanced_json[file_path] = {
            "_metadata": metadata,
            **resolved_data,  # Unpack the resolved schema after metadata
        }

    logger.info("Metadata generation complete")
    return enhanced_json


def main():
    parser = argparse.ArgumentParser(
        description="Resolve $ref references in JSON files"
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing JSON files"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory for resolved JSON files"
    )
    parser.add_argument(
        "--combined-output", default=None, help="Output file for combined JSON"
    )
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Load all JSON files into memory (without saving combined file yet)
    combined_json = {}
    json_files = glob.glob(os.path.join(args.input_dir, "**", "*.json"), recursive=True)

    logger.info(f"Found {len(json_files)} JSON files")

    for file_path in json_files:
        relative_path = os.path.relpath(file_path, args.input_dir)
        data = load_json_file(file_path)
        if data:
            combined_json[relative_path] = data

    # Resolve references
    resolved_json = resolve_references_with_metadata(combined_json)

    # Output each resolved file separately
    for file_path, data in resolved_json.items():
        output_path = os.path.join(args.output_dir, file_path)
        save_json_file(output_path, data)

    # Save the fully resolved combined file at the end
    combined_file = args.combined_output or os.path.join(
        args.output_dir, "combined.json"
    )
    save_json_file(combined_file, resolved_json)

    logger.info(f"All references resolved. Output saved to {args.output_dir}")


if __name__ == "__main__":
    main()
