# LZA JSON Reference Resolver

A tool for downloading the Landing Zone Accelerator (LZA) source code, extracting JSON files, and resolving `$ref` references within the JSON files.

## Prerequisites

- Bash shell
- Python 3.6 or later
- curl
- unzip

## Usage

The JSON schema files are automatically extracted from the downloaded source code at:
`source/packages/@aws-accelerator/config/lib/schemas`

### Processing a Specific Schema File

After running the main script, you can also resolve references for a specific schema file:

```bash
./docker-json-schema.sh
```

Where:
- `<schema_file>` is the path to the schema file to resolve (relative to the schemas directory)
- `[output_file]` (optional) is the path where the resolved schema will be saved
  - Default: `./resolved_<schema_file>` in the current directory

## How It Works

1. The script first downloads the LZA source code from the GitHub repository (or a provided URL).
2. It extracts the downloaded ZIP file to the temp directory.
3. It locates and copies the JSON schema files from the specified path (`source/packages/@aws-accelerator/config/lib/schemas`).
4. It loads all JSON files into memory to facilitate cross-file reference resolution.
5. The script resolves all `$ref` references, which could point to elements within the same file or in other files.
6. It generates comprehensive metadata for each schema, including searchable indexes and relationship information.
7. It outputs each resolved JSON file individually to the output directory, maintaining the original file structure.
8. Finally, it creates a combined JSON file containing all resolved schemas with their metadata, organized by their original file paths.

## Output

The resolved JSON files will be available in the `output` directory. Additionally, a combined file will be generated:

- `combined.json`: All JSON files combined, with all references resolved and enhanced with metadata

Each JSON file will be both individually resolved (maintaining the original directory structure) and included in the combined file.

### Enhanced Metadata

Each schema in the output now includes a comprehensive metadata section that provides:

- Basic information (title, description)
- Statistics (property count, required fields, nesting depth)
- Search index for property-based searching
- Relationship information (references to/from other schemas)

Example metadata structure:

```json
{
  "_metadata": {
    "title": "AWS Accounts Configuration",
    "description": "Configuration schema for AWS accounts",
    "statistics": {
      "propertyCount": 12,
      "requiredCount": 5,
      "referencesCount": 3,
      "nestingDepth": 4
    },
    "searchIndex": {
      "allProperties": ["accounts", "organizationalUnits"],
      "requiredProperties": ["accounts"],
      "propertyPaths": ["accounts[].name", "accounts[].email"],
      "propertyTypes": {"accounts": "array", "accounts[].name": "string"},
      "patterns": {"accounts[].email": "^[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$"},
      "enums": {"accounts[].type": ["AWS", "GovCloud", "China"]}
    },
    "relationships": {
      "references": [{"schema": "ou-config.json", "paths": ["accounts.ou"]}],
      "referencedBy": [{"schema": "organization.json", "paths": ["org.accounts"]}]
    }
  },
  // Original schema with resolved references follows...
}
```

This metadata enables powerful search and analysis capabilities when working with the schema files.

## MCP Integration: JSON Schema Search

The JSON schema search functionality has been integrated into the LZA MCP server. This implementation provides five different search types that allow users to efficiently find and explore JSON schemas.

### Available Search Tools

The MCP server provides two complementary tools for working with JSON schemas:

1. **searchJsonSchema**: Used for finding schemas that match specified criteria
2. **getFullSchema**: Used for retrieving complete schema details after finding relevant schemas

### Search Types

1. **General Search**: Searches across all metadata fields (titles, descriptions, property names)
2. **Property Search**: Finds schemas with specific properties
3. **Pattern Search**: Finds schemas using specific validation patterns (like email formats)
4. **Relationship Search**: Finds schemas that reference or are referenced by other schemas
5. **Complexity Search**: Finds schemas based on complexity metrics (nesting depth, property counts)

### Tool 1: searchJsonSchema

This tool provides concise search results to help you locate relevant schemas quickly:

```python
# Basic search
result = await searchJsonSchema(
    search_terms=["security", "permissions"],
    search_type="general",
    max_results=5
)

# Search with format options
result = await searchJsonSchema(
    search_terms=["subnet", "vpc"],
    search_type="property",
    format_level="standard",  # Options: minimal, standard, detailed
    max_results=5
)
```

#### Search Types and Examples

##### 1. General Search

Searches across all metadata fields including titles, descriptions, and property names.

```python
result = await searchJsonSchema(
    search_terms=["security", "permissions"],
    search_type="general"
)
```

##### 2. Property Search

Finds schemas that contain properties matching the search terms.

```python
result = await searchJsonSchema(
    search_terms=["vpc", "subnet"],
    search_type="property"
)
```

##### 3. Pattern Search

Finds schemas that use specific validation patterns (like regular expressions).

```python
result = await searchJsonSchema(
    search_terms=["email"],
    search_type="pattern"
)
```

##### 4. Relationship Search

Discovers schemas based on their relationships with other schemas.

```python
result = await searchJsonSchema(
    search_terms=["account"],
    search_type="relationship"
)
```

##### 5. Complexity Search

Finds schemas based on complexity metrics like nesting depth or property count.

```python
result = await searchJsonSchema(
    search_terms=["complex"],
    search_type="complexity",
    filters={
        "min_depth": 3,
        "min_properties": 10
    }
)
```

#### Advanced Search Options

##### Setting Custom Schema Path

```python
result = await searchJsonSchema(
    search_terms=["security"],
    schema_path="/path/to/custom/combined.json"
)
```

##### Formatting Search Results

```python
# Minimal results - basic information only
result = await searchJsonSchema(
    search_terms=["vpc"],
    format_level="minimal"
)

# Standard results - includes metadata when available
result = await searchJsonSchema(
    search_terms=["vpc"],
    format_level="standard"  # Default
)

# Detailed results - includes property types and extra information
result = await searchJsonSchema(
    search_terms=["vpc"],
    format_level="detailed"
)
```

##### Complexity Filters

```python
result = await searchJsonSchema(
    search_terms=["network"],
    search_type="complexity",
    filters={
        "min_depth": 2,
        "max_depth": 5,
        "min_properties": 3,
        "max_properties": 15,
        "min_required": 1,
        "max_required": 10
    }
)
```

#### Improved Search Result Format

The search results are now provided in a more concise and usable format:

```json
{
  "success": true,
  "message": "Found 10 matches for 'vpc, subnet' (showing 5)",
  "search_info": {
    "terms": ["vpc", "subnet"],
    "type": "property",
    "total_matches": 10,
    "returned_matches": 5
  },
  "results": [
    {
      "rank": 1,
      "path": "network-config.json",
      "score": 8.5,
      "title": "Network Configuration Schema",
      "description": "Schema for defining VPC and network configurations",
      "match_locations": [
        "partial:centralNetworkServices.ipams",
        "partial:vpcs[].subnets[].ipamAllocation"
      ],
      "schema_ref": "network-config.json"
    },
    // More results...
  ]
}
```

### Tool 2: getFullSchema

After finding relevant schemas using searchJsonSchema, use this tool to retrieve complete schema details or specific properties within a schema:

```python
# Get full schema details using the schema_ref from search results
full_schema = await getFullSchema(
    schema_path="network-config.json",
    include_metadata=True
)

# Or get a specific property within the schema
property_schema = await getFullSchema(
    schema_path="network-config.json",
    property_path="centralNetworkServices.ipams",
    include_metadata=True
)
```

#### getFullSchema Result Format

For full schema requests:
```json
{
  "success": true,
  "schema_path": "network-config.json",
  "metadata": {
    "title": "Network Configuration Schema",
    "description": "Schema for defining VPC and network configurations",
    "statistics": {
      // Schema statistics...
    }
  },
  "schema": {
    // Complete JSON schema...
  }
}
```

For property-specific requests:
```json
{
  "success": true,
  "schema_path": "network-config.json",
  "property_path": "centralNetworkServices.ipams",
  "property": {
    // Specific property schema...
  },
  "schema_metadata": {
    // Schema metadata if requested...
  }
}
```

## Optimized Schema Search Workflow

To efficiently explore schemas, follow this workflow to focus on specific properties:

### 1. Search for Relevant Schemas

Start with a broad search to find schemas containing your topics of interest:

```python
search_result = await searchJsonSchema(
    search_terms=["ipam", "vpc"],
    search_type="general",
    format_level="standard"
)
```

### 2. Extract Property Paths from match_locations

The most valuable information in search results is often the `match_locations` array, which tells you exactly where your search terms appear in the schema:

```python
if search_result["results"]:
    # Get match locations from the top result
    match_locations = search_result["results"][0]["match_locations"]
    schema_ref = search_result["results"][0]["schema_ref"]
    
    # Example match_location: "property:centralNetworkServices.ipams:substring"
    # The middle part between the colons is the property path
    print("Matching locations:", match_locations)
```

### 3. Extract Property Path from match_location

Parse the match locations to extract specific property paths:

```python
# Find match locations most relevant to your interest
relevant_matches = [loc for loc in match_locations if "ipam" in loc]

if relevant_matches:
    # Match locations have format like "property:path.to.property:match_type"
    # Extract the middle part (the property path)
    property_path = relevant_matches[0].split(":", 2)[1]
    print(f"Found relevant property path: {property_path}")
```

### 4. Get Targeted Schema Information

Instead of retrieving the entire schema, get just the specific property you need:

```python
property_details = await getFullSchema(
    schema_path=schema_ref,
    property_path=property_path  # Pass the specific property path
)

# Now you have focused information about just the relevant property
print(f"Property details: {property_details['property']}")
```

### Complete Optimized Workflow Example

This example shows the complete optimized workflow:

```python
# Step 1: Search for schemas related to IPAM
search_result = await searchJsonSchema(
    search_terms=["ipam", "vpc"],
    search_type="property",
    max_results=3,
    format_level="standard"
)

# Step 2: Analyze match_locations to find specific properties
if search_result["results"]:
    result = search_result["results"][0]
    schema_ref = result["schema_ref"]
    match_locations = result["match_locations"]
    
    print(f"Found schema: {schema_ref} (score: {result['score']})")
    print(f"Match locations: {match_locations}")
    
    # Step 3: Extract property path from match_location
    # Find the most relevant property path by looking for key terms
    relevant_matches = [loc for loc in match_locations if "ipam" in loc]
    
    if relevant_matches:
        # Extract property path (the part between "property:" and ":substring")
        property_path = relevant_matches[0].split(":", 2)[1]
        print(f"Focusing on property path: {property_path}")
        
        # Step 4: Get specific property details
        property_details = await getFullSchema(
            schema_path=schema_ref,
            property_path=property_path
        )
        
        # Now you have focused information about just the property you care about
        print(f"Property details: {property_details['property']}")
    else:
        # Fallback to full schema if no specific property found
        full_schema = await getFullSchema(schema_path=schema_ref)
        print(f"Retrieved full schema: {full_schema['schema_path']}")
```

This approach gives you precisely targeted information without retrieving and parsing the entire schema, making it much more efficient and avoiding response size limitations.

### Benefits of the Two-Tool Approach

1. **Better Search Experience**:
   - Search results provide just enough information to evaluate relevance
   - Avoid hitting response size limits with large schemas
   - Find schemas quickly without wading through full definitions

2. **Detailed Schema Access When Needed**:
   - Get the complete schema only when you need the details
   - Include or exclude metadata as needed
   - Clearer separation of concerns between search and schema retrieval

### Implementation Details

The implementation consists of the following components:

- **searchJsonSchema**: MCP tool that provides all search capabilities with improved result formatting
- **getFullSchema**: MCP tool for retrieving complete schema details
- **schema_search.py**: Core search implementation (existing file)
- **search.py**: Command-line interface for local use (existing file)

## Command-Line Schema Search

The `search.py` script provides a command-line interface for searching:

```bash
python src/search.py output/combined.json --terms '["vpc","subnet"]' --type property --max-results 5 --summarize
```

Command-line options:
- `--terms`: Search terms in JSON array format (must be a valid JSON array)
- `--type`: Search type (general, property, pattern, relationship, complexity)
- `--max-results`: Maximum number of results to return
- `--output`: Save results to a JSON file
- `--no-metadata`: Exclude metadata from results
- `--no-schema`: Exclude schema from results
- `--summarize`: Print a human-readable summary of results

### Command-Line Examples

Try out different search types with the example script:

```bash
python src/search_examples.py output/combined.json
```

## Direct Programmatic Usage

You can also use the search functionality directly in your Python code:

```python
from schema_search import search_json_schemas

# General search for "security" related schemas
results = search_json_schemas(
    schema_path="output/combined.json",
    search_terms=["security"],
    search_type="general",
    max_results=5
)
```

## Resolving $ref References

The process of resolving `$ref` references involves:

1. Finding all instances of `$ref` in the JSON files
2. For each reference, locating the target JSON element (which might be in another file)
3. Replacing the `$ref` property with the contents of the referenced element
4. Handling circular references to prevent infinite loops

### Circular References

The tool detects circular references and provides detailed console output when they occur:

```
⚠️ Circular reference detected and skipped: path/to/reference
   In file: schema/file.json
   At path: root.properties.object
   Reference chain: previous/reference/path, another/reference/path
```

When a circular reference is detected:
- The original `$ref` property is preserved in the output
- Processing continues with other properties
- Detailed logging helps identify and troubleshoot circular reference issues

## Limitations

- The current implementation assumes references are correctly formatted
- It handles cross-file references based on relative paths
- Circular references are detected but not fully resolved (they are maintained as `$ref` references)