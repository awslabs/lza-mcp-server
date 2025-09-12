# LZA MCP Server Manual Test Cases

This document provides step-by-step instructions for manually testing the LZA MCP Server functionality.

## Prerequisites

- Finch container runtime installed
- Amazon Q Developer IDE extension installed
- AWS credentials configured
- Access to AWS account with appropriate permissions

## Setup Instructions

### 1. Build the Finch Container

```bash
cd ~/xdev/mte/lza-mcp-server/src/lza-mcp-server
make release

# Build using Dockerfile.local for local development
finch build -f Dockerfile.local -t lza-mcp-server:local .

# Or use docker-compose (recommended)
finch compose up --build
```

### 2. Copy MCP Configuration File

Copy the MCP configuration to Amazon Q's expected location:

```bash
cp ~/xdev/mte/lza-mcp-server/src/lza-mcp-server/mcp-config-finch.json ~/.aws/amazonq/mcp.json
```

### 3. Start Amazon Q with Debug Enabled

1. Open your IDE (VS Code/IntelliJ)
2. Enable debug mode in Amazon Q settings
3. Restart the IDE to load the MCP configuration

### 4. Verify MCP Server Loading

In Amazon Q chat, run:
```
/mcp
```

You should see the `lza-mcp-server` listed as an available MCP server.

## Tool Testing Workflow

### AWS Services Tools

#### Test 1: Check AWS Connectivity
**Tool:** `checkAwsConnectivity`

**Sample Prompt:**
```
Check my AWS connectivity and verify my credentials are working properly.
```

**Expected Result:** Confirmation of AWS access with account details and region information.

#### Test 2: Setup S3 Bucket
**Tool:** `setupS3Bucket`

**Sample Prompt:**
```
Create an S3 bucket for my LZA configuration storage. Use the name "my-lza-config-bucket-test-123".
```

**Expected Result:** S3 bucket created with proper permissions and configuration for LZA use.

### Configuration Management Tools

#### Test 3: Get Minimum Configuration
**Tool:** `getMinimumConfiguration`

**Sample Prompt:**
```
Generate a minimal LZA configuration template for me to get started.
```

**Expected Result:** Complete set of minimal YAML configuration files for LZA deployment.

#### Test 4: Upload Configuration to S3
**Tool:** `uploadConfigurationToS3`

**Sample Prompt:**
```
Upload my LZA configuration files to S3. Use the bucket "my-lza-config-bucket-test-123" and offer to release the pipeline after upload.
```

**Expected Result:** Configuration files uploaded to S3 with option to trigger pipeline execution.

### Validation Tools

#### Test 5: Validate Configuration from S3
**Tool:** `validateConfigurationFromS3`

**Sample Prompt:**
```
Validate the LZA configuration stored in s3://my-lza-config-bucket-test-123/
```

**Expected Result:** Validation report showing syntax check results and compliance status.

#### Test 6: Validate Configuration from Local Share
**Tool:** `validateConfigurationFromShare`

**Sample Prompt:**
```
Validate my local LZA configuration files in ~/Documents/lza-config directory.
```

**Expected Result:** Local file validation with detailed error/success reporting.

#### Test 7: Cleanup Validation Files
**Tool:** `cleanupValidationZip`

**Sample Prompt:**
```
Clean up the temporary validation files from ~/Documents/lza-config directory.
```

**Expected Result:** Temporary files and zip archives removed successfully.

### Pipeline Management Tools

#### Test 8: Release Pipeline
**Tool:** `releasePipeline`

**Sample Prompt:**
```
Start the LZA pipeline execution to deploy my configuration changes.
```

**Expected Result:** Pipeline execution started with execution ID returned.

#### Test 9: Get Pipeline Status
**Tool:** `getPipelineStatus`

**Sample Prompt:**
```
Check the current status of my LZA pipeline execution and show me the progress.
```

**Expected Result:** Detailed pipeline status with stage progression and current execution state.

#### Test 10: Diagnose Pipeline Errors
**Tool:** `diagnosePipelineErrors`

**Sample Prompt:**
```
Help me diagnose any errors in my failed LZA pipeline execution.
```

**Expected Result:** Detailed error logs and diagnostic information for troubleshooting.

#### Test 11: Release Pipeline After Upload
**Tool:** `releasePipelineAfterUpload`

**Sample Prompt:**
```
Trigger the LZA pipeline execution now that my configuration upload is complete.
```

**Expected Result:** Pipeline execution initiated following successful configuration upload.

### Schema Management Tools

#### Test 12: Search JSON Schema
**Tool:** `searchJsonSchema`

**Sample Prompt:**
```
Search the LZA JSON schema for properties related to "vpc" and "networking" configurations.
```

**Expected Result:** Relevant schema properties and configurations related to VPC and networking.

#### Test 13: Get Full Schema
**Tool:** `getFullSchema`

**Sample Prompt:**
```
Get the complete LZA configuration schema for network-config.json with metadata included.
```

**Expected Result:** Complete JSON schema for network configuration with property definitions.

## Complete End-to-End Workflow Test

### Test 14: Full LZA Deployment Workflow

**Sample Prompts Sequence:**

1. **Check connectivity:**
   ```
   Check my AWS connectivity first.
   ```

2. **Setup infrastructure:**
   ```
   Create an S3 bucket called "lza-e2e-test-bucket-456" for my LZA configuration.
   ```

3. **Generate configuration:**
   ```
   Generate minimal LZA configuration templates and save them to ~/Documents/lza-test-config.
   ```

4. **Validate locally:**
   ```
   Validate the configuration files in ~/Documents/lza-test-config directory.
   ```

5. **Upload to S3:**
   ```
   Upload the validated configuration to S3 bucket "lza-e2e-test-bucket-456".
   ```

6. **Deploy:**
   ```
   Start the LZA pipeline to deploy my configuration.
   ```

7. **Monitor:**
   ```
   Check the pipeline status and show me detailed progress information.
   ```

8. **Troubleshoot (if needed):**
   ```
   If there are any pipeline failures, help me diagnose the errors.
   ```

9. **Schema reference:**
   ```
   Show me the schema for security-config.json so I can understand the available options.
   ```

10. **Cleanup:**
    ```
    Clean up any temporary validation files from my local directory.
    ```

**Expected Result:** Complete LZA deployment workflow from initial setup through monitoring and troubleshooting.

## Verification Checklist

- [ ] All 13 individual tools respond correctly
- [ ] MCP server loads without errors
- [ ] AWS connectivity is verified
- [ ] S3 bucket creation works
- [ ] Configuration generation produces valid files
- [ ] Validation tools catch syntax errors
- [ ] Pipeline tools provide accurate status
- [ ] Schema tools return relevant information
- [ ] End-to-end workflow completes successfully
- [ ] Error handling works appropriately
- [ ] Cleanup operations remove temporary files

## Troubleshooting

### Common Issues

1. **MCP server not loading:**
   - Check `~/.aws/amazonq/mcp.json` exists and is valid
   - Verify Finch container is built successfully
   - Restart IDE after configuration changes

2. **AWS connectivity failures:**
   - Verify AWS credentials are configured
   - Check AWS_PROFILE environment variable
   - Ensure IAM permissions are sufficient

3. **Container build failures:**
   - Check Finch VM is running: `finch vm start`
   - Use correct dockerfile: `finch build -f Dockerfile.local -t lza-mcp-server:local .`
   - Or use docker-compose: `finch compose up --build`
   - Check for network connectivity issues

4. **Tool execution errors:**
   - Check Amazon Q debug logs
   - Verify AWS region is set correctly
   - Ensure required AWS services are available in region

### Debug Commands

Check MCP server logs:
```bash
# View container logs if running
finch logs <container_id>
```

Verify AWS credentials:
```bash
aws sts get-caller-identity --profile isengard_personal
```

Test container manually:
```bash
finch run --rm -it lza-mcp-server:local /bin/bash
```