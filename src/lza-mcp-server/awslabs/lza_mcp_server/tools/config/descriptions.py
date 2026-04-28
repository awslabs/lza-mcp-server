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

        Automatically selects the config source (CodeCommit or S3):
        - If repository_name is provided, or if the pipeline's source action is CodeCommit,
          files are fetched via GetFolder/GetBlob.
        - Otherwise, a ZIP is downloaded from S3 and extracted.

        PARAMETERS:
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, downloads from
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
        - bucket_name (Optional[str]): Explicit S3 bucket name override. Takes precedence over
          auto-detection. Only used for S3 source.
        - workspace_id (Optional[str]): Workspace to extract configuration into. If omitted,
          a new workspace is created automatically. The workspace_id is returned in the response.
        - path (Optional[str]): Relative path within the workspace to extract into.
          If omitted, files are extracted into the workspace root.
        - repository_name (Optional[str]): CodeCommit repository name. When provided, uses
          CodeCommit instead of S3. When omitted, auto-detection is attempted via the pipeline
          source action before falling back to S3.
        - branch (Optional[str]): CodeCommit branch to read from. Defaults to "main".
          Only used when the CodeCommit source is active.

        Note: GetFolder returns at most 1000 entries per call. LZA configuration repositories
        are well within this limit in practice.
"""

_PUT_LZA_CONFIG_SHARED = """
        Supports standard deployments (management account) and external pipeline deployments
        (CodePipeline or ECS container) identified by an Accelerator Qualifier.

        Automatically selects the destination (CodeCommit or S3):
        - If repository_name is provided, or if the pipeline's source action is CodeCommit,
          files are committed via CreateCommit (single commit, all files).
        - Otherwise, a ZIP is created and uploaded to S3.

        PARAMETERS:
        - workspace_id (str, required): Workspace containing the LZA configuration files.
        - path (str, required): Relative path within the workspace where config files reside.
          Use the same path returned by getLzaConfiguration().
        - qualifier (Optional[str]): Accelerator Qualifier for external pipeline deployments.
          Omit for standard deployments. When provided, uploads to
          {qualifier}-config-{account_id}-{region} bucket with key lza/aws-accelerator-config.zip.
        - repository_name (Optional[str]): CodeCommit repository name. When provided, uses
          CodeCommit instead of S3. When omitted, auto-detection is attempted via the pipeline
          source action before falling back to S3.
        - branch (Optional[str]): CodeCommit branch to commit to. Defaults to "main".
          Only used when the CodeCommit destination is active.
        - commit_message (Optional[str]): Commit message for CodeCommit. Auto-generated if omitted.
"""

DESCRIPTIONS = {
    "getMinimumConfiguration": {
        "standard": "Generate minimal LZA configuration templates and extract them into a workspace for quick setup",
        "disable_guidance": "Generate minimal LZA configuration templates and extract them into a workspace for quick setup",
    },
    "getLzaConfiguration": {
        "standard": (
            "Retrieve LZA configuration from S3 or CodeCommit for both standard and external pipeline deployments."
            + _GET_LZA_CONFIG_SHARED
            + """
        RECOMMENDED WORKFLOW:
        1. Run checkAwsConnectivity() to verify credentials and discover qualifiers
        2. Call getLzaConfiguration(qualifier=...) to download and extract configuration into a workspace
        3. Use workspace tools or readLzaConfigFile to inspect/edit files
        4. Call putLzaConfiguration(workspace_id=..., path=..., qualifier=...) to upload changes
        5. Call startDeployment(qualifier=...) to deploy

        IMPORTANT: The response includes workspace_id — use it in subsequent putLzaConfiguration() calls.
        If no workspace_id is provided, a new workspace is created automatically.

        RETURNS: Dictionary with success, workspace_id, workspace_created, path, file/directory counts,
        structure, config_source ("s3" or "codecommit"), and llm_instructions."""
        ),
        "disable_guidance": (
            "Retrieve LZA configuration from S3 or CodeCommit and extract it into a workspace."
            + _GET_LZA_CONFIG_SHARED
            + """
        RETURNS: Dictionary with success, workspace_id, workspace_created, path, file/directory counts,
        structure, config_source ("s3" or "codecommit"), and llm_instructions."""
        ),
    },
    "putLzaConfiguration": {
        "standard": (
            "Upload LZA configuration to S3 or CodeCommit for both standard and external pipeline deployments."
            + _PUT_LZA_CONFIG_SHARED
            + """        - bucket_name (Optional[str]): Explicit S3 bucket name override (S3 destination only).

        RECOMMENDED WORKFLOW:
        1. getLzaConfiguration(qualifier=...) — download config into a workspace
        2. Edit files using workspace tools
        3. putLzaConfiguration(workspace_id=..., path=..., qualifier=...) — upload
        4. startDeployment(qualifier=...) — deploy"""
        ),
        "disable_guidance": (
            "Upload LZA configuration to S3 or CodeCommit for both standard and external pipeline deployments."
            + _PUT_LZA_CONFIG_SHARED
            + """        - bucket_name (Optional[str]): Explicit S3 bucket name override (S3 destination only)."""
        ),
    },
}
