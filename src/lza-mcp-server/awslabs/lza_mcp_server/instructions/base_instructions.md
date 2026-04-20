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
- **getLzaConfiguration**: Retrieve and extract LZA configuration from S3 (supports standard and external pipeline deployments via qualifier)
- **putLzaConfiguration**: Upload configuration files to S3 (supports standard and external pipeline deployments via qualifier)

### Pipeline Management
- **startDeployment**: Start an LZA deployment (supports standard pipeline, external CodePipeline, and ECS container deployments)
- **getDeploymentStatus**: Monitor deployment status with stage progression (supports both standard pipeline and ECS container deployments)
- **diagnoseDeploymentErrors**: Diagnose failed LZA deployments (supports both standard pipeline and ECS container deployments)

### Schema Management
- **listLzaSupportedVersions**: List all supported LZA versions with schema information
- **searchJsonSchema**: Search through LZA JSON schemas (requires lza_version parameter)
- **getFullSchema**: Retrieve complete LZA configuration JSON schemas (requires lza_version parameter)
