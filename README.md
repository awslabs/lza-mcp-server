# Landing Zone Accelerator on AWS (LZA) MCP Server

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE.txt)
[![Code of Conduct](https://img.shields.io/badge/Code%20of%20Conduct-Amazon-orange.svg)](CODE_OF_CONDUCT.md)

A Model Context Protocol (MCP) server that enables AI-assisted management of [Landing Zone Accelerator on AWS](https://aws.amazon.com/solutions/implementations/landing-zone-accelerator-on-aws/) (LZA) deployments through compatible development tools and IDEs.

**Documentation:** [Contributing](CONTRIBUTING.md) | [Code of Conduct](CODE_OF_CONDUCT.md) | [Security](SECURITY.md) | [Changelog](CHANGELOG.md) | [License](LICENSE.txt)

## Table of Contents

- [Overview](#overview)
- [Privacy Notice](#privacy-notice)
- [Quick Start](#quick-start)
- [Build Process](#build-process)
- [AWS Permissions](#aws-permissions)
- [MCP Client Configuration](#mcp-client-configuration)
- [Available Tools](#available-tools)
- [Schema Management](#schema-management)
- [Universal Configuration](#universal-configuration)
- [Configuration Operations](#configuration-operations)
- [Pipeline Management](#pipeline-management)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)

## Overview

The LZA MCP Server streamlines Landing Zone Accelerator on AWS operations by providing AI-powered assistance for configuration management, pipeline orchestration, and schema discovery. Organizations can reduce operational complexity and accelerate deployment cycles while maintaining security and compliance standards. The server includes specialized tools for merging [LZA Universal Configuration](https://github.com/aws/lza-universal-configuration) templates, enabling rapid deployment of enterprise-ready, compliance-focused baseline environments.

**Key Benefits:**
- **Accelerated Operations**: AI-assisted configuration reduces manual effort and deployment time
- **Enhanced Accuracy**: Schema validation and intelligent search helping prevent configuration errors while providing a reliable tools to discover LZA capabilities
- **Operational Visibility**: Real-time pipeline monitoring with automated diagnostics
- **Security by Design**: Comprehensive input validation and least-privilege IAM policies
- **Universal Configuration Integration**: Streamlined merging of enterprise-ready compliance templates

**Architecture:**
The server operates as a containerized MCP endpoint, invoked by compatible IDEs (Kiro, Claude Desktop) via stdio transport. All AWS operations use temporary credentials following [AWS security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html).

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Privacy Notice

> **⚠️ Data Sharing with AI Providers**  
> This MCP server executes AWS API calls using your credentials and shares the response data with your third-party AI model provider (e.g., Kiro CLI, Claude Desktop, Cursor, VS Code, Kiro IDE). Users are responsible for understanding your AI provider's data handling practices and ensuring compliance with your organization's security and privacy requirements when using this tool with AWS resources.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Quick Start

### Prerequisites

- **Container Runtime**: Docker or Finch (the build process auto-detects which is available)
- AWS credentials with [required IAM permissions](#aws-permissions)
- MCP-compatible IDE (Kiro IDE, Claude Desktop)
- Existing LZA deployment (for pipeline and configuration operations)

> **📋 Supported LZA Deployments**  
> This MCP server supports LZA deployments using **S3-based configuration storage**. The default LZA deployment stores configuration files in an S3 bucket (`aws-accelerator-config-*`), which this server accesses for configuration retrieval and upload operations.
> 
> **Note:** CodeCommit-based configuration repositories are not currently supported. If your LZA deployment uses CodeCommit for configuration storage, you'll need to migrate to S3-based storage to use this MCP server. See [LZA configuration file documentation](https://docs.aws.amazon.com/solutions/latest/landing-zone-accelerator-on-aws/using-configuration-files.html) for details on configuration storage options.

### 1. Build Container Image

The build process automatically detects whether Docker or Finch is installed and uses the available runtime:

```bash
cd src/lza-mcp-server
make build
```

**Using a specific runtime:**

```bash
# Force Docker
make build CONTAINER_RUNTIME=docker

# Force Finch
make build CONTAINER_RUNTIME=finch
```

This generates a container image with embedded LZA schemas for versions v1.12.0 and later (mutable).

**What if neither is installed?**

The build will fail with a helpful error message directing you to installation resources:
- **Docker**: https://docs.docker.com/get-docker/
- **Finch**: https://github.com/runfinch/finch

### 2. Configure AWS Permissions

Create an IAM role or user with the [recommended IAM policy](#aws-permissions). The policy follows least-privilege principles and supports standard LZA deployments.

> **⚠️ Security Recommendation**  
> Use [temporary credentials via AWS IAM Identity Center](https://docs.aws.amazon.com/wellarchitected/latest/framework/sec_identities_unique.html) instead of long-term access keys. Temporary credentials reduce risk of credential exposure and align with AWS security best practices.

### 3. Configure AWS Credentials

The `extract-aws-credentials.sh` script handles credential extraction from your AWS CLI profile and passes them to the container. This script works with most AWS credential sources:

- Static credentials (access key/secret key)
- IAM Identity Center (SSO)
- IAM roles
- Credential process
- Temporary credentials

**For IAM Identity Center users**, login to your SSO session before starting the MCP server:

```bash
aws sso login --profile your-sso-profile
```

SSO sessions typically expire after 8-12 hours. If the MCP server reports authentication errors, re-run `aws sso login` to refresh your session.

The script uses `aws configure export-credentials` to retrieve temporary credentials from your active session and inject them into the container environment.

### 4. Configure MCP Client

Add the server configuration to your IDE's MCP settings file:

**Kiro IDE:** `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (global)  
**Claude Desktop:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "command": "<REPO_PATH>/scripts/extract-aws-credentials.sh",
      "args": [
        "docker", "run",
        "--security-opt=no-new-privileges:true",
        "--cap-drop=ALL",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=200m",
        "--rm", "-i",
        "-v", "<CONFIG_PATH>:/app/lza-config:rw",
        "-e", "LZA_CONFIG_HOST_PATH=<CONFIG_PATH>",
        "-e", "AWS_ACCESS_KEY_ID",
        "-e", "AWS_SECRET_ACCESS_KEY",
        "-e", "AWS_SESSION_TOKEN",
        "-e", "AWS_REGION",
        "lza-mcp-server:local"
      ],
      "env": {
        "AWS_PROFILE": "<YOUR_AWS_PROFILE>",
        "AWS_REGION": "<YOUR_AWS_REGION>"
      }
    }
  }
}
```

> **Note:** To use Finch instead of Docker, replace `"docker"` with `"finch"` in the args array.

**Configuration Parameters:**
- `<REPO_PATH>`: Full path to cloned repository (e.g., `/Users/username/repos/lza-mcp-server`)
- `<CONFIG_PATH>`: Local directory for configuration files (e.g., `/Users/username/Documents/lza-config`)
  - **Recommendation:** Place within your IDE workspace for easier file access (e.g., `.kiro/lza-config` for Kiro IDE)
- `<YOUR_AWS_PROFILE>`: AWS CLI profile name from `~/.aws/credentials` or `~/.aws/config`
- `<YOUR_AWS_REGION>`: AWS region where LZA is deployed (e.g., `us-east-1`)

**Optional Environment Variables:**

You can customize the MCP server behavior by adding environment variables to the `env` section:

```json
"env": {
  "AWS_PROFILE": "<YOUR_AWS_PROFILE>",
  "AWS_REGION": "<YOUR_AWS_REGION>",
  "LZA_PREFIX": "AWSAccelerator",
  "LOG_INSTRUCTIONS": "false"
}
```

- `LZA_PREFIX`: The prefix used by your LZA deployment for resource naming (default: `AWSAccelerator`)
  - LZA uses this prefix to name resources like pipelines, CloudFormation stacks, and SSM parameters
  - If you customized the prefix during LZA installation, set this to match your deployment
  - Example: If your pipeline is named `MyOrg-Pipeline`, set `LZA_PREFIX="MyOrg"`
  - This affects:
    - Pipeline name: `{LZA_PREFIX}-Pipeline`
    - SSM parameter: `/accelerator/{LZA_PREFIX}-InstallerStack/version`
    - CloudFormation stacks: `{LZA_PREFIX}-*`
- `LOG_INSTRUCTIONS`: Enable logging of MCP server instructions at startup (default: `false`)
  - Set to `true`, `1`, or `yes` to enable instruction logging
  - Useful for debugging or understanding what instructions are provided to the AI model
  - Instructions are logged at INFO level and include all guidance provided to the model

>**Note:** The [credential extraction script](#3-configure-aws-credentials) requires your AWS CLI profile to be ready for use. Complete any profile-specific prerequisites before starting your LZA MCP server (e.g., `aws sso login` for IAM Identity Center profiles).

### 4. Verify Installation

Restart your IDE and test connectivity:

```
Use your tools, check my AWS connectivity
```

The server will verify credentials and report the authenticated identity.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Build Process

### Schema Generation

The container build includes automated schema processing that powers the schema search and discovery tools. This process runs once during `make build` and takes approximately 30-60 seconds.

**What happens during build:**

1. **Fetch LZA Releases**: Queries GitHub API for available LZA versions
2. **Clone Source**: Downloads LZA source code for each version
3. **Extract Schemas**: Copies JSON schemas from `source/packages/@aws-accelerator/config/lib/schemas`
4. **Process Schemas**: Resolves `$ref` references and generates search metadata
5. **Embed in Image**: Creates version-specific directories at `/app/json-schemas/{version}/`

**Schema enhancements:**
- **Reference Resolution**: All `$ref` pointers resolved for self-contained schemas
- **Search Metadata**: Pre-computed indexes for property names, types, patterns, and relationships
- **Statistics**: Property counts, nesting depth, and complexity metrics

This preprocessing enables sub-second schema searches without runtime analysis overhead.

### Build Customization

Control which LZA versions and UC releases are included in the container:

```bash
# Default build (v1.12.0 to latest LZA, latest UC) - auto-detects runtime
make build

# Custom LZA version range using Makefile
make build LZA_MIN_VERSION=v1.10.0 LZA_MAX_VERSION=v1.14.0

# Direct build with specific runtime (replace 'docker' with 'finch' if needed)
docker build \
  --build-arg LZA_MIN_VERSION=v1.11.0 \
  --build-arg LZA_MAX_VERSION=v1.13.0 \
  --build-arg LZA_UC_RELEASE=v1.0.0 \
  -t lza-mcp-server:local .
```

> **Note:** The Makefile auto-detects Docker or Finch. For direct builds, replace `docker` with `finch` if using Finch.

**Build Arguments:**

| Argument | Default | Purpose |
|----------|---------|---------|
| `LZA_MIN_VERSION` | `v1.12.0` | Earliest LZA version to include |
| `LZA_MAX_VERSION` | `latest` | Latest LZA version to include |
| `LZA_UC_RELEASE` | `latest` | Universal Configuration release version |

**Note:** Including more versions increases build time and image size proportionally. Most users only need schemas matching their deployed LZA version.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## AWS Permissions

The MCP server requires specific IAM permissions for LZA operations. This policy follows AWS least-privilege principles.

> **🔒 Privacy Consideration**  
> AWS API responses retrieved using these permissions will be shared with your AI model provider. Review your organization's data classification policies before granting access to sensitive AWS resources.

### Recommended IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "STSAccess",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Sid": "SSMAccess",
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": "arn:${PARTITION}:ssm:${HOME-REGION}:${MANAGEMENT_ACCOUNT}:parameter/accelerator/*"
    },
    {
      "Sid": "S3WriteAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:${PARTITION}:s3:::${ACCELERATOR_PREFIX}-config-*/zipped/*"
      ]
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:${PARTITION}:s3:::${ACCELERATOR_PREFIX}-config-*"
    },
    {
      "Sid": "KMSEncryptionAccess",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:${PARTITION}:kms:*:${MANAGEMENT_ACCOUNT}:key/*",
      "Condition": {
        "ForAnyValue:StringEquals": {
          "kms:ResourceAliases": "alias/accelerator/installer/kms/key"
        }
      }
    },
    {
      "Sid": "PipelineAccess",
      "Effect": "Allow",
      "Action": [
        "codepipeline:GetPipeline",
        "codepipeline:GetPipelineState",
        "codepipeline:GetPipelineExecution",
        "codepipeline:ListPipelineExecutions",
        "codepipeline:StartPipelineExecution"
      ],
      "Resource": "arn:${PARTITION}:codepipeline:${HOME-REGION}:${MANAGEMENT_ACCOUNT}:${ACCELERATOR_PREFIX}-Pipeline"
    },
    {
      "Sid": "CodeBuildAccess",
      "Effect": "Allow",
      "Action": "codebuild:BatchGetBuilds",
      "Resource": "arn:${PARTITION}:codebuild:${HOME-REGION}:${MANAGEMENT_ACCOUNT}:project/${ACCELERATOR_PREFIX}-*"
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": "logs:GetLogEvents",
      "Resource": "arn:${PARTITION}:logs:${HOME-REGION}:${MANAGEMENT_ACCOUNT}:log-group:/aws/codebuild/${ACCELERATOR_PREFIX}-*:*"
    }
  ]
}
```

### Policy Variables

Replace these placeholders with your deployment values:

- `${HOME-REGION}`: AWS region where LZA is deployed (e.g., `us-east-1`)
- `${MANAGEMENT_ACCOUNT}`: AWS management account ID (12-digit number)
- `${ACCELERATOR_PREFIX}`: LZA resource prefix (default: `aws-accelerator`)
- `${PARTITION}`: AWS partition (`aws`, `aws-us-gov`, or `aws-cn`)

### Permission Scope

| Service | Purpose | Reference |
|---------|---------|-----------|
| **STS** | Identity verification for connectivity checks | [AWS STS Documentation](https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html) |
| **SSM** | Retrieve deployed LZA version from Parameter Store | [AWS Systems Manager Parameters](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html) |
| **S3** | Read/write LZA configuration files in config bucket | [S3 Bucket Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html) |
| **KMS** | Encrypt/decrypt configurations using LZA KMS key | [AWS KMS Key Policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html) |
| **CodePipeline** | Monitor and trigger LZA pipeline executions | [CodePipeline Monitoring](https://docs.aws.amazon.com/codepipeline/latest/userguide/monitoring.html) |
| **CodeBuild** | Retrieve build project details for diagnostics | [CodeBuild Projects](https://docs.aws.amazon.com/codebuild/latest/userguide/builds-working.html) |
| **CloudWatch Logs** | Access CodeBuild logs for error analysis | [CloudWatch Logs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html) |

**Note:** The KMS policy uses alias-based access control (`kms:ResourceAliases`) for maintainability. This approach allows key rotation without policy updates, following [AWS KMS best practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html).

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## MCP Client Configuration

### Configuration File Locations

| IDE | Configuration Path |
|-----|-------------------|
| **Kiro IDE** | `.kiro/settings/mcp.json` (workspace)<br>`~/.kiro/settings/mcp.json` (global) |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |

### Complete Configuration Example

```json
{
  "mcpServers": {
    "awslabs.lza-mcp-server": {
      "command": "/Users/jsmith/repos/lza-mcp-server/scripts/extract-aws-credentials.sh",
      "args": [
        "docker", "run",
        "--security-opt=no-new-privileges:true",
        "--cap-drop=ALL",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=200m",
        "--rm", "-i",
        "-v", "/Users/jsmith/Documents/lza-config:/app/lza-config:rw",
        "-e", "LZA_CONFIG_HOST_PATH=/Users/jsmith/Documents/lza-config",
        "-e", "AWS_ACCESS_KEY_ID",
        "-e", "AWS_SECRET_ACCESS_KEY",
        "-e", "AWS_SESSION_TOKEN",
        "-e", "AWS_REGION",
        "-e", "FASTMCP_LOG_LEVEL=INFO",
        "-e", "ENABLE_UC_MERGE=false",
        "lza-mcp-server:local"
      ],
      "env": {
        "AWS_PROFILE": "lza-role-mcp-policy-attached",
        "AWS_REGION": "us-east-1"
      },
      "disabled": false,
      "autoApprove": [
        "checkAwsConnectivity",
        "listLzaSupportedVersions",
        "searchJsonSchema",
        "getFullSchema",
        "getPipelineStatus",
        "getConfigurationFromS3"
      ]
    }
  }
}
```

### Security Flags

The configuration includes container security hardening:

- `--security-opt=no-new-privileges:true`: Prevents privilege escalation
- `--cap-drop=ALL`: Removes all Linux capabilities
- `--read-only`: Makes root filesystem read-only
- `--tmpfs /tmp`: Provides writable temp space with `noexec`

These flags mitigate container escape vulnerabilities. Keep Docker/Finch updated for latest security patches.

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `LZA_CONFIG_HOST_PATH` | Local path for configuration files (must match volume mount) | `/Users/jsmith/Documents/lza-config` |
| `AWS_PROFILE` | AWS CLI profile name for role with LZA MCP policy attached | `lza-role-mcp-policy-attached` |
| `AWS_REGION` | Default AWS region | `us-east-1` |
| `FASTMCP_LOG_LEVEL` | Logging verbosity | `INFO`, `DEBUG` |
| `ENABLE_UC_MERGE` | Enable Universal Configuration merge tools | `false` (default), `true` |
| `LOG_INSTRUCTIONS` | Log MCP server instructions at startup | `false` (default), `true` |

**Note:** Setting `ENABLE_UC_MERGE=true` enables 9 additional tools for UC merge workflows but increases context size by ~56%.

### Auto-Approved Tools

The `autoApprove` list includes read-only operations that don't modify AWS resources:

- Configuration retrieval and inspection
- Schema searches and discovery
- Pipeline status monitoring
- AWS connectivity verification

Tools that modify resources (`releasePipeline`, `uploadConfigurationToS3`) require explicit approval for safety.

### Schema Integrity Validation

The server validates schema integrity at startup using SHA-256 checksums. This protects against tampering or corruption of embedded LZA schemas. If validation fails, the server refuses to start with a clear error message.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Available Tools

### AWS Services

**checkAwsConnectivity**  
Verifies AWS credentials and reports authenticated identity. Use this to confirm AWS connectivity with a IAM credentials before performing operations.

**getDeployedLzaVersion**  
Retrieves the currently deployed LZA version from SSM Parameter Store. Use this to identify the correct schema version for searches.

### Configuration Management

**getMinimumConfiguration**  
Generates minimal LZA configuration templates for new deployments. Templates include required accounts and baseline settings.

**uploadConfigurationToS3**  
Uploads configuration files to the LZA S3 bucket.

**getConfigurationFromS3**  
Retrieves current LZA configuration from S3 for inspection or modification. Extracts files to shared Docker volume for IDE access.

### Pipeline Management

**releasePipeline**  
Starts LZA pipeline execution to deploy configuration changes. See [CodePipeline execution documentation](https://docs.aws.amazon.com/codepipeline/latest/userguide/executions-view.html) for execution details.

**getPipelineStatus**  
Monitors pipeline execution progress with stage-level details. Returns real-time status for all pipeline stages.

**diagnosePipelineErrors**  
Retrieves detailed error logs from failed pipeline executions. Analyzes CodeBuild logs and provides troubleshooting guidance.

### Schema Search

**listLzaSupportedVersions**  
Lists all LZA versions with embedded schemas. Use this to identify the correct version for schema searches.

**searchJsonSchema**  
Searches LZA configuration schemas by property names, patterns, or complexity. Requires explicit `lza_version` parameter.

**getFullSchema**  
Retrieves complete schema definitions or specific properties. Supports filtering by property path for targeted queries.

### Universal Configuration Merge (Optional)

Enable with `ENABLE_UC_MERGE=true` to access UC merge workflow tools:

- **validateLzaForUcMerge**: Validate LZA installation compatibility
- **get_uc_releases**: Discover available UC release versions
- **get_uc_network_models**: Compare network deployment models
- **start_uc_merge_session**: Initialize UC merge session
- **readLzaConfigFile**: Read LZA configuration files
- **readUcFile**: Read UC files from merge session
- **updateUcFile**: Update UC files in merge session
- **getUcNetworkCustomizationGuide**: Get customization guidance
- **copyUcToLzaConfig**: Copy UC configuration to LZA directory

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Schema Management

Schemas are generated during container build. See [Build Process](#build-process) for build details and customization options.

### Multi-Version Support

The server supports multiple LZA versions simultaneously:
- Search schemas for specific versions
- Compare configurations across releases
- Match schemas to deployed LZA version
- Access latest LZA schemas automatically

### File Structure

```
/app/json-schemas/
├── v1.12.0/
│   ├── accounts-config-schema.json
│   ├── global-config-schema.json
│   ├── iam-config-schema.json
│   ├── network-config-schema.json
│   ├── organization-config-schema.json
│   ├── security-config-schema.json
│   └── combined.json
├── v1.13.0/
│   └── ...
└── v1.14.0/
    └── ...
```

### Using Schema Tools

All schema tools require explicit version specification:

```bash
# List available versions
listLzaSupportedVersions()

# Search schemas for specific version
searchJsonSchema(
  lza_version="v1.12.0",
  search_terms=["vpc", "subnet"]
)

# Get full schema
getFullSchema(
  lza_version="v1.13.0",
  schema_path="network-config-schema.json"
)
```

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Universal Configuration

The [LZA Universal Configuration](https://github.com/aws/lza-universal-configuration) provides enterprise-ready configuration templates that establish secure, scalable, and well-architected multi-account AWS environments. These templates enable rapid deployment of baseline environments supporting multiple global compliance frameworks.

The MCP server includes UC release artifacts and specialized merge tools to streamline integration of these compliance-focused templates with existing LZA deployments.

### What UC Provides

- **Enterprise-Ready Templates**: Pre-configured security, governance, and organization settings
- **Network Patterns**: Hub-and-spoke and shared VPC networking architectures
- **Compliance Frameworks**: Support for multiple global regulatory requirements
- **Best Practices**: Opinionated, well-architected approach to multi-account environments

### Included Content

During build, the latest UC release is downloaded:
- Configuration packages (hub-and-spoke, shared-vpc, etc.)
- Complete documentation from source repository

### Build Arguments

```bash
# Use latest release (default)
make build

# Specify version
docker build \
  --build-arg LZA_UC_RELEASE=v1.0.0 \
  -t lza-mcp-server:local .
```

### File Structure

```
/app/lza-uc/
└── v1.0.0/
    ├── hub-and-spoke/
    ├── hub-and-spoke-for-govcloud-us/
    ├── shared-vpc/
    └── docs/
```

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Configuration Operations

### Retrieving Configurations

The `getConfigurationFromS3` tool downloads and extracts the current LZA configuration:

1. Downloads ZIP from `zipped/aws-accelerator-config.zip`
2. Extracts to `/app/lza-config/retrieved-config` (container path)
3. Returns `host_path` for IDE file access
4. Provides metadata (file counts, directory structure)
5. Automatically cleans up previous retrievals

> **💡 Recommendation**  
> Place the configuration directory within your IDE workspace for easier file access. This allows seamless navigation and AI assisted editing of retrieved configurations.

### Volume Mount Configuration

The `LZA_CONFIG_HOST_PATH` environment variable must match the volume mount path:

```json
{
  "args": [
    "-v", "/Users/jsmith/Documents/lza-config:/app/lza-config:rw",
    "-e", "LZA_CONFIG_HOST_PATH=/Users/jsmith/Documents/lza-config"
  ]
}
```

This ensures the server provides correct file paths for IDE access.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Pipeline Management

### Deployment Workflow

1. **Upload Configuration**
   ```
   Use your tools, upload my LZA configuration
   ```

2. **Start Pipeline**
   ```
   Start LZA pipeline execution
   ```

3. **Monitor Progress**
   ```
   Get LZA pipeline status
   ```

4. **Diagnose Errors** (if needed, it will auto-suggest)
   ```
   Diagnose pipeline errors
   ```

### Pipeline Monitoring

The server provides real-time pipeline monitoring with stage-level details. See [AWS CodePipeline monitoring documentation](https://docs.aws.amazon.com/codepipeline/latest/userguide/monitoring.html) for execution state details.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Advanced Topics

### Custom Schema Versions

Build container with specific LZA version range:

```bash
docker build \
  --build-arg LZA_MIN_VERSION=v1.8.0 \
  --build-arg LZA_MAX_VERSION=v1.15.0 \
  -t lza-mcp-server:custom .
```

### Logging Configuration

Adjust logging verbosity for troubleshooting:

```json
{
  "env": {
    "FASTMCP_LOG_LEVEL": "DEBUG"
  }
}
```

Levels: `ERROR`, `WARNING`, `INFO`, `DEBUG`

### Resource Limits

Add resource constraints to prevent resource exhaustion:

```json
{
  "args": [
    "--memory=1g",
    "--cpus=1.0"
  ]
}
```

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Troubleshooting

### Schema Issues

**Schema file not found**  
Rebuild container image: `make build`

**Search returns no results**  
Verify version exists: `listLzaSupportedVersions()`

**Missing lza_version parameter**  
All schema tools require explicit version (e.g., `"v1.12.0"`)

### Container Issues

**Build fails during LZA clone**  
Check network connectivity and GitHub access

**AWS credentials warnings**  
Verify AWS CLI profile configuration in `~/.aws/credentials`

### Configuration Issues

**Bucket not found**  
Verify LZA deployment and configuration bucket existence

**Permission denied**  
Confirm profile name in MCP configuration and ensure role has LZA MCP recommended policy attached

### Pipeline Issues

**Pipeline not found**  
Verify pipeline name matches LZA deployment (default: `AWSAccelerator-Pipeline`) and MCP configuration JSON region specification

**Execution fails immediately**  
Check container logs, possibly increase logging level

### AWS Signature Errors

**InvalidSignatureException: Signature expired**  
This error indicates clock skew between your container and AWS services. AWS requires request signatures to be within 5 minutes of the current time.

**Verify the issue:**
```bash
# Check your local time
date -u

# Check container time (replace CONTAINER_ID)
docker exec CONTAINER_ID date -u
# or for Finch:
finch exec CONTAINER_ID date -u
```

If times differ by more than a few seconds, you have clock skew.

**Resolution:**

For Docker Desktop:
```bash
# Restart Docker Desktop from menu, or:
docker restart CONTAINER_ID
```

For Finch:
```bash
finch vm stop
finch vm start
```

After restarting, reconnect your MCP server to create a fresh container with synchronized time.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and contribute to the project.

## Code of Conduct

This project has adopted the [Amazon Open Source Code of Conduct](CODE_OF_CONDUCT.md). For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact opensource-codeofconduct@amazon.com with any additional questions or comments.

## Security

See [SECURITY.md](SECURITY.md) for information on reporting security vulnerabilities.

## License

Apache License 2.0 - see [LICENSE](LICENSE.txt) file for details.

[Back to top](#landing-zone-accelerator-on-aws-lza-mcp-server)
