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

# Run locally
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

### MCP Server Configuration

The LZA MCP server can be configured for use with any MCP-compatible client (Amazon Q, Claude Desktop, Kiro IDE, etc.).

#### Minimum Required Configuration

Add this configuration to your MCP settings file. Replace the placeholder paths with your actual system paths:

**For Kiro IDE**: `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (global)
**For Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
**For Amazon Q**: `~/.aws/amazonq/mcp.json`

```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "command": "<REPO_PATH>/scripts/extract-aws-credentials.sh",
      "args": [
        "docker",
        "run",
        "--rm",
        "-i",
        "-v",
        "<CONFIG_PATH>:/app/lza-config:rw",
        "-e",
        "LZA_CONFIG_HOST_PATH=<CONFIG_PATH>",
        "-e",
        "AWS_ACCESS_KEY_ID",
        "-e",
        "AWS_SECRET_ACCESS_KEY",
        "-e",
        "AWS_SESSION_TOKEN",
        "-e",
        "AWS_REGION",
        "-e",
        "FASTMCP_LOG_LEVEL=DEBUG",
        "lza-mcp-server:local"
      ],
      "env": {
        "AWS_PROFILE": "<YOUR_AWS_PROFILE>",
        "AWS_REGION": "<YOUR_AWS_REGION>"
      },
      "disabled": false,
      "autoApprove": [
        "getMinimumConfiguration",
        "checkAwsConnectivity",
        "searchJsonSchema",
        "getFullSchema",
        "getPipelineStatus",
        "getConfigurationFromS3",
        "diagnosePipelineErrors",
        "releasePipeline",
        "uploadConfigurationToS3"
      ]
    }
  }
}
```

#### Configuration Placeholders

Replace these placeholders with your actual values:

- `<REPO_PATH>`: Full path to your cloned lza-mcp-server repository
  - Example: `/Users/username/repos/lza-mcp-server`
  - Windows: `C:/Users/username/repos/lza-mcp-server`

- `<CONFIG_PATH>`: Full path where LZA configurations will be stored/retrieved
  - Example: `/Users/username/Documents/lza-config`
  - Windows: `C:/Users/username/Documents/lza-config`
  - This directory will be created automatically if it doesn't exist

- `<YOUR_AWS_PROFILE>`: Your AWS CLI profile name
  - Example: `default`, `lza-admin`, `production`
  - Must be configured in `~/.aws/credentials`

- `<YOUR_AWS_REGION>`: Your AWS home region
  - Example: `us-east-1`, `eu-west-1`, `ap-southeast-2`

#### Environment Variables

The configuration uses these important environment variables:

- **LZA_CONFIG_HOST_PATH**: Path on your local system where configurations are stored
  - Must match the volume mount path before `:/app/lza-config`
  - Used by the MCP server to provide correct file paths in responses

- **AWS_PROFILE**: AWS credentials profile to use
- **AWS_REGION**: Default AWS region for operations
- **FASTMCP_LOG_LEVEL**: Logging level (DEBUG, INFO, WARNING, ERROR)

#### Auto-Approved Tools

The `autoApprove` list includes read-only and safe operations that don't modify your AWS environment:
- Configuration retrieval and inspection
- Schema searches
- Pipeline status checks
- AWS connectivity verification

Tools that modify AWS resources (like `releasePipeline` and `uploadConfigurationToS3`) can be added to auto-approve if desired, but require explicit approval by default for safety.

#### Example Configuration (macOS)

```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "command": "/Users/jsmith/repos/lza-mcp-server/scripts/extract-aws-credentials.sh",
      "args": [
        "docker",
        "run",
        "--rm",
        "-i",
        "-v",
        "/Users/jsmith/Documents/lza-config:/app/lza-config:rw",
        "-e",
        "LZA_CONFIG_HOST_PATH=/Users/jsmith/Documents/lza-config",
        "-e",
        "AWS_ACCESS_KEY_ID",
        "-e",
        "AWS_SECRET_ACCESS_KEY",
        "-e",
        "AWS_SESSION_TOKEN",
        "-e",
        "AWS_REGION",
        "-e",
        "FASTMCP_LOG_LEVEL=DEBUG",
        "lza-mcp-server:local"
      ],
      "env": {
        "AWS_PROFILE": "lza-admin",
        "AWS_REGION": "us-east-1"
      },
      "disabled": false,
      "autoApprove": [
        "getMinimumConfiguration",
        "checkAwsConnectivity",
        "searchJsonSchema",
        "getFullSchema",
        "getPipelineStatus",
        "getConfigurationFromS3",
        "diagnosePipelineErrors"
      ]
    }
  }
}
```

#### Restart Your MCP Client

After updating the configuration:
- **Kiro IDE**: Reload the MCP server from the MCP Server view
- **Claude Desktop**: Restart the application
- **Amazon Q**: Restart Amazon Q Developer

## AWS Permissions

The MCP server requires specific IAM permissions to interact with AWS services for LZA pipeline management, configuration operations, and schema access. Below is the recommended IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OrgStatement",
      "Effect": "Allow",
      "NotAction": [
        "organizations:DescribeAccount",
        "organizations:DescribeOrganization",
        "organizations:DescribeOrganizationalUnit",
        "organizations:ListAccounts",
        "organizations:ListAccountsForParent",
        "organizations:ListChildren",
        "organizations:ListOrganizationalUnitsForParent",
        "organizations:ListParents",
        "organizations:ListRoots"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PipelineAccess",
      "Effect": "Allow",
      "Action": [
        "codepipeline:GetPipelineExecution",
        "codepipeline:GetPipelineState",
        "codepipeline:ListActionExecutions",
        "codepipeline:ListPipelineExecutions"
      ],
      "Resource": "arn:aws:codepipeline:${HOME-REGION}:${MANAGEMENT_ACCOUNT}:${ACCELERATOR_PREFIX}-Pipeline"
    },
    {
      "Sid": "IAMStatement",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListPolicies",
        "iam:ListRolePolicies"
      ],
      "Resource": [
        "arn:${PARTITION}:iam::*:role/cdk-accel*",
        "arn:${PARTITION}:iam::*:role/${MANAGEMENT_ACCOUNT_ACCESS_ROLE}",
        "arn:aws:iam::*:role/${ACCELERATOR_PREFIX}-*"
      ]
    },
    {
      "Sid": "KmsStatement",
      "Effect": "Allow",
      "Action": [
        "kms:DescribeKey",
        "kms:ListAliases"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "ForAllValues:StringLike": {
          "kms:ResourceAliases": [
            "alias/accelerator*"
          ]
        }
      }
    },
    {
      "Sid": "S3Statement",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketEncryption",
        "s3:GetBucketVersioning",
        "s3:GetObject",
        "s3:ListBuckets",
        "s3:ListObject",
        "s3:PutBucketVersioning",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:${PARTITION}:s3:::aws-accelerator*",
        "arn:${PARTITION}:s3:::aws-accelerator*/*"
      ]
    }
  ]
}
```

### Policy Variables

Replace the following placeholders with your specific values:

- `${HOME-REGION}`: Your AWS home region (e.g., `us-east-1`)
- `${MANAGEMENT_ACCOUNT}`: Your AWS management account ID
- `${ACCELERATOR_PREFIX}`: Your LZA accelerator prefix (default: `AWSAccelerator`)
- `${PARTITION}`: AWS partition (typically `aws`, or `aws-us-gov` for GovCloud)
- `${MANAGEMENT_ACCOUNT_ACCESS_ROLE}`: Role name for cross-account access (default: `OrganizationAccountAccessRole`)

### Permission Breakdown

- **Organizations**: Read-only access to AWS Organizations for account and OU information
- **CodePipeline**: Access to monitor and manage LZA pipeline executions
- **IAM**: Read access to roles and policies used by LZA
- **KMS**: Access to KMS keys with the accelerator alias for encryption operations
- **S3**: Read/write access to LZA configuration buckets for configuration management

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
The host path is determined by the `LZA_CONFIG_HOST_PATH` environment variable in your MCP configuration:

1. **Set in MCP Configuration**: The `LZA_CONFIG_HOST_PATH` environment variable must match your volume mount path
2. **Volume Mount**: Use `-v <CONFIG_PATH>:/app/lza-config:rw` to mount your local directory
3. **Environment Variable**: Use `-e LZA_CONFIG_HOST_PATH=<CONFIG_PATH>` to tell the server where files are on your host

**Important**: Both the volume mount path and the `LZA_CONFIG_HOST_PATH` environment variable must use the same path. This ensures the MCP server provides correct file paths that work on your local system.

Example:
```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "args": [
        "docker", "run", "--rm", "-i",
        "-v", "/Users/jsmith/Documents/lza-config:/app/lza-config:rw",
        "-e", "LZA_CONFIG_HOST_PATH=/Users/jsmith/Documents/lza-config",
        ...
      ]
    }
  }
}
```

See the [MCP Server Configuration](#mcp-server-configuration) section for complete configuration examples.

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
- **S3 download failures**: Verify AWS credentials and S3 bucket permissions

## Documentation

See `deployment/README.md` for detailed deployment instructions and troubleshooting.

## License

Apache License 2.0 - see LICENSE file for details.
