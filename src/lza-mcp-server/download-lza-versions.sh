#!/bin/bash

# Exit on error
set -e

LZA_MIN_VERSION="$1"
LZA_MAX_VERSION="$2"
LZA_REPO_URL="$3"

echo "==================================================="
echo "Starting LZA multi-version download and processing"
echo "==================================================="

# Fetch all releases from GitHub API
echo "Fetching releases from GitHub API..."
RELEASES_JSON=$(curl -s "https://api.github.com/repos/awslabs/landing-zone-accelerator-on-aws/releases?per_page=100")

# Extract all release tags
ALL_TAGS=$(echo "$RELEASES_JSON" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

# Determine the max version (latest if not specified)
if [ -z "$LZA_MAX_VERSION" ]; then
    LZA_MAX_VERSION=$(echo "$RELEASES_JSON" | grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
    echo "No max version specified, using latest: $LZA_MAX_VERSION"
else
    echo "Using specified max version: $LZA_MAX_VERSION"
fi

# Check if min version is specified
if [ -z "$LZA_MIN_VERSION" ]; then
    echo "Error: LZA_MIN_VERSION must be specified"
    exit 1
fi

echo "Min version: $LZA_MIN_VERSION"
echo "Max version: $LZA_MAX_VERSION"
echo ""

# Create output directory for all versions
mkdir -p /app/json-schemas

# Flag to track if we're in the version range
IN_RANGE=false
VERSIONS_TO_PROCESS=()

# Build list of versions to process (from latest to oldest in the API response)
for TAG in $ALL_TAGS; do
    # Check if we've reached the max version
    if [ "$TAG" = "$LZA_MAX_VERSION" ]; then
        IN_RANGE=true
    fi
    
    # Add to processing list if in range
    if [ "$IN_RANGE" = true ]; then
        VERSIONS_TO_PROCESS+=("$TAG")
    fi
    
    # Stop if we've reached the min version
    if [ "$TAG" = "$LZA_MIN_VERSION" ]; then
        break
    fi
done

# Check if we found any versions
if [ ${#VERSIONS_TO_PROCESS[@]} -eq 0 ]; then
    echo "Error: No versions found between $LZA_MIN_VERSION and $LZA_MAX_VERSION"
    exit 1
fi

echo "Found ${#VERSIONS_TO_PROCESS[@]} version(s) to process:"
printf '%s\n' "${VERSIONS_TO_PROCESS[@]}"
echo ""

# Process each version
for VERSION in "${VERSIONS_TO_PROCESS[@]}"; do
    echo "---------------------------------------------------"
    echo "Processing version: $VERSION"
    echo "---------------------------------------------------"
    
    # Create temp directory for this version
    TEMP_DIR="/app/lza-temp/$VERSION"
    mkdir -p "$TEMP_DIR"
    
    # Clone the specific version
    echo "Cloning $VERSION..."
    git clone --branch "$VERSION" --depth 1 "$LZA_REPO_URL" "$TEMP_DIR"
    
    # Extract JSON schemas for this version
    JSON_SOURCE_DIR="/app/json-source-$VERSION"
    JSON_OUTPUT_DIR="/app/json-schemas/$VERSION"
    
    mkdir -p "$JSON_SOURCE_DIR"
    mkdir -p "$JSON_OUTPUT_DIR"
    
    # Copy JSON schema files
    JSON_SCHEMAS_PATH="$TEMP_DIR/source/packages/@aws-accelerator/config/lib/schemas"
    if [ -d "$JSON_SCHEMAS_PATH" ]; then
        echo "Copying JSON schema files..."
        cp -r "$JSON_SCHEMAS_PATH"/* "$JSON_SOURCE_DIR/"
        
        # Process JSON files and resolve references
        echo "Processing JSON files and resolving references..."
        python3 json-schema/src/resolve_refs.py --input-dir "$JSON_SOURCE_DIR" --output-dir "$JSON_OUTPUT_DIR"
        
        echo "✓ Version $VERSION processed successfully"
        echo "  Output: $JSON_OUTPUT_DIR"
    else
        echo "⚠ Warning: JSON schemas path not found for $VERSION"
        echo "  Expected: $JSON_SCHEMAS_PATH"
    fi
    
    # Clean up temp and source directories for this version
    rm -rf "$TEMP_DIR"
    rm -rf "$JSON_SOURCE_DIR"
    
    echo ""
done

echo "==================================================="
echo "All versions processed successfully!"
echo "JSON schemas available in: /app/json-schemas/"
echo "==================================================="
