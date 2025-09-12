# AWS Landing Zone Accelerator (LZA) MCP Server

An AWS Labs Model Context Protocol (MCP) server for AWS Landing Zone Accelerator pipeline management.

## Features

- **Pipeline Management**: Start, monitor, and diagnose LZA pipeline executions
- **Schema Search**: Search and explore LZA JSON configuration schemas
- **Cross-Account Support**: Works with LZA deployments in different AWS accounts
- **Container Support**: Containerized deployment using Finch for local development and AWS Lambda deployment
- **Amazon Q Integration**: Compatible with Amazon Q Developer for AI-assisted operations

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
cd src/lza-mcp-server
pip install -e .
```

2. **Download LZA schemas:**
```bash
make download-schema
```

3. **Configure AWS credentials:**
```bash
aws configure
# or set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
```

4. **Run the server:**
```bash
python -m server
```

### Container Deployment

#### For AWS Lambda Deployment
```bash
# Download schemas and build Lambda-compatible image
make download-schema
finch build -t lza-mcp-server:lambda .
```

#### For Local Development
```bash
# Build local development image
finch build -f Dockerfile.local -t lza-mcp-server:local .

# Run locally
finch run -p 8000:8000 -v ~/.aws:/home/lzauser/.aws:ro lza-mcp-server:local
```

#### Using Finch Compose
```bash
# Start Finch VM if not running
finch vm start

# Build and run using docker-compose (uses Dockerfile.local)
finch compose up --build

# Or build manually with local dockerfile
finch build -f Dockerfile.local -t lza-mcp-server:local .
```

### Amazon Q Integration

1. **Copy the MCP configuration:**
```bash
cp mcp-config.json ~/.aws/amazonq/mcp.json
```

2. **Update paths in the configuration file to match your setup**

3. **Restart Amazon Q Developer**

## AWS Permissions

## Schema Management

The server includes automated LZA schema management that downloads and processes the latest schema files from the official LZA repository.

### Automated Schema Download

Schemas are automatically downloaded as part of the release process:

```bash
# Download schemas only
make download-schema

# Full release (includes schema download)
make release

# Clean schema files
make clean-schema
```

### How It Works

1. **Download**: Fetches the latest LZA source code from GitHub
2. **Extract**: Extracts JSON schema files from `source/packages/@aws-accelerator/config/lib/schemas`
3. **Process**: Resolves `$ref` references and generates metadata
4. **Output**: Creates `json-output/combined.json` with all schemas and metadata
5. **Version**: Tracks download timestamp and source information

### Schema Files Location

- **Development**: `json-output/combined.json`
- **Container**: `/app/json-output/combined.json`
- **Version Info**: `json-output/.schema_version`

## Available Tools

### Pipeline Management
- **releasePipeline**: Start the LZA pipeline execution
- **getPipelineStatus**: Get current pipeline status and progress
- **diagnosePipelineErrors**: Retrieve logs for failed pipeline executions

### Schema Search
- **searchJsonSchema**: Search LZA configuration schemas by terms, properties, patterns, or complexity
- **getFullSchema**: Retrieve complete schema details or specific properties

## Troubleshooting

### Schema Issues
- **Schema file not found**: Run `make download-schema` to download the latest schemas
- **Search returns no results**: Verify `json-output/combined.json` exists and contains data
- **Outdated schemas**: Run `make clean-schema && make download-schema` to refresh
- **Network issues**: Check internet connectivity for GitHub access during schema download

### Container Issues
- **Finch VM not started**: Run `finch vm start` before using Finch commands
- **Build context errors**: Ensure you're running commands from the correct directory with all required files
- **AWS credentials warnings**: Set environment variables or use AWS credential files
- **Local vs Lambda builds**: Use `Dockerfile.local` for local development, default `Dockerfile` for Lambda deployment
- **Missing schema in container**: Ensure `make download-schema` was run before building the Docker image

## Documentation

See `deployment/README.md` for detailed deployment instructions and troubleshooting.

## License

Apache License 2.0 - see LICENSE file for details.
