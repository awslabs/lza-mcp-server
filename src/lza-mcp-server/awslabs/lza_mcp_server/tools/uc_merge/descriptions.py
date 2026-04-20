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

"""Tool descriptions for UC merge MCP tools.

Each entry maps a tool name to its standard (guidance-enabled) and disable_guidance
(guidance-disabled) description strings. The manage module selects the
appropriate variant at registration time via tool_description().
"""

DESCRIPTIONS = {
    "validateLzaForUcMerge": {
        "standard": (
            "Validate that the LZA installation is fresh and compatible with UC merge. "
            "Requires a workspace_id from getLzaConfiguration() and an optional path parameter. "
            "Checks accounts-config.yaml has only 3 mandatory accounts, "
            "network-config.yaml has minimal configuration, and iam-config.yaml has minimal configuration. "
            "Call this after getLzaConfiguration() to ensure the installation is compatible with UC merge before proceeding."
        ),
        "disable_guidance": (
            "Validate that the LZA installation is fresh and compatible with UC merge. "
            "Requires a workspace_id from getLzaConfiguration() and an optional path parameter. "
            "Checks accounts-config.yaml has only 3 mandatory accounts, "
            "network-config.yaml has minimal configuration, and iam-config.yaml has minimal configuration."
        ),
    },
    "copyUcToLzaConfig": {
        "standard": (
            "Copy UC configuration from a UC workspace to an LZA workspace. "
            "Requires uc_workspace_id (from start_uc_merge_session) and lza_workspace_id (from getLzaConfiguration), "
            "with an optional path prefix for the LZA workspace destination. "
            "Merges UC files with the existing LZA configuration by copying all files from the UC workspace. "
            "Files are overwritten as needed, and directory structure is preserved. "
            "After this operation completes, call putLzaConfiguration() to upload the merged configuration."
        ),
        "disable_guidance": (
            "Copy UC configuration from a UC workspace to an LZA workspace. "
            "Requires uc_workspace_id (from start_uc_merge_session) and lza_workspace_id (from getLzaConfiguration), "
            "with an optional path prefix for the LZA workspace destination. "
            "Merges UC files with the existing LZA configuration by copying all files from the UC workspace. "
            "Files are overwritten as needed, and directory structure is preserved."
        ),
    },
    "get_uc_releases": {
        "standard": (
            "Discover available UC release versions. "
            "Scans the UC repository directory to find all available release versions "
            "of the AWS Landing Zone Accelerator Universal Configuration. Returns "
            "releases in descending version order (newest first)."
        ),
        "disable_guidance": (
            "Discover available UC release versions. "
            "Scans the UC repository directory to find all available release versions "
            "of the AWS Landing Zone Accelerator Universal Configuration. Returns "
            "releases in descending version order (newest first)."
        ),
    },
    "get_uc_network_models": {
        "standard": (
            "Get available UC network deployment models with comparison information. "
            "Dynamically discovers available network models from the specified UC release "
            "and provides comparison information to help users select the appropriate "
            "architecture for their organization."
        ),
        "disable_guidance": (
            "Get available UC network deployment models with comparison information. "
            "Dynamically discovers available network models from the specified UC release "
            "and provides comparison information to help users select the appropriate "
            "architecture for their organization."
        ),
    },
    "start_uc_merge_session": {
        "standard": (
            "Start a new UC merge session with the selected release and network model. "
            "Creates a workspace with a fresh copy of the UC configuration "
            "for the specified network model. Returns a workspace_id that must be passed to "
            "subsequent UC merge tools (getUcNetworkCustomizationGuide, copyUcToLzaConfig). "
            "Use readResource and writeWorkspaceFile to read and modify UC files in the workspace."
        ),
        "disable_guidance": (
            "Start a new UC merge session with the selected release and network model. "
            "Creates a workspace with a fresh copy of the UC configuration "
            "for the specified network model. Returns a workspace_id for the created workspace."
        ),
    },
    "getUcNetworkCustomizationGuide": {
        "standard": (
            "Get network customization guidance and file list for the workspace's network model. "
            "Requires a workspace_id from start_uc_merge_session. "
            "This tool provides metadata about which network settings are relevant for the "
            "selected network model and lists all configuration files in the workspace. "
            "Use this to understand what settings can be customized and which files are "
            "available to read."
        ),
        "disable_guidance": (
            "Get network customization guidance and file list for the workspace's network model. "
            "Requires a workspace_id from start_uc_merge_session. "
            "This tool provides metadata about which network settings are relevant for the "
            "selected network model and lists all configuration files in the workspace. "
            "Use this to understand what settings can be customized and which files are "
            "available to read."
        ),
    },
}
