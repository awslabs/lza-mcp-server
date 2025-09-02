# AWS Landing Zone Accelerator (LZA) MCP Server

An AWS Labs Model Context Protocol (MCP) server for AWS Landing Zone Accelerator pipeline management.

## Features

- **Pipeline Management**: Start, monitor, and diagnose LZA pipeline executions
- **Cross-Account Support**: Works with LZA deployments in different AWS accounts
- **Container Support**: Containerized deployment using Docker or Finch for local and cloud environments
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

#### Using Docker Compose
```bash
docker-compose up --build
```

#### Using Finch Compose
```bash
# Start Finch VM if not running
finch vm start
finch compose up --build
```

#### Using Docker directly
```bash
docker build -t lza-mcp-server .
docker run -p 8000:8000 -v ~/.aws:/home/lzauser/.aws:ro lza-mcp-server
```

#### Using Finch directly
```bash
# Start Finch VM if not running
finch vm start
finch build -t lza-mcp-server .
finch run -p 8000:8000 -v ~/.aws:/home/lzauser/.aws:ro lza-mcp-server
```

### Amazon Q Integration

1. **Copy the MCP configuration:**
```bash
cp mcp-config.json ~/.aws/amazonq/mcp.json
```

2. **Update paths in the configuration file to match your setup**

3. **Restart Amazon Q Developer**

## AWS Permissions

## Available Tools

- **releasePipeline**: Start the LZA pipeline execution
- **getPipelineStatus**: Get current pipeline status and progress
- **diagnosePipelineErrors**: Retrieve logs for failed pipeline executions

## Troubleshooting

### Finch Issues
- **VM not started**: Run `finch vm start` before using Finch commands
- **Build context errors**: Ensure you're running commands from the correct directory with all required files
- **AWS credentials warnings**: Set environment variables or use AWS credential files

## Documentation

See `deployment/README.md` for detailed deployment instructions and troubleshooting.

## License

Apache License 2.0 - see LICENSE file for details.
