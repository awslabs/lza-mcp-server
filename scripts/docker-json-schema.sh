#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Configuration
LZA_REPO_URL="https://github.com/awslabs/landing-zone-accelerator-on-aws/archive/refs/heads/main.zip"
TEMP_DIR="temp"
OUTPUT_DIR="src/lza-mcp-server/json-output"
SCHEMA_PATH="source/packages/@aws-accelerator/config/lib/schemas"
VERSION_FILE="$OUTPUT_DIR/.schema_version"

echo "🚀 LZA Schema Download and Processing Script"
echo "============================================="

# Clean up any existing temp directory
if [ -d "$TEMP_DIR" ]; then
    echo "🗑️  Cleaning up existing temp directory..."
    rm -rf "$TEMP_DIR"
fi

# Create directories
mkdir -p "$TEMP_DIR"
mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading LZA source code from GitHub..."
curl -L -o "$TEMP_DIR/lza-main.zip" "$LZA_REPO_URL"

echo "📦 Extracting source code..."
cd "$TEMP_DIR"
unzip -q lza-main.zip
cd ..

# Find the extracted directory (it should be landing-zone-accelerator-on-aws-main)
EXTRACTED_DIR=$(find "$TEMP_DIR" -name "landing-zone-accelerator-on-aws-*" -type d | head -1)

if [ -z "$EXTRACTED_DIR" ]; then
    echo "❌ Error: Could not find extracted LZA directory"
    exit 1
fi

echo "📂 Found extracted directory: $EXTRACTED_DIR"

# Check if schema directory exists
FULL_SCHEMA_PATH="$EXTRACTED_DIR/$SCHEMA_PATH"
if [ ! -d "$FULL_SCHEMA_PATH" ]; then
    echo "❌ Error: Schema directory not found at $FULL_SCHEMA_PATH"
    exit 1
fi

echo "🔍 Found schema directory with $(find "$FULL_SCHEMA_PATH" -name "*.json" | wc -l) JSON files"

# Process schemas using Python
echo "⚙️  Processing schemas and resolving references..."
python3 src/lza-mcp-server/json-schema/src/resolve_refs.py --input-dir "$FULL_SCHEMA_PATH" --output-dir "$OUTPUT_DIR"

# Verify output and create version file
if [ -f "$OUTPUT_DIR/combined.json" ]; then
    echo "✅ Schema processing complete!"
    
    # Create version file with timestamp and commit info
    echo "# LZA Schema Version Information" > "$VERSION_FILE"
    echo "DOWNLOAD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$VERSION_FILE"
    echo "SOURCE_URL=$LZA_REPO_URL" >> "$VERSION_FILE"
    echo "SCHEMA_COUNT=$(find "$OUTPUT_DIR" -name "*.json" -not -name "combined.json" | wc -l)" >> "$VERSION_FILE"
    
    echo "📊 Generated files:"
    echo "   - Combined schema: $OUTPUT_DIR/combined.json"
    echo "   - Individual schemas: $OUTPUT_DIR/"
    echo "   - Version info: $VERSION_FILE"
    ls -la "$OUTPUT_DIR"
else
    echo "❌ Error: combined.json not generated"
    exit 1
fi

# Clean up temp directory
echo "🗑️  Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo "🎉 LZA schema download and processing completed successfully!"