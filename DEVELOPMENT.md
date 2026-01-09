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
            ├── pipeline_tools.py # Pipeline management
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
# Check if schemas were created
docker run --rm lza-mcp-server:latest ls -la /app/json-schemas/

# Check schema processing logs during build
docker build --progress=plain -t lza-mcp-server:debug . 2>&1 | grep -A 10 -B 10 "json-schema"
```

**Note**: Distroless images don't have shell. Use single commands or copy files out for inspection.

**Search Not Working**:
```bash
# Copy schema file out for inspection
docker cp container-name:/app/json-schemas/v1.12.0/ ./local-schemas/

# Check logs for search errors
docker logs container-name 2>&1 | grep -i schema
```

**Note**: Distroless images don't have Python CLI access. Use logs and file extraction for debugging.

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

#### Input Validation Patterns

**All MCP tools MUST validate inputs at entry point.** Use validation utilities from `utils/input_validation.py`:

```python
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    validate_file_path,
    validate_s3_bucket_name,
    validate_s3_key,
    validate_pipeline_name,
    validate_execution_id,
)

@mcp.tool()
async def example_tool(ctx: Context, name: str, bucket: str, file_path: str):
    # VALIDATE FIRST - all inputs must be validated before processing
    is_valid, error = validate_string_input(name, "name", min_length=1, max_length=100)
    if not is_valid:
        return {"success": False, "error": error}
    
    is_valid, error = validate_s3_bucket_name(bucket)
    if not is_valid:
        return {"success": False, "error": error}
    
    is_valid, error = validate_file_path(file_path, base_directory=Path("/app/config"))
    if not is_valid:
        return {"success": False, "error": error}
    
    # THEN PROCESS - only after all validation passes
    ...
```

**Validation Patterns:**

| Validator | Pattern | Purpose |
|-----------|---------|---------|
| `validate_s3_bucket_name()` | `^[a-z0-9][a-z0-9.-]*[a-z0-9]$` (3-63 chars) | AWS S3 bucket naming rules |
| `validate_s3_key()` | No `..`, no leading `/`, max 1024 bytes | Prevent path traversal |
| `validate_file_path()` | No `..`, no absolute paths, within base_directory | Prevent path traversal |
| `validate_pipeline_name()` | `^[A-Za-z0-9._-]+$` (1-100 chars) | AWS CodePipeline naming |
| `validate_execution_id()` | UUID format (36 chars) | AWS execution ID format |
| `validate_session_id()` | `^uc-session-\d{8}-\d{6}$` | UC merge session format |
| `validate_lza_version()` | `^v?\d+\.\d+\.\d+$` | Semantic version format |
| `validate_email()` | RFC 5321 email format | Email validation |
| `validate_account_id()` | `^\d{12}$` | AWS account ID (12 digits) |
| `sanitize_command_argument()` | Removes shell metacharacters | Prevent command injection |

**Test coverage:** Run `make test-coverage` to verify validation coverage.

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

# Check container contents (distroless - no shell)
docker run --rm lza-mcp-server:dev ls -la /app/json-schemas/
```

#### Manual Testing Scenarios

Test these key workflows to validate functionality:

1. **AWS Connectivity**: `Check my AWS connectivity`
2. **Configuration Generation**: `Generate a minimum viable LZA configuration`
3. **Configuration Retrieval**: `Retrieve my current LZA configuration from S3`
4. **Schema Discovery**: `Search for VPC-related configuration options`
5. **Pipeline Management**: `Show me the status of my LZA pipeline`

For detailed testing procedures, coverage analysis, and troubleshooting, see [TESTING.md](TESTING.md).

### 3. Code Quality

#### Code Style

- **Follow PEP 8** Python style guidelines
- **Use type hints** for all function parameters and return values
- **Write comprehensive docstrings** with examples
- **Use meaningful variable names** and clear logic flow

#### Security Scanning

**Container Vulnerability Scanning (Optional):**

Scan Docker images for security vulnerabilities using Trivy:

```bash
# Install Trivy (one-time setup)
brew install trivy

# Scan container for vulnerabilities
make scan-container

# Or run without installing Trivy locally
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image lza-mcp-server:local --severity HIGH,CRITICAL
```

Trivy scans for:
- OS package vulnerabilities
- Python dependency vulnerabilities (complements pip-audit)
- Base image security issues
- Known CVEs

**Code Security Scanning (Required):**

Run before committing code:

```bash
# Complete pre-commit verification (includes Bandit + pip-audit)
make release
```

This runs:
- Bandit - Python code security analysis
- pip-audit - Dependency vulnerability scanning
- Plus: linting, formatting, type checking, and tests

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
  - `get_config_s3.py`: Retrieve and extract configurations from S3
  - `manage_config_tools.py`: Tool registration and coordination
  - `common.py`: Shared configuration utilities

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

#### Distroless Container Debugging

The production image uses distroless base (no shell) for security. Debugging requires different approaches:

```bash
# View logs (primary debugging method)
docker logs -f container-name

# Copy files out for inspection
docker cp container-name:/app/file.log ./local-file.log

# Check running processes
docker top container-name

# Inspect container configuration
docker inspect container-name
```

**Note**: Cannot use `docker exec -it container /bin/bash` with distroless images. For interactive debugging, temporarily switch to `python:3.11-slim` base in the builder stage's final FROM line.

### Debugging Tools

- **MCP Inspector**: Test MCP protocol compliance
- **Docker logs**: View container output and errors (primary method for distroless)
- **AWS CLI**: Test AWS operations independently
- **File extraction**: Copy files from container for inspection

## Performance Optimization

### Best Practices

- **Reuse AWS sessions** across operations
- **Stream large files** instead of loading into memory
- **Use async/await** for I/O operations
- **Clean up temporary files** promptly
- **Cache expensive operations** when appropriate

### Monitoring

- **Log performance metrics** for tool operations
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

- **Use distroless base images** to minimize attack surface (T-007 mitigation)
- **Multi-stage builds** separate build tools from runtime
- **Don't run as root** - distroless runs as nonroot user (uid 65532)
- **Scan images** for vulnerabilities
- **Keep dependencies updated**

## Future Development

### Planned Features

1. **Enhanced Schema Search**: More sophisticated search algorithms
2. **Template Management**: User-defined configuration templates
3. **Batch Operations**: Process multiple configurations simultaneously
4. **Integration APIs**: RESTful API in addition to MCP protocol
5. **Enhanced Error Diagnostics**: More detailed pipeline error analysis

### Extension Points

- **Custom Validators**: Plugin system for organization-specific rules
- **Template Engines**: Support for different configuration formats
- **Notification Systems**: Integration with monitoring and alerting
- **Analytics**: Usage tracking and performance analytics

---

**Navigation**: [← Architecture](ARCHITECTURE.md) | [README](README.md) | [Setup](SETUP.md) | [Usage](USAGE.md) | [Advanced](ADVANCED.md) | [Testing](TESTING.md)