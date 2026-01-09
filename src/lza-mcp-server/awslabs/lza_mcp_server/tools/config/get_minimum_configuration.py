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
import yaml
import logging
from typing import Dict, Any, Optional
from mcp.server.fastmcp import Context
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    validate_file_path,
)

logger = logging.getLogger(__name__)


async def tool_get_minimum_configuration(
    ctx: Context,
    config_type: Optional[str] = None,
    save_to_directory: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate complete minimum viable LZA configurations with all required components.

    Creates a set of baseline LZA configuration files that include all the minimum required
    settings for a successful LZA deployment. These configurations serve as a starting point
    that users can customize for their specific requirements.

    The generated configurations include:
    - accounts-config.yaml: Core account structure with Management, LogArchive, and Audit accounts
    - global-config.yaml: Global settings including regions, logging, and cost reporting
    - iam-config.yaml: Basic IAM policies and roles required for LZA operation
    - network-config.yaml: Minimal network configuration with VPC and security groups
    - organization-config.yaml: AWS Organizations structure with basic OUs
    - security-config.yaml: Essential security configurations and compliance settings

    ⚠️ IMPORTANT: The generated configurations contain placeholder values that MUST be
    customized before deployment:
    - Email addresses must be replaced with real, unique email addresses
    - AWS regions must be set to your preferred regions
    - Account names and organizational units should match your requirements

    Args:
        config_type (str, optional): Optional specific configuration type to generate (accounts, global, iam, network, organization, security). If not provided, generates all configuration files
        save_to_directory (str, optional): Directory path where configuration files should be saved. If provided, files will be written to disk automatically

    Returns:
        Dictionary containing the complete configuration files and instructions for customization

    Examples:

    Generate all configuration files:
    ```python
    # Generate complete LZA configuration set
    result = await getMinimumConfiguration()

    if "config_files" in result:
        configs = result["config_files"]
        print(f"✅ Generated {len(configs)} configuration files:")
        for config_name in configs.keys():
            print(f"  - {config_name}-config.yaml")

        # The assistant should now ask for customization details
        print("\\n⚠️ IMPORTANT: Please provide:")
        print("1. Email addresses for Management, LogArchive, and Audit accounts")
        print("2. Your preferred AWS home region")
    ```
    Most common usage - generate all required configuration files
    """
    await ctx.info(
        "Generating minimum configuration"
        + (f" for {config_type}" if config_type else "")
        + (f" to {save_to_directory}" if save_to_directory else "")
    )

    # Validate config_type if provided
    if config_type:
        is_valid, validation_error = validate_string_input(
            config_type, "config_type", min_length=1, max_length=50
        )
        if not is_valid:
            error_message = f"Invalid config_type: {validation_error}"
            await ctx.error(error_message)
            return {"error": error_message}

    # Validate save_to_directory if provided
    if save_to_directory:
        is_valid, validation_error = validate_file_path(
            save_to_directory, allow_absolute=True
        )
        if not is_valid:
            error_message = f"Invalid save_to_directory: {validation_error}"
            await ctx.error(error_message)
            return {"error": error_message}

    # Define the path to the minimum configuration files
    min_config_dir = os.environ.get(
        "LZA_MIN_CONFIG_DIR", "/app/lza-minimum-configuration"
    )

    # Make sure the config directory exists
    if not os.path.isdir(min_config_dir):
        error_message = f"Minimum configuration directory not found: {min_config_dir}"
        await ctx.error(error_message)
        return {
            "error": error_message,
            "message": "Configuration templates not found. Please contact the administrator.",
        }

    # Dictionary to store loaded configurations
    configs = {}

    # List of expected config types
    expected_types = [
        "accounts",
        "global",
        "iam",
        "network",
        "organization",
        "security",
        "customizations",
    ]

    # Read the configurations from files
    for cfg_type in expected_types:
        file_path = os.path.join(min_config_dir, f"{cfg_type}-config.yaml")
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    configs[cfg_type] = yaml.safe_load(f)
                    await ctx.info(f"Loaded configuration for {cfg_type}")
            except Exception as e:
                await ctx.error(f"Error loading {cfg_type} configuration: {str(e)}")

    # Return empty result if no configs were found
    if not configs:
        error_message = "No configuration templates found"
        await ctx.error(error_message)
        return {
            "error": error_message,
            "message": "Configuration templates not found. Please contact the administrator.",
        }

    result = {}

    # Return specific config type if requested
    if config_type:
        if config_type in configs:
            result["config_files"] = {config_type: configs[config_type]}
        else:
            error_message = f"Unknown config type: {config_type}. Available types: {list(configs.keys())}"
            await ctx.error(error_message)
            return {"error": error_message, "available_types": list(configs.keys())}
    else:
        result["config_files"] = configs

    # Add instructions for the AI assistant
    result["instructions_for_assistant"] = {
        "message": "IMPORTANT: These configuration files must be saved as individual YAML files to create a working LZA deployment.",
        "file_naming": "Each configuration should be saved as '{type}-config.yaml' (e.g., accounts-config.yaml, global-config.yaml)",
        "required_action": "BEFORE SAVING: You MUST ask the user to provide their specific email addresses and preferred AWS region.",
        "critical_customizations": [
            "1. In accounts-config.yaml: Replace placeholder emails (management-account@example.com, etc.) with the user's actual email addresses",
            "2. In global-config.yaml: Update homeRegion and enabledRegions with the user's preferred AWS region",
            "3. Ask explicitly: 'What email addresses would you like to use for your Management, LogArchive, and Audit accounts?'",
            "4. Ask explicitly: 'Which AWS region would you like to use as your home region?'",
        ],
        "user_guidance": "AFTER getting this information, then modify the configuration files with the user's values BEFORE saving them.",
        "explain_to_user": "Explain that personalized email addresses and regions are REQUIRED for a successful deployment. Using placeholder values will cause deployment failures.",
    }

    # Save to directory if requested
    if save_to_directory:
        try:
            # Create directory if it doesn't exist
            os.makedirs(save_to_directory, exist_ok=True)

            saved_files = []

            # Save each config file
            for name, content in result["config_files"].items():
                file_path = os.path.join(save_to_directory, f"{name}-config.yaml")
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(content, f, default_flow_style=False)
                saved_files.append(file_path)

            result["saved_to_directory"] = save_to_directory
            result["saved_files"] = saved_files

            await ctx.info(
                f"Saved {len(saved_files)} configuration files to {save_to_directory}"
            )

            # Add success message for the assistant
            result["instructions_for_assistant"]["files_saved"] = True
            result["instructions_for_assistant"]["message"] += (
                f" Files have been saved to {save_to_directory}."
            )
            result["instructions_for_assistant"]["required_action"] = (
                "Inform the user that the files have been saved and explain how to customize them for their environment."
            )
        except Exception as e:
            error_message = f"Error saving configuration files: {str(e)}"
            await ctx.error(error_message)
            result["error"] = error_message

    return result
