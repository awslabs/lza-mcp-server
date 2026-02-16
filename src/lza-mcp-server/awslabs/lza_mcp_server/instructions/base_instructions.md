# AWS Landing Zone Accelerator (LZA) MCP Server

This MCP server helps manage LZA configurations and pipeline operations for the AWS Landing Zone Accelerator solution.

## Configuration

The server can be configured via environment variables in your MCP client configuration:

- **LZA_PREFIX**: The prefix used by your LZA deployment for resource naming (default: "AWSAccelerator")
  - This prefix is used for pipeline names, SSM parameters, and CloudFormation stacks
  - Set this if you customized the prefix during LZA installation
  - Example: If your pipeline is named "MyOrg-Pipeline", set LZA_PREFIX="MyOrg"

## Available Tools

### AWS Services
- **checkAwsConnectivity**: Verify AWS credentials and connectivity
- **getDeployedLzaVersion**: Get the currently deployed LZA version from SSM Parameter Store

### Configuration Management
- **getMinimumConfiguration**: Generate minimal LZA configuration templates
- **uploadConfigurationToS3**: Upload configuration files to S3 bucket
- **getConfigurationFromS3**: Retrieve and extract current LZA configuration from S3

### Pipeline Management
- **releasePipeline**: Trigger execution of the LZA Configuration Pipeline
- **getPipelineStatus**: Monitor pipeline execution status with stage progression
- **diagnosePipelineErrors**: Retrieve CodeBuild logs for failed executions

### Schema Management
- **listLzaSupportedVersions**: List all supported LZA versions with schema information
- **searchJsonSchema**: Search through LZA JSON schemas (requires lza_version parameter)
- **getFullSchema**: Retrieve complete LZA configuration JSON schemas (requires lza_version parameter)
