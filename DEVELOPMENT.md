# LZA MCP Server Development Guide

Guide for contributing to and extending the AWS Landing Zone Accelerator MCP Server.

## Development Setup

### Prerequisites

- **Python 3.10+** - For local development and testing
- **Docker** - For building and testing containers
- **Poetry** or **pip** - For Python dependency management
- **Git** - For version control
- **AWS CLI** - For testing AWS integrations

### Local Development Environment

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd lza-mcp-server
   ```

2. **Set up Python environment**:
   ```bash
   cd src/lza-mcp-server
   
   # Using Poetry (recommended)
   poetry install
   poetry shell
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Install MCP dependencies**:
   ```bash
   pip install mcp[cli]>=1.6.0
   ```

4. **Set up AWS credentials** for testing:
   ```bash
   aws configure
   # or
   export AWS_PROFILE=your-profile
   ```

### Project Structure

```
lza-mcp-server/
├── README.md                    # Main documentation
├── SETUP.md                     # Setup instructions
├── USAGE.md                     # Usage guide
├── ARCHITECTURE.md              # Technical architecture
├── DEVELOPMENT.md               # This file
├── mcp-config.json              # MCP client configuration
├── docker-json-schema.sh        # JSON schema processing script
└── src/lza-mcp-server/          # Main source code
    ├── pyproject.toml           # Python project configuration
    ├── Dockerfile               # Container build instructions
    ├── server.py                # Entry point script
    ├── json-schema/             # JSON schema processing pipeline
    │   ├── README.md            # Schema processing documentation
    │   └── src/                 # Schema processing modules
    │       ├── resolve_refs.py  # Reference resolution
    │       ├── metadata_generator.py # Metadata generation
    │       ├── schema_search.py # Search implementation
    │       └── search.py        # Command-line interface
    └── awslabs/lza_mcp_server/  # Main Python package
        ├── __init__.py          # Package initialization
        ├── __main__.py          # Module entry point
        ├── server.py            # MCP server implementation
        ├── utils.py             # Shared utilities
        └── tools/               # Tool implementations
            ├── __init__.py      # Tools package
            ├── aws_tools.py     # AWS connectivity and S3
            ├── config_tools.py  # Configuration generation
            ├── validation_tools.py # Validation workflows
            └── schema_tools.py  # Schema search and discovery
```

## JSON Schema Build Process

The LZA MCP Server includes a sophisticated JSON schema processing pipeline that runs during Docker container build. This process creates searchable, enhanced schemas that power the `searchJsonSchema` and `getFullSchema` tools.

### Schema Processing Pipeline

The JSON schema processing happens automatically during `docker build` via the `docker-json-schema.sh` script:

1. **Schema Extraction**: Extracts JSON schemas from the LZA source code at `source/packages/@aws-accelerator/config/lib/schemas`
2. **Reference Resolution**: Resolves all `$ref` references across schema files using `resolve_refs.py`
3. **Metadata Generation**: Creates comprehensive metadata for each schema
4. **Schema Combination**: Combines all processed schemas into `combined.json`

### Build Process Flow

```bash
# During Docker build, this script runs automatically:
./docker-json-schema.sh

# Which performs these steps:
# 1. Copy schemas from LZA source to /app/json-source
# 2. Run Python processing: resolve_refs.py --input-dir /app/json-source --output-dir /app/json-output
# 3. Generate /app/json-output/combined.json with all processed schemas
```

### Schema Enhancement Features

The processing pipeline adds several enhancements to the raw LZA schemas:

#### 1. Reference Resolution
- Resolves all `$ref` references within and across schema files
- Handles circular references gracefully
- Creates self-contained schema definitions

#### 2. Metadata Generation
Each schema gets enhanced with comprehensive metadata:

```json
{
  "_metadata": {
    "title": "Network Configuration Schema",
    "description": "Schema for defining VPC and network configurations",
    "statistics": {
      "propertyCount": 45,
      "requiredCount": 8,
      "referencesCount": 12,
      "nestingDepth": 6
    },
    "searchIndex": {
      "allProperties": ["vpcs", "transitGateways", "centralNetworkServices"],
      "requiredProperties": ["homeRegion"],
      "propertyPaths": ["vpcs[].subnets[].name", "vpcs[].subnets[].ipamAllocation"],
      "propertyTypes": {"vpcs": "array", "vpcs[].name": "string"},
      "patterns": {"vpcs[].cidr": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"},
      "enums": {"vpcs[].region": ["us-east-1", "us-west-2", "eu-central-1"]}
    },
    "relationships": {
      "references": [{"schema": "accounts-config.json", "paths": ["vpcs.account"]}],
      "referencedBy": [{"schema": "security-config.json", "paths": ["networkFirewall.vpcs"]}]
    }
  }
}
```

#### 3. Search Optimization
- Pre-computed property indexes for fast searching
- Multiple search strategies (general, property, pattern, relationship, complexity)
- Relevance scoring and match location tracking

### Working with Schema Processing

#### Modifying Schema Processing
If you need to modify the schema processing logic:

1. **Edit processing scripts** in `json-schema/src/`:
   - `resolve_refs.py`: Reference resolution logic
   - `metadata_generator.py`: Metadata generation
   - `schema_search.py`: Search implementation

2. **Test locally**:
   ```bash
   cd src/lza-mcp-server
   # Run the processing pipeline manually
   ./docker-json-schema.sh
   
   # Test search functionality
   python json-schema/src/search.py /app/json-output/combined.json --terms '["vpc"]' --type property
   ```

3. **Rebuild container** to test changes:
   ```bash
   docker build -t lza-mcp-server:dev .
   ```

#### Debugging Schema Issues

**Schema Not Found Errors**:
```bash
# Check if combined.json was created
docker run --rm -it lza-mcp-server:latest ls -la /app/json-output/

# Check schema processing logs
docker build --progress=plain -t lza-mcp-server:debug . 2>&1 | grep -A 10 -B 10 "json-schema"
```

**Search Not Working**:
```bash
# Test search module directly
docker run --rm -it lza-mcp-server:latest python3 -c "
from json_schema.src.schema_search import search_json_schemas
result = search_json_schemas('/app/json-output/combined.json', ['vpc'], 'general', 5)
print(result)
"
```

#### Schema Processing Performance

The schema processing adds approximately 30-60 seconds to the Docker build time but provides significant runtime benefits:

- **Fast Search**: Pre-processed indexes enable sub-second search responses
- **Rich Metadata**: Comprehensive schema information without runtime analysis
- **Resolved References**: Complete schema definitions without cross-file lookups

## Development Workflow

### 1. Making Changes

#### Adding New Tools

1. **Choose the appropriate module**:
   - AWS operations → `tools/aws_services/`
   - Configuration generation and retrieval → `tools/config/`
   - Validation workflows → `tools/validation/`
   - Schema operations → `tools/schema/`
   - Pipeline management → `tools/pipeline/`

2. **Implement the tool**:
   ```python
   @mcp.tool(name="newToolName")
   async def new_tool(
       ctx: Context,
       parameter: str,
       optional_param: Optional[int] = None
   ) -> Dict[str, Any]:
       """Tool description with comprehensive documentation.
       
       Detailed explanation of what the tool does, when to use it,
       and any important considerations.
       
       Args:
           parameter (str): Description of required parameter
           optional_param (int, optional): Description of optional parameter
           
       Returns:
           Dictionary containing the tool's results
           
       Examples:
       
       Basic usage:
       ```python
       result = await newToolName(parameter="value")
       ```
       """
       await ctx.info(f"Starting new tool with parameter: {parameter}")
       
       try:
           # Tool implementation
           result = perform_operation(parameter, optional_param)
           
           await ctx.info("Tool completed successfully")
           return {
               "success": True,
               "result": result
           }
           
       except Exception as e:
           await ctx.error(f"Tool failed: {str(e)}")
           return {
               "success": False,
               "error": str(e)
           }
   ```

3. **Register the tool** in the module's `register_*_tools()` function

#### Modifying Existing Tools

1. **Update the tool function** with your changes
2. **Update the docstring** if the interface changes
3. **Test the changes** thoroughly
4. **Update documentation** if needed

### 2. Testing

The LZA MCP Server uses comprehensive testing with automated coverage tracking and performance optimization. For complete testing documentation, see [TESTING.md](TESTING.md).

#### Quick Testing Commands

```bash
cd src/lza-mcp-server

# Complete test suite with coverage
make test-coverage

# Fast development testing (unit tests only)
make test-fast

# Integration tests with AWS services
make test-integration

# Generate coverage dashboard
make coverage-dashboard
```

#### Development Testing Workflow

```bash
# 1. Run syntax validation
python -m py_compile awslabs/lza_mcp_server/tools/*.py

# 2. Run unit tests during development
pytest tests/ -k "not integration" -v

# 3. Run integration tests before commits
export AWS_PROFILE=your-profile
pytest tests/ -k "integration" -v

# 4. Check coverage before PR
pytest tests/ --cov=awslabs.lza_mcp_server --cov-report=term
```

#### Docker Testing

```bash
# Build and test Docker image
docker build -t lza-mcp-server:dev .

# Test with MCP Inspector
npx @modelcontextprotocol/inspector docker run --rm -it lza-mcp-server:dev

# Test schema processing
docker run --rm -it lza-mcp-server:dev python3 -c "
import sys
sys.path.append('/app/json-schema/src')
from schema_search import search_json_schemas
result = search_json_schemas('/app/json-output/combined.json', ['vpc'], 'general', 3)
print(f'Found {result[\"total_matches\"]} matches')
"
```

#### Manual Testing Scenarios

Test these key workflows to validate functionality:

1. **AWS Connectivity**: `Check my AWS connectivity`
2. **Configuration Generation**: `Generate a minimum viable LZA configuration`
3. **Configuration Retrieval**: `Retrieve my current LZA configuration from S3`
4. **Validation Workflow**: `Validate my LZA configuration from s3://bucket/config.zip`
5. **Schema Discovery**: `Search for VPC-related configuration options`

For detailed testing procedures, coverage analysis, and troubleshooting, see [TESTING.md](TESTING.md).

### 3. Code Quality

#### Code Style

- **Follow PEP 8** Python style guidelines
- **Use type hints** for all function parameters and return values
- **Write comprehensive docstrings** with examples
- **Use meaningful variable names** and clear logic flow

#### Documentation Standards

- **Tool docstrings** must include:
  - Clear description of purpose
  - Detailed parameter documentation
  - Return value description
  - At least one usage example
  - When to use the tool

- **Code comments** for complex logic
- **Update documentation files** when adding features

#### Error Handling

- **Use try/catch blocks** for all external operations
- **Provide helpful error messages** with troubleshooting guidance
- **Log errors appropriately** with context
- **Return structured error responses**

## Architecture Guidelines

### Tool Design Principles

1. **Single Responsibility**: Each tool should have one clear purpose
2. **Comprehensive Documentation**: Rich docstrings with examples
3. **Error Handling**: Graceful failure with helpful messages
4. **Progress Reporting**: Use `ctx.info()` and `ctx.error()` for user feedback
5. **Consistent Interface**: Follow established patterns for parameters and returns

### Module Organization

- **AWS Tools** (`tools/aws_services/`): Operations that interact with AWS services
  - `check_aws_connectivity.py`: AWS credential verification
  - `s3_upload_utils.py`: S3 upload operations
  - `common.py`: Shared AWS utilities

- **Config Tools** (`tools/config/`): Configuration generation, retrieval, and management
  - `get_minimum_configuration.py`: Generate minimal LZA configurations
  - `upload_config_s3.py`: Upload configurations to S3
  - `get_config_s3.py`: **NEW** - Retrieve and extract configurations from S3
  - `manage_config_tools.py`: Tool registration and coordination
  - `common.py`: Shared configuration utilities

- **Validation Tools** (`tools/validation/`): Configuration validation workflows
  - `validation_tools.py`: Validation and cleanup operations (includes unified `cleanupConfiguration`)

- **Schema Tools** (`tools/schema/`): Schema discovery and analysis
  - `search_json_schema.py`: Search LZA configuration schemas
  - `get_full_schema.py`: Retrieve complete schema details
  - `manage_schema_tools.py`: Tool registration

- **Pipeline Tools** (`tools/pipeline/`): Pipeline management and monitoring
  - `release_pipeline.py`: Start pipeline executions
  - `get_pipeline_status.py`: Monitor pipeline progress
  - `diagnose_pipeline_errors.py`: Retrieve error logs

- **Utils**: Shared functionality used across modules
  - `error_handling.py`: Structured error responses
  - `utils.py`: Common utilities

### Dependencies

- **Minimize external dependencies** to reduce container size
- **Use standard library** when possible
- **Document new dependencies** in `pyproject.toml`
- **Consider security implications** of new packages

## Building and Deployment

### Docker Build

```bash
# Standard build
docker build -t lza-mcp-server:latest .

# Development build with debugging
docker build --build-arg LOG_LEVEL=DEBUG -t lza-mcp-server:dev .

# Multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t lza-mcp-server:latest .
```

### Release Process

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG** with new features and fixes
3. **Test thoroughly** with multiple MCP clients
4. **Build and tag** Docker image
5. **Update documentation** as needed

## Contributing

### Pull Request Process

1. **Fork the repository** and create a feature branch
2. **Make your changes** following the development guidelines
3. **Test your changes** thoroughly
4. **Update documentation** if needed
5. **Submit a pull request** with clear description

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] All tools have comprehensive docstrings
- [ ] Error handling is implemented properly
- [ ] Changes are tested with Docker build
- [ ] Documentation is updated if needed
- [ ] No breaking changes to existing tools

## Debugging

### Common Issues

#### Import Errors
```bash
# Check Python path
export PYTHONPATH=/path/to/lza-mcp-server/src/lza-mcp-server

# Verify imports
python -c "from awslabs.lza_mcp_server import main; print('Success')"
```

#### Docker Build Issues
```bash
# Clean build cache
docker system prune -f

# Build with verbose output
docker build --progress=plain --no-cache -t lza-mcp-server:debug .
```

#### MCP Integration Issues
```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector docker run --rm -it lza-mcp-server:latest

# Enable debug logging
docker run --rm -it -e FASTMCP_LOG_LEVEL=DEBUG lza-mcp-server:latest
```

### Debugging Tools

- **MCP Inspector**: Test MCP protocol compliance
- **Docker logs**: View container output and errors
- **AWS CLI**: Test AWS operations independently
- **Python debugger**: Use `pdb` for step-through debugging

## Performance Optimization

### Best Practices

- **Reuse AWS sessions** across operations
- **Stream large files** instead of loading into memory
- **Use async/await** for I/O operations
- **Clean up temporary files** promptly
- **Cache expensive operations** when appropriate

### Monitoring

- **Log performance metrics** for validation operations
- **Monitor memory usage** during large file processing
- **Track AWS API call patterns** to optimize costs
- **Measure tool execution times**

## Security Considerations

### Development Security

- **Never commit credentials** to version control
- **Use environment variables** for sensitive configuration
- **Validate all inputs** thoroughly
- **Follow least privilege principle** for AWS permissions

### Container Security

- **Use minimal base images** to reduce attack surface
- **Don't run as root** in containers
- **Scan images** for vulnerabilities
- **Keep dependencies updated**

## Future Development

### Planned Features

1. **Enhanced Schema Search**: More sophisticated search algorithms
2. **Configuration Validation**: Additional validation rules and checks
3. **Template Management**: User-defined configuration templates
4. **Batch Operations**: Process multiple configurations simultaneously
5. **Integration APIs**: RESTful API in addition to MCP protocol

### Extension Points

- **Custom Validators**: Plugin system for organization-specific rules
- **Template Engines**: Support for different configuration formats
- **Notification Systems**: Integration with monitoring and alerting
- **Analytics**: Usage tracking and performance analytics

---

**Navigation**: [← Architecture](ARCHITECTURE.md) | [README](README.md) | [Setup](SETUP.md) | [Usage](USAGE.md) | [Advanced](ADVANCED.md) | [Testing](TESTING.md)