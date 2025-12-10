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

"""UC Merge-related MCP tools for the LZA MCP Server."""

import logging
from mcp.server.fastmcp import Context

from .get_uc_releases import tool_get_uc_releases
from .get_uc_network_models import tool_get_uc_network_models
from .start_uc_merge_session import tool_start_uc_merge_session
from .read_lza_config_file import read_lza_config_file
from .read_uc_file import read_uc_file
from .get_uc_network_customization_guide import get_uc_network_customization_guide
from .update_uc_file import update_uc_file
from .copy_uc_to_lza_config import copy_uc_to_lza_config
from .validate_lza_for_uc_merge import validate_lza_for_uc_merge


logger = logging.getLogger(__name__)


def register_uc_merge_tools(mcp):
    """Register UC merge-related MCP tools.
    
    This function registers all tools needed for the Universal Configuration
    merge workflow, enabling AI-assisted integration of LZA Universal Configuration
    with fresh LZA installations.
    
    Tools registered:
    - validate_lza_for_uc_merge: Validate LZA installation is fresh and compatible
    - get_uc_releases: Discover available UC release versions
    - get_uc_network_models: Get network deployment model comparison
    - start_uc_merge_session: Initialize a UC merge session
    - read_lza_config_file: Read LZA configuration files
    - read_uc_file: Read UC files from session
    - update_uc_file: Update UC files in session
    - get_uc_network_customization_guide: Get customization guidance
    - copy_uc_to_lza_config: Copy UC configuration to LZA directory
    
    Args:
        mcp: FastMCP server instance
    """
    
    @mcp.tool()
    async def validateLzaForUcMerge(ctx: Context):
        """Validate that the LZA installation is fresh and compatible with UC merge.
        
        This tool validates that the current LZA installation meets the requirements
        for UC merge by checking:
        - accounts-config.yaml has only 3 mandatory accounts (no workload accounts)
        - network-config.yaml has minimal configuration (empty arrays)
        - iam-config.yaml has minimal configuration (empty arrays)
        
        Call this after getConfigurationFromS3() to ensure the installation is
        compatible with UC merge before proceeding.
        
        Returns:
            Dictionary with validation results and next steps guidance
        """
        return await validate_lza_for_uc_merge(ctx)
    
    @mcp.tool()
    async def get_uc_releases(ctx: Context):
        """Discover available UC release versions.
        
        Scans the UC repository directory to find all available release versions
        of the AWS Landing Zone Accelerator Universal Configuration. Returns
        releases in descending version order (newest first).
        
        Returns:
            Dictionary with available releases and next steps guidance
        """
        return await tool_get_uc_releases(ctx)
    
    @mcp.tool()
    async def get_uc_network_models(ctx: Context, uc_release: str):
        """Get available UC network deployment models with comparison information.
        
        Dynamically discovers available network models from the specified UC release
        and provides comparison information to help users select the appropriate
        architecture for their organization.
        
        Args:
            uc_release: UC release version (e.g., "v1.0.0"). Required parameter.
        
        Returns:
            Dictionary with available models, comparison data, and next steps guidance
        """
        return await tool_get_uc_network_models(ctx, uc_release)
    
    @mcp.tool()
    async def start_uc_merge_session(ctx: Context, uc_release: str, network_model: str):
        """Start a new UC merge session with the selected release and network model.
        
        Creates a session directory with a fresh copy of the UC configuration
        for the specified network model. The session_id must be passed to 
        subsequent UC merge tools (read_uc_file, update_uc_file, copy_uc_to_lza_config).
        
        This ensures each merge session works with pristine UC files and doesn't
        interfere with other sessions.
        
        Args:
            uc_release: UC release version (e.g., "v1.0.0"). Required parameter.
            network_model: Network model name (e.g., "hub-and-spoke", "shared-vpc"). Required parameter.
        
        Returns:
            Dictionary with session information or error details
        """
        return await tool_start_uc_merge_session(ctx, uc_release, network_model)
    
    @mcp.tool()
    async def readLzaConfigFile(ctx: Context, file_path: str):
        """Read a configuration file from the extracted LZA configuration.
        
        This tool reads files from the LZA configuration directory that was
        extracted via getConfigurationFromS3(). It validates paths for security
        and provides context-aware guidance based on the file being read.
        
        Common files to review:
        - accounts-config.yaml: Account structure and emails
        - global-config.yaml: Global settings including homeRegion
        - network-config.yaml: Network configuration
        - iam-config.yaml: IAM configuration
        
        Args:
            file_path: Relative path to file (e.g., "accounts-config.yaml"). Required parameter.
        
        Returns:
            Dictionary with file content, metadata, and next steps guidance
        """
        return await read_lza_config_file(ctx, file_path)
    
    @mcp.tool()
    async def readUcFile(ctx: Context, session_id: str, file_path: str):
        """Read a file from the UC session directory.
        
        This tool reads files from the UC session directory created by
        start_uc_merge_session(). It validates paths for security and provides
        context-aware guidance based on the file being read.
        
        For UC merge workflow, review at minimum:
        - accounts-config.yaml: Account structure and emails
        - replacements-config.yaml: Network settings and global replacements
        
        Args:
            session_id: Session identifier from start_uc_merge_session(). Required parameter.
            file_path: Relative path within UC session (e.g., "accounts-config.yaml"). Required parameter.
        
        Returns:
            Dictionary with file content, metadata, and next steps guidance
        """
        return await read_uc_file(ctx, session_id, file_path)
    
    @mcp.tool()
    async def getUcNetworkCustomizationGuide(ctx: Context, session_id: str):
        """Get network customization guidance and file list for the session's network model.
        
        This tool provides metadata about which network settings are relevant for the
        selected network model and lists all configuration files in the session directory.
        Use this to understand what settings can be customized and which files are
        available to read.
        
        Args:
            session_id: Session identifier from start_uc_merge_session(). Required parameter.
        
        Returns:
            Dictionary with:
            - network_model: Selected network model
            - shared_settings: Settings used by all models
            - model_specific_settings: Settings specific to this model
            - configuration_files: Files organized by type (config_files, policy_directories, supporting_directories)
            - customization_guidance: Guidance text
            - common_changes: List of common customizations
            - next_steps: Guidance for next actions
        """
        return get_uc_network_customization_guide(session_id)
    
    @mcp.tool()
    async def updateUcFile(ctx: Context, session_id: str, file_path: str, updates: dict):
        """Update a UC configuration file in the session directory with new values.
        
        This tool allows updating UC configuration files with user customizations.
        It validates the session, file existence, and applies security checks before
        updating. After updates, it validates YAML syntax and performs basic value
        validation for CIDR ranges and numeric values.
        
        Args:
            session_id: Session identifier from start_uc_merge_session(). Required parameter.
            file_path: Relative path to file within session (e.g., "replacements-config.yaml"). Required parameter.
            updates: Dictionary of key-value pairs to update in the YAML file. Required parameter.
        
        Returns:
            Dictionary with:
            - success: Operation success status
            - session_id: Session identifier
            - file_path: Path to updated file
            - updates_applied: Dictionary of changes applied (old and new values)
            - validation_errors: List of validation errors (empty if successful)
            - next_steps: Guidance for next actions
        
        Example:
            result = await updateUcFile(
                session_id="uc-session-20250127-143022",
                file_path="replacements-config.yaml",
                updates={
                    "HomeRegionIngressCidr": "10.0.0.0/16",
                    "DevVpcMaskLength": 24
                }
            )
        """
        return await update_uc_file(session_id, file_path, updates)
    
    @mcp.tool()
    async def copyUcToLzaConfig(ctx: Context, session_id: str):
        """Copy UC configuration from session directory to extracted LZA configuration directory.
        
        This tool merges UC files with the existing LZA configuration by copying all
        files from the session directory to the LZA configuration directory. Files are
        overwritten as needed, and directory structure is preserved.
        
        After this operation completes, call uploadConfigurationToS3() WITHOUT any path
        parameter to upload the merged configuration.
        
        Args:
            session_id: Session identifier from start_uc_merge_session(). Required parameter.
        
        Returns:
            Dictionary with:
            - success: Operation success status
            - session_id: Session identifier
            - files_copied: Number of files copied
            - directories_created: Number of directories created
            - source: Source directory path (session)
            - destination: Destination directory path (LZA config)
            - next_steps: Guidance to call uploadConfigurationToS3()
        """
        return await copy_uc_to_lza_config(ctx, session_id)
    
    logger.info("UC merge tools registered successfully")
