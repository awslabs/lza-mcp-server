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

"""Tool descriptions for schema MCP tools.

Each entry maps a tool name to its standard (guidance-enabled) and disable_guidance
(guidance-disabled) description strings. The manage module selects the
appropriate variant at registration time via tool_description().
"""

DESCRIPTIONS = {
    "searchJsonSchema": {
        "standard": (
            "Search through LZA JSON schemas to find specific properties and configurations. "
            "Searches ACROSS ALL SCHEMAS for the specified version. For schema-specific queries, "
            "use getFullSchema instead. TIP: Use getDeployedLzaVersion first to get the correct "
            "lza_version parameter for your environment."
        ),
        "disable_guidance": (
            "Search through LZA JSON schemas to find specific properties and configurations. "
            "Searches across all schemas for the specified version."
        ),
    },
    "getFullSchema": {
        "standard": (
            "Retrieve complete LZA configuration JSON schemas with optional property filtering. "
            "Use this for schema-specific queries with the schema_path parameter. TIP: Use "
            "getDeployedLzaVersion first to get the correct lza_version parameter for your environment."
        ),
        "disable_guidance": (
            "Retrieve complete LZA configuration JSON schemas with optional property filtering. "
            "Use schema_path to target a specific schema file."
        ),
    },
    "listLzaSupportedVersions": {
        "standard": "List all supported LZA versions with their schema information",
        "disable_guidance": "List all supported LZA versions with their schema information",
    },
}
