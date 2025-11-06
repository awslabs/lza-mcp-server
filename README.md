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

2. **Configure AWS credentials:**
```bash
aws configure
# or set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
```

3. **Run the server:**
```bash
python -m server
```

### Container Deployment

#### For AWS Lambda Deployment
```bash
# Build Lambda-compatible image (schemas generated during build)
finch build -t lza-mcp-server:lambda .
```

#### For Local Development
```bash
# Build local development image (includes LZA repo and schema generation)
make build-local

# Or build manually
finch build -f Dockerfile.local -t lza-mcp-server:local .

# Run locally with validation support
make run-local

# Or run manually
finch run -d \
  --name lza-mcp-server \
  -p 8000:8000 \
  -v ~/.aws:/home/lzauser/.aws:ro \
  -v ~/Documents/lza-config:/app/lza-config \
  lza-mcp-server:local
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

The server includes automated LZA schema management that generates schemas during Docker image build.

### Schema Generation

Schemas are automatically generated when building the Docker image:

```bash
# Build local image (generates schemas automatically)
make build-local
```

### How It Works

1. **Clone**: Docker build clones the latest LZA source code from GitHub
2. **Extract**: Extracts JSON schema files from `source/packages/@aws-accelerator/config/lib/schemas`
3. **Process**: Resolves `$ref` references and generates metadata during build
4. **Output**: Creates `json-output/combined.json` with all schemas and metadata
5. **Embed**: Schemas are embedded in the Docker image

### Schema Files Location

- **Container**: `/app/json-output/combined.json`
- **LZA Source**: `/app/lza` (cloned during build)
- **Local Development**: Schemas generated in Docker image only

## Available Tools

### AWS Services
- **checkAwsConnectivity**: Verify AWS credentials and connectivity

### Configuration Management
- **getMinimumConfiguration**: Generate minimal LZA configuration templates
- **uploadConfigurationToS3**: Upload configuration files to S3 bucket
- **getConfigurationFromS3**: Retrieve and extract current LZA configuration from S3

### Configuration Validation
- **validateConfigurationFromS3**: Validate LZA configurations stored in S3 buckets
- **validateConfigurationFromShare**: Validate configurations using Docker shared volumes
- **cleanupConfiguration**: Clean up temporary validation files and retrieved configurations (planned)

### Pipeline Management
- **releasePipeline**: Start the LZA pipeline execution
- **getPipelineStatus**: Get current pipeline status and progress
- **diagnosePipelineErrors**: Retrieve logs for failed pipeline executions

### Schema Search
- **searchJsonSchema**: Search LZA configuration schemas by terms, properties, patterns, or complexity
- **getFullSchema**: Retrieve complete schema details or specific properties

## Configuration Retrieval

The server provides tools to retrieve and inspect deployed LZA configurations from S3.

### Retrieving Current Configuration

Retrieve the currently deployed LZA configuration from S3 for inspection or comparison:

### Retrieval Workflow

The `getConfigurationFromS3` tool:
- Downloads the configuration ZIP from `zipped/aws-accelerator-config.zip` in the S3 bucket
- Extracts all files to `/app/lza-config/retrieved-config` (Docker container path)
- Returns both `container_path` and `host_path` for file access
- **LLM uses `host_path`** to inspect and read configuration files on the local system
- Returns comprehensive metadata including file counts, directory structure, and file listings
- Automatically cleans up previous retrieved configurations to keep the file system clean
- Users map their local directory (e.g., `~/Documents/lza-config`) to `/app/lza-config` in the container

**Volume Mount Configuration**:
The host path is determined by:
1. Environment variable `LZA_CONFIG_HOST_PATH` (if set in MCP server configuration)
2. Default: `~/Documents/lza-config`

To configure a custom host path, add the environment variable to your MCP server configuration:
```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/your/custom/path:/app/lza-config:rw",
        "-e", "LZA_CONFIG_HOST_PATH=/your/custom/path",
        ...
      ]
    }
  }
}
```

## Configuration Validation

The server provides two methods for validating LZA configurations before deployment.

### S3-Based Validation

Validates configurations stored in S3 buckets (recommended for production):

```bash
# 1. Check AWS connectivity
checkAwsConnectivity()

# 2. Create S3 bucket (if needed) using AWS CLI
aws s3 mb s3://your-bucket-name --region your-region

# 3. Create and upload configuration ZIP to S3
cd /path/to/config && zip -r config.zip .
aws s3 cp config.zip s3://your-bucket-name/config.zip

# 4. Validate from S3
validateConfigurationFromS3(s3_path="s3://your-bucket-name/config.zip")
```

### Local Shared Volume Validation

Validates configurations using Docker shared volumes (for local development):

```bash
# 1. Create ZIP of configuration directory
cd /path/to/config && zip -r ~/Documents/lza-config/config.zip .

# 2. Run validation with shared volume
validateConfigurationFromShare(local_share_path="~/Documents/lza-config")

# 3. Clean up after successful upload (manual cleanup if needed)
# Note: Automatic cleanup occurs on next retrieval
```

### Validation Requirements

- ZIP files must contain the complete configuration directory structure
- Include all subdirectories and supporting files (IAM policies, SCP policies, etc.)
- Use `zip -r config.zip .` from within the configuration directory
- Ensure all referenced files are included in the ZIP

## Configuration Cleanup

### Automatic Cleanup

The `getConfigurationFromS3` tool automatically cleans up the previous retrieved configuration before creating a new one. This ensures the file system stays clean without requiring manual intervention.

### Manual Cleanup

If you need to clean up a retrieved configuration directory immediately (before the next retrieval), you can manually remove it:

```bash
# From inside the Docker container
rm -rf /app/lza-config/retrieved-config

# Or from your local system (if you have the volume mounted)
rm -rf ~/Documents/lza-config/retrieved-config
```

## Pipeline Deployment

After validating and uploading your configuration, deploy changes using the pipeline tool:

```bash
# 1. Upload configuration
uploadConfigurationToS3(config_path="/path/to/config", bucket_name="my-bucket")

# 2. Start pipeline execution
releasePipeline(pipeline_name="AWSAccelerator-Pipeline")

# 3. Check status
getPipelineStatus(pipeline_name="AWSAccelerator-Pipeline")
```

## Troubleshooting

### Schema Issues
- **Schema file not found**: Rebuild Docker image with `make build-local`
- **Search returns no results**: Verify Docker image was built successfully
- **Outdated schemas**: Rebuild Docker image to get latest LZA schemas
- **Network issues during build**: Check internet connectivity for GitHub access during Docker build

### Container Issues
- **Finch VM not started**: Run `finch vm start` before using Finch commands
- **Build context errors**: Ensure you're running commands from the correct directory with all required files
- **AWS credentials warnings**: Set environment variables or use AWS credential files
- **Local vs Lambda builds**: Use `Dockerfile.local` for local development, default `Dockerfile` for Lambda deployment
- **Missing schema in container**: Schemas are generated during build - rebuild image if missing
- **Build fails during LZA clone**: Check network connectivity and GitHub access

### Configuration Retrieval Issues
- **Bucket not found**: Verify LZA has been deployed and the configuration bucket exists
- **Object not found**: Ensure configuration has been uploaded to `zipped/aws-accelerator-config.zip`
- **Invalid bucket name**: Bucket names must be 3-63 characters, lowercase, following AWS S3 naming rules
- **Permission denied**: Verify IAM permissions include `s3:GetObject` for the configuration bucket
- **Invalid ZIP file**: The downloaded file may be corrupted - check the S3 object integrity

### Validation Issues
- **ZIP file errors**: Ensure ZIP contains complete directory structure with `zip -r config.zip .`
- **Missing files**: Include all subdirectories and referenced files (IAM policies, SCP policies)
- **S3 download failures**: Verify AWS credentials and S3 bucket permissions
- **Shared volume access**: Ensure Docker container has volume mount `-v ~/Documents/lza-config:/app/lza-config`

## Documentation

See `deployment/README.md` for detailed deployment instructions and troubleshooting.

## License

Apache License 2.0 - see LICENSE file for details.
