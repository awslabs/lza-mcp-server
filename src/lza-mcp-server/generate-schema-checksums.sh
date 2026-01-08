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

# Generate SHA-256 checksums for all LZA schema files
# This implements T-015 (Template and schema integrity validation)

set -e

SCHEMA_DIR="${1:-/app/json-schemas}"
OUTPUT_FILE="${2:-$SCHEMA_DIR/checksums.sha256}"

echo "==================================================="
echo "Generating schema checksums (T-015)"
echo "==================================================="
echo "Schema directory: $SCHEMA_DIR"
echo "Output file: $OUTPUT_FILE"
echo ""

if [ ! -d "$SCHEMA_DIR" ]; then
    echo "Error: Schema directory not found: $SCHEMA_DIR"
    exit 1
fi

# Create output file with header
cat > "$OUTPUT_FILE" << 'EOF'
# LZA Schema Checksums (T-015)
# Generated at build time for integrity validation
# Format: <sha256> <relative_path>
EOF

# Find all combined.json files in version directories
SCHEMA_COUNT=0

for VERSION_DIR in "$SCHEMA_DIR"/*; do
    # Skip if not a directory or is a symlink
    if [ ! -d "$VERSION_DIR" ] || [ -L "$VERSION_DIR" ]; then
        continue
    fi
    
    VERSION_NAME=$(basename "$VERSION_DIR")
    COMBINED_JSON="$VERSION_DIR/combined.json"
    
    if [ -f "$COMBINED_JSON" ]; then
        echo "Processing: $VERSION_NAME/combined.json"
        
        # Calculate checksum and get relative path
        CHECKSUM=$(sha256sum "$COMBINED_JSON" | awk '{print $1}')
        RELATIVE_PATH="$VERSION_NAME/combined.json"
        
        # Append to output file
        echo "$CHECKSUM $RELATIVE_PATH" >> "$OUTPUT_FILE"
        
        SCHEMA_COUNT=$((SCHEMA_COUNT + 1))
        echo "  Checksum: $CHECKSUM"
    fi
done

echo ""
echo "==================================================="
echo "✓ Generated checksums for $SCHEMA_COUNT schema files"
echo "==================================================="

# Display the checksum file for verification
echo ""
echo "Checksum manifest contents:"
cat "$OUTPUT_FILE"
echo ""

if [ $SCHEMA_COUNT -eq 0 ]; then
    echo "Warning: No schema files found!"
    exit 1
fi

exit 0
