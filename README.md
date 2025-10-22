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
- **setupS3Bucket**: Create and configure S3 buckets for LZA configuration storage

### Configuration Management
- **getMinimumConfiguration**: Generate minimal LZA configuration templates
- **uploadConfigurationToS3**: Upload configuration files to S3 bucket

### Configuration Validation
- **validateConfigurationFromS3**: Validate LZA configurations stored in S3 buckets
- **validateConfigurationFromShare**: Validate configurations using Docker shared volumes
- **cleanupValidationZip**: Clean up temporary validation files after upload

### Pipeline Management
- **releasePipeline**: Start the LZA pipeline execution (standalone)
- **releasePipelineAfterUpload**: Trigger pipeline execution after configuration upload (workflow integration)
- **getPipelineStatus**: Get current pipeline status and progress
- **diagnosePipelineErrors**: Retrieve logs for failed pipeline executions

### Schema Search
- **searchJsonSchema**: Search LZA configuration schemas by terms, properties, patterns, or complexity
- **getFullSchema**: Retrieve complete schema details or specific properties

## Configuration Validation

The server provides two methods for validating LZA configurations before deployment.

### S3-Based Validation

Validates configurations stored in S3 buckets (recommended for production):

```bash
# 1. Check AWS connectivity
checkAwsConnectivity()

# 2. Create/verify S3 bucket
setupS3Bucket()

# 3. Upload configuration ZIP to S3
aws s3 cp config.zip s3://your-bucket/config.zip

# 4. Validate from S3
validateConfigurationFromS3(s3_path="s3://your-bucket/config.zip")
```

### Local Shared Volume Validation

Validates configurations using Docker shared volumes (for local development):

```bash
# 1. Create ZIP of configuration directory
cd /path/to/config && zip -r ~/Documents/lza-config/config.zip .

# 2. Run validation with shared volume
validateConfigurationFromShare(local_share_path="~/Documents/lza-config")

# 3. Clean up after successful upload
cleanupValidationZip()
```

### Validation Requirements

- ZIP files must contain the complete configuration directory structure
- Include all subdirectories and supporting files (IAM policies, SCP policies, etc.)
- Use `zip -r config.zip .` from within the configuration directory
- Ensure all referenced files are included in the ZIP

## Pipeline Deployment

After validating and uploading your configuration, deploy changes using the pipeline tools.

### Standalone Pipeline Execution

Use `releasePipeline` to manually trigger the pipeline at any time:

```bash
# Start pipeline execution
releasePipeline(pipeline_name="AWSAccelerator-Pipeline")

# Check status
getPipelineStatus(pipeline_name="AWSAccelerator-Pipeline")
```

### Workflow-Integrated Pipeline Execution

Use `releasePipelineAfterUpload` as part of the upload workflow:

```bash
# 1. Upload configuration
uploadConfigurationToS3(config_path="/path/to/config", bucket_name="my-bucket")

# 2. Trigger pipeline with confirmation workflow
releasePipelineAfterUpload(pipeline_name="AWSAccelerator-Pipeline")
```

The workflow-integrated version provides additional confirmation steps and error handling designed for the complete upload-to-deployment workflow.

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

### Validation Issues
- **ZIP file errors**: Ensure ZIP contains complete directory structure with `zip -r config.zip .`
- **Missing files**: Include all subdirectories and referenced files (IAM policies, SCP policies)
- **S3 download failures**: Verify AWS credentials and S3 bucket permissions
- **Shared volume access**: Ensure Docker container has volume mount `-v ~/Documents/lza-config:/app/lza-config`

## Documentation

See `deployment/README.md` for detailed deployment instructions and troubleshooting.

## License

Apache License 2.0 - see LICENSE file for details.
