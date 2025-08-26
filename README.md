# AWS Landing Zone Accelerator (LZA) MCP Server

A Model Context Protocol (MCP) server for AWS Landing Zone Accelerator configuration validation and management.

## Overview

The LZA MCP Server provides AI assistants with tools to help users work with AWS Landing Zone Accelerator configurations. This server follows the Model Context Protocol standard to expose capabilities like configuration validation, generation, and AWS integration.

## Key Features

- **Configuration Generation**: Create minimum viable LZA configurations
- **Native Validation**: Validate configurations using the official LZA validator
- **S3 Integration**: Upload and manage configurations via S3
- **AWS Connectivity**: Check AWS credentials and setup validation resources
- **JSON Schema Discovery**: Search and explore LZA configuration schemas with comprehensive metadata
- **CodePipeline Management**: Release, monitor, and diagnose AWS CodePipeline executions for LZA deployments
- **Docker-based**: Self-contained validation environment with pre-processed schemas
