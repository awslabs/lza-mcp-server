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
            "Checks accounts-config.yaml has only 3 mandatory accounts, "
            "network-config.yaml has minimal configuration, and iam-config.yaml has minimal configuration. "
            "Call this after getLzaConfiguration() to ensure the installation is compatible with UC merge before proceeding."
        ),
        "disable_guidance": (
            "Validate that the LZA installation is fresh and compatible with UC merge. "
            "Checks accounts-config.yaml has only 3 mandatory accounts, "
            "network-config.yaml has minimal configuration, and iam-config.yaml has minimal configuration."
        ),
    },
    "readUcFile": {
        "standard": (
            "Read a file from the UC session directory. "
            "Reads files from the session created by start_uc_merge_session(). "
            "Validates paths for security and provides context-aware guidance based on the file being read. "
            "For UC merge workflow, review at minimum: "
            "accounts-config.yaml (account structure and emails) and "
            "replacements-config.yaml (network settings and global replacements)."
        ),
        "disable_guidance": (
            "Read a file from the UC session directory. "
            "Reads files from the session created by start_uc_merge_session(). "
            "Validates paths for security."
        ),
    },
    "copyUcToLzaConfig": {
        "standard": (
            "Copy UC configuration from session directory to extracted LZA configuration directory. "
            "Merges UC files with the existing LZA configuration by copying all files from the session directory. "
            "Files are overwritten as needed, and directory structure is preserved. "
            "After this operation completes, call putLzaConfiguration() WITHOUT any path parameter to upload the merged configuration."
        ),
        "disable_guidance": (
            "Copy UC configuration from session directory to extracted LZA configuration directory. "
            "Merges UC files with the existing LZA configuration by copying all files from the session directory. "
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
            "Creates a session directory with a fresh copy of the UC configuration "
            "for the specified network model. The session_id must be passed to "
            "subsequent UC merge tools (read_uc_file, update_uc_file, copy_uc_to_lza_config). "
            "This ensures each merge session works with pristine UC files and doesn't "
            "interfere with other sessions."
        ),
        "disable_guidance": (
            "Start a new UC merge session with the selected release and network model. "
            "Creates a session directory with a fresh copy of the UC configuration "
            "for the specified network model. "
        ),
    },
    "getUcNetworkCustomizationGuide": {
        "standard": (
            "Get network customization guidance and file list for the session's network model. "
            "This tool provides metadata about which network settings are relevant for the "
            "selected network model and lists all configuration files in the session directory. "
            "Use this to understand what settings can be customized and which files are "
            "available to read."
        ),
        "disable_guidance": (
            "Get network customization guidance and file list for the session's network model. "
            "This tool provides metadata about which network settings are relevant for the "
            "selected network model and lists all configuration files in the session directory. "
            "Use this to understand what settings can be customized and which files are "
            "available to read."
        ),
    },
    "updateUcFile": {
        "standard": (
            "Update a UC configuration file in the session directory with new values. "
            "This tool allows updating UC configuration files with user customizations. "
            "It validates the session, file existence, and applies security checks before "
            "updating. After updates, it validates YAML syntax and performs basic value "
            "validation for CIDR ranges and numeric values."
        ),
        "disable_guidance": (
            "Update a UC configuration file in the session directory with new values. "
            "This tool allows updating UC configuration files with user customizations. "
            "It validates the session, file existence, and applies security checks before "
            "updating. After updates, it validates YAML syntax and performs basic value "
            "validation for CIDR ranges and numeric values."
        ),
    },
}
