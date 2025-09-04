# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import tempfile
import zipfile
import logging
from typing import Dict, Any
from mcp.server.fastmcp import Context

from .common import validate_configuration_impl
from ...aws_access import get_aws_session

logger = logging.getLogger(__name__)


async def _validate_from_docker_path(
    ctx: Context, docker_zip_path: str = None
) -> Dict[str, Any]:
    """Validate configuration from Docker shared volume path."""
    try:
        # Use environment variable for container path if not provided
        if docker_zip_path is None:
            container_share_path = os.environ.get(
                "LZA_CONFIG_CONTAINER_PATH", "/app/lza-config"
            )
            docker_zip_path = os.path.join(container_share_path, "config.zip")

        if not os.path.exists(docker_zip_path):
            return {
                "valid": False,
                "errors": [
                    {
                        "message": f"ZIP file not found at {docker_zip_path}",
                        "severity": "error",
                    }
                ],
                "message": "ZIP file not accessible",
            }

        # Extract and validate
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "extracted_config")
            os.makedirs(config_dir, exist_ok=True)

            with zipfile.ZipFile(docker_zip_path, "r") as zip_ref:
                zip_ref.extractall(config_dir)

            return validate_configuration_impl(config_dir)

    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        await ctx.error(error_msg)
        return {
            "valid": False,
            "errors": [{"message": error_msg, "severity": "error"}],
            "message": "Validation failed",
        }


async def tool_validate_configuration_from_share(
    ctx: Context, local_share_path: str = "~/Documents/lza-config"
) -> Dict[str, Any]:
    """Complete LZA validation workflow using Docker shared volume.

    ⚠️ IMPORTANT FOR LLM: ALWAYS offer validation method choice to users first!

    BEFORE using this tool, present these validation options to the user:

    1. **S3-based validation**: Most reliable, uses cloud storage
       - Requires AWS credentials and S3 bucket
       - User uploads ZIP file to S3, then validates

    2. **Local shared volume validation** (this tool): Uses Docker shared volumes
       - Requires Docker with shared volume mount
       - Creates ZIP locally and validates via shared volume

    Ask: "Which validation method would you prefer? (1 or 2)"
    Only proceed with shared volume validation if user chooses option 2.

    ⚠️ CRITICAL FOR LLM: DO NOT RUN DOCKER COMMANDS DIRECTLY! Use MCP tools only.

    IMPORTANT INSTRUCTIONS FOR LLM: This tool requires you to execute the following steps IN ORDER:

    1. **Check AWS Connectivity**:
       - First call checkAwsConnectivity() to verify AWS credentials
       - Do not proceed if AWS connectivity fails

    2. **Find Available LZA Configurations**:
       - Search the workspace for directories containing both 'accounts-config.yaml' and 'organization-config.yaml'
       - Present discovered configurations to the user as a numbered list
       - Ask the user to select which configuration to validate

    3. **Create ZIP and Place in Docker Share Location**:
       - Create a ZIP file of the ENTIRE selected configuration directory
       - CRITICAL: Include ALL files and subdirectories, even empty ones
       - Use commands like: cd /path/to/selected/config && zip -r ~/Documents/lza-config/config.zip .
       - The dot (.) at the end is MANDATORY - it includes all files and preserves directory structure

    4. **Run Validation**:
       - Call validateConfigurationFromShare() MCP tool to perform validation
       - DO NOT run Docker commands directly - use the MCP tool instead
       - The MCP server will handle Docker container execution internally

    5. **Clean Up**:
       - After validation completes, remove the ZIP file from the Docker share location
       - Use commands like: rm ~/Documents/lza-config/config.zip
       - Ensure the share location is clean for future use

    WORKFLOW REQUIREMENTS:
    - Docker container must be run with shared volume mount: -v "~/Documents/lza-config:/app/lza-config"
    - ZIP file must contain ALL files and subdirectories, not just YAML files
    - Use `cd /path/to/config && zip -r ~/Documents/lza-config/config.zip .` (dot is mandatory)
    - Empty directories and hidden files must be preserved in the ZIP
    - Clean up ZIP file is mandatory to prevent conflicts with future validations

    ⚠️ MCP TOOL USAGE - CRITICAL:
    - Step 4 must use validateConfigurationFromShare() MCP tool
    - DO NOT execute Docker run commands directly
    - DO NOT use execute_bash to run Docker containers
    - The MCP server handles Docker execution internally

    Args:
        local_share_path (str, optional): Path on local system for shared files (default: ~/Documents/lza-config)
        workspace_path (str, optional): Path to search for LZA configurations (default: current directory)

    Returns:
        Complete validation results with workflow status tracking for each step

    Example LLM Workflow:
    ```
    1. "Let me check your AWS connectivity first..."
       → Use MCP tool: checkAwsConnectivity()

    2. "I'll search for LZA configurations in your workspace..."
       → Search for directories with accounts-config.yaml and organization-config.yaml
       → Present: "Found 2 LZA configurations: 1. /path/to/config1  2. /path/to/config2"
       → Ask: "Which configuration would you like to validate? (1 or 2)"

    3. "I'll create a ZIP file and place it in the Docker share location..."
       → Use bash: cd /selected/path && zip -r ~/Documents/lza-config/config.zip .
       → Confirm: "ZIP file created successfully"

    4. "Now I'll run the validation using the MCP tool..."
       → Use MCP tool: validateConfigurationFromShare()
       → ⚠️ DO NOT run Docker commands - the MCP tool handles this internally

    5. "Cleaning up the ZIP file..."
       → Use bash: rm ~/Documents/lza-config/config.zip
       → Confirm: "Cleanup completed"
    ```

    ⚠️ REMEMBER: Steps 3 and 5 use bash commands for ZIP creation/cleanup. Step 4 uses the MCP tool!
    ⚠️ CRITICAL: The ZIP command MUST use the dot (.) and be run from within the config directory!
    """
    # Initialize workflow tracking
    workflow_status = {
        "discovered_configs": [],
        "selected_config": None,
        "zip_created": False,
        "zip_cleaned": False,
        "steps_completed": [],
    }

    try:
        # Step 1: Validate AWS Credentials
        await ctx.info("🔐 Step 1: Validating AWS credentials...")
        try:
            session = get_aws_session()
            sts_client = session.client("sts")
            caller_identity = sts_client.get_caller_identity()
            await ctx.info(
                f"✅ AWS credentials valid - Account: {caller_identity['Account']}"
            )
            workflow_status["steps_completed"].append("credentials_validated")
        except Exception as e:
            await ctx.error(f"❌ AWS credentials validation failed: {str(e)}")
            return {
                "valid": False,
                "errors": [
                    {
                        "message": f"AWS credentials validation failed: {str(e)}",
                        "severity": "error",
                    }
                ],
                "message": "AWS connectivity required for LZA validation",
                **workflow_status,
                "troubleshooting": "Please ensure AWS credentials are properly configured",
            }

        # Step 2: Check for ZIP file in shared volume
        await ctx.info("📦 Step 2: Checking for config.zip in shared volume...")
        container_share_path = os.environ.get(
            "LZA_CONFIG_CONTAINER_PATH", "/app/lza-config"
        )
        docker_zip_path = os.path.join(container_share_path, "config.zip")

        if not os.path.exists(docker_zip_path):
            expanded_local_path = os.path.expanduser(local_share_path)
            return {
                "valid": False,
                "errors": [
                    {
                        "message": f"config.zip not found in shared volume at {docker_zip_path}",
                        "severity": "error",
                    }
                ],
                "message": "ZIP file not found in shared volume",
                **workflow_status,
                "instructions": f"""
PREREQUISITE STEPS MISSING:

Before calling this tool, you must:

1. Create a ZIP file of your LZA configuration:
cd /path/to/your/lza-config
zip -r config.zip .

2. Place the ZIP file in the shared volume location:
cp config.zip {expanded_local_path}/

3. Ensure Docker is running with shared volume mount:
docker run -v "{expanded_local_path}:{container_share_path}" ...

The ZIP file should be accessible at: {docker_zip_path}
""",
            }

        # Step 3: Run validation on shared ZIP file
        await ctx.info("⚖️  Step 3: Running validation...")
        validation_result = await _validate_from_docker_path(ctx, docker_zip_path)

        # Add workflow tracking to results
        validation_result.update(workflow_status)
        validation_result["steps_completed"].append("validation_completed")

        if validation_result.get("valid", False):
            await ctx.info("🎉 Complete 5-step workflow executed successfully!")
        else:
            await ctx.info("❌ Validation completed with errors")

        return validation_result

    except Exception as e:
        await ctx.error(f"Unexpected error in validation workflow: {str(e)}")
        return {
            "valid": False,
            "errors": [{"message": f"Workflow error: {str(e)}", "severity": "error"}],
            "message": "Unexpected workflow error",
            **workflow_status,
        }
