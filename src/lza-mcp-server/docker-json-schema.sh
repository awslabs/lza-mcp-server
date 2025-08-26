#!/bin/bash

# Exit on error
set -e

# Define default variables
DEFAULT_JSON_SCHEMA_PATH="source/packages/@aws-accelerator/config/lib/schemas"
LZA_EXTRACTED_DIR="${LZA_VALIDATOR_SHARE_PATH:-/app/lza}"
JSON_SOURCE_DIR="/app/json-source"
JSON_OUTPUT_DIR="/app/json-output"

# Copy the JSON schema files to a separate directory for processing
mkdir -p "$JSON_SOURCE_DIR"

echo "Copying JSON schema files from $DEFAULT_JSON_SCHEMA_PATH..."
JSON_SCHEMAS_PATH="$LZA_EXTRACTED_DIR/$DEFAULT_JSON_SCHEMA_PATH"
if [ -d "$JSON_SCHEMAS_PATH" ]; then
    cp -r "$JSON_SCHEMAS_PATH"/* "$JSON_SOURCE_DIR/"
    echo "JSON schema files copied successfully to $JSON_SOURCE_DIR"
else
    echo "Error: JSON schemas path not found at $JSON_SCHEMAS_PATH"
    echo "Directory structure of extracted source:"
    find "$LZA_EXTRACTED_DIR" -type d -maxdepth 3
    exit 1
fi

# Step 2: Process the JSON files and resolve references
echo "Step 2: Processing JSON files and resolving references..."
python3 json-schema/src/resolve_refs.py --input-dir "$JSON_SOURCE_DIR" --output-dir "$JSON_OUTPUT_DIR"

echo ""
echo "==================================================="
echo "Process completed successfully!"
echo "Resolved JSON files are available in the output directory"
echo "==================================================="