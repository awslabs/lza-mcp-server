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

"""Tool descriptions for configuration MCP tools.

Each entry maps a tool name to its standard (guidance-enabled) and disable_guidance
(guidance-disabled) description strings. The manage module selects the
appropriate variant at registration time via tool_description().
"""

_GET_LZA_CONFIG_SHARED = """
        Supports standard deployments (management account) and external pipeline deployments
        (CodePipeline or ECS container) identified by an Accelerator Qualifier.

        PARAMETERS:
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, downloads from
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
        - bucket_name (Optional[str]): Explicit bucket name override. Takes precedence over
          auto-detection.
"""

_PUT_LZA_CONFIG_SHARED = """
        Supports standard deployments (management account) and external pipeline deployments
        (CodePipeline or ECS container) identified by an Accelerator Qualifier.

        PARAMETERS:
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, uploads to
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
"""

_UPDATE_LZA_CONFIG_SHARED = """Update an LZA configuration file in the extracted configuration directory.

        Supports three mutually exclusive modes:

        MODE 1 — Update existing values (use 'updates'):
            Modify existing key-value pairs using dot-notation paths with optional
            array index syntax. Also adds new keys if they don't exist yet.

        MODE 2 — Insert a new item into a list (use 'insert_path' + 'insert_value'):
            Append a new object to an existing YAML list, such as adding a new VPC
            to the 'vpcs' array or a new workload account.

        MODE 3 — Delete a key or list item (use 'delete_path'):
            Remove a key from a dict or an item from a list using dot-notation path.

        PARAMETERS:
        - file_path (str): Relative path to config file (e.g., "network-config.yaml"). Required.
        - updates (dict, optional): Key-value pairs to set. Keys use dot/index notation.
        - insert_path (str, optional): Dot-notation path to a list to append to.
        - insert_value (dict, optional): Object to append at insert_path.
        - delete_path (str, optional): Dot-notation path to the key or list item to remove.

        IMPORTANT: 'updates', 'insert_path'/'insert_value', and 'delete_path' are mutually exclusive.

        EXAMPLES:
            # Update existing values
            updateLzaConfigFile(file_path="network-config.yaml", updates={"vpcs[0].vpcName": "prod-vpc"})

            # Insert a new VPC
            updateLzaConfigFile(
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value={"vpcName": "dev-vpc", "account": "Development", "cidrs": [{"value": "10.3.0.0/16"}]}
            )

            # Add a new workload account
            updateLzaConfigFile(
                file_path="accounts-config.yaml",
                insert_path="workloadAccounts",
                insert_value={"name": "SharedServices", "email": "shared@example.com", "organizationalUnit": "Infrastructure"}
            )

            # Remove the third VPC
            updateLzaConfigFile(file_path="network-config.yaml", delete_path="vpcs[2]")

            # Remove an entire top-level key
            updateLzaConfigFile(file_path="network-config.yaml", delete_path="endpointPolicies")

        IMPORTANT: 'updates', 'insert_path'/'insert_value', and 'delete_path' are mutually exclusive."""

_CREATE_LZA_CONFIG_SHARED = """Create a new configuration file in the extracted LZA configuration directory.

        Creates YAML (.yaml, .yml) or JSON (.json) files based on the file extension.
        Useful for adding new policy files (JSON), custom configuration files, or
        any additional files needed by the LZA configuration.

        PARAMETERS:
        - file_path (str): Relative path for the new file. The extension determines
          the format (.yaml/.yml for YAML, .json for JSON). Required.
        - content (dict): Dictionary representing the file content to write. Required.
        - overwrite (bool): If True, overwrite an existing file. Defaults to False.
        - json_indent (int or str, optional): Indentation for JSON files. Accepts 2, 4,
          or "tab". Ignored for YAML files. Defaults to 2.

        EXAMPLES:
            # Create a JSON IAM policy file
            createLzaConfigFile(
                file_path="iam-policies/boundary-policy.json",
                content={
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}]
                }
            )

            # Create a YAML configuration file
            createLzaConfigFile(
                file_path="custom-config.yaml",
                content={"rules": [{"name": "require-tag", "enabled": True}]}
            )

            # Create a JSON file with tab indentation
            createLzaConfigFile(
                file_path="policy.json",
                content={"Version": "2012-10-17", "Statement": []},
                json_indent="tab"
            )

            # Create a JSON file with 4-space indentation
            createLzaConfigFile(
                file_path="policy.json",
                content={"Version": "2012-10-17", "Statement": []},
                json_indent=4
            )
"""

DESCRIPTIONS = {
    "getMinimumConfiguration": {
        "standard": "Generate minimal LZA configuration templates for quick setup",
        "disable_guidance": "Generate minimal LZA configuration templates for quick setup",
    },
    "getLzaConfiguration": {
        "standard": (
            "Retrieve LZA configuration from S3 for both standard and external pipeline deployments."
            + _GET_LZA_CONFIG_SHARED
            + """
        RECOMMENDED WORKFLOW:
        1. Run checkAwsConnectivity() to verify credentials and discover qualifiers
        2. Call getLzaConfiguration(qualifier=...) to download and extract configuration
        3. Use 'host_path' from the response to inspect/edit files
        4. Call putLzaConfiguration(qualifier=...) to upload changes (no path needed)
        5. Call startDeployment(qualifier=...) to deploy

        IMPORTANT: Use 'host_path' from the response to access files for inspection.
        The 'container_path' is internal Docker path only.

        NOTE: Automatic cleanup occurs on next retrieval to keep the file system clean.

        RETURNS: Dictionary with success, container_path, host_path, file/directory counts,
        structure, bucket_name, object_key, qualifier, and llm_instructions."""
        ),
        "disable_guidance": (
            "Retrieve LZA configuration from S3 and extract it locally."
            + _GET_LZA_CONFIG_SHARED
            + """
        RETURNS: Dictionary with success, container_path, host_path, file/directory counts,
        structure, bucket_name, object_key, qualifier, and llm_instructions."""
        ),
    },
    "putLzaConfiguration": {
        "standard": (
            "Upload LZA configuration to S3 for both standard and external pipeline deployments."
            + _PUT_LZA_CONFIG_SHARED
            + """        - config_path (Optional[str]): Path to config folder WITHIN the container.
          Leave empty to auto-detect from getLzaConfiguration().
        - bucket_name (Optional[str]): Explicit bucket name override.

        IMPORTANT: This server runs in Docker. If you used getLzaConfiguration(), leave
        config_path empty — the tool auto-detects the retrieved configuration.

        RECOMMENDED WORKFLOW:
        1. getLzaConfiguration(qualifier=...) — download config
        2. Edit files via host_path
        3. putLzaConfiguration(qualifier=...) — upload (no path needed)
        4. startDeployment(qualifier=...) — deploy"""
        ),
        "disable_guidance": (
            "Upload LZA configuration to S3 for both standard and external pipeline deployments."
            + _PUT_LZA_CONFIG_SHARED
            + """        - config_path (Optional[str]): Path to config folder WITHIN the container.
          Leave empty to auto-detect.
        - bucket_name (Optional[str]): Explicit bucket name override."""
        ),
    },
    "readLzaConfigFile": {
        "standard": "Read a configuration file from the extracted LZA configuration directory",
        "disable_guidance": "Read a configuration file from the extracted LZA configuration directory",
    },
    "updateLzaConfigFile": {
        "standard": (
            _UPDATE_LZA_CONFIG_SHARED
            + "\n\n        WORKFLOW: getLzaConfiguration() → readLzaConfigFile() → updateLzaConfigFile() → putLzaConfiguration() → startDeployment()"
        ),
        "disable_guidance": _UPDATE_LZA_CONFIG_SHARED,
    },
    "createLzaConfigFile": {
        "standard": (
            _CREATE_LZA_CONFIG_SHARED
            + "\n        WORKFLOW: getLzaConfiguration() → createLzaConfigFile() → putLzaConfiguration() → startDeployment()"
        ),
        "disable_guidance": (
            _CREATE_LZA_CONFIG_SHARED
            + "\n        RETURNS: Dictionary with success status, file path, and operation details."
        ),
    },
}
