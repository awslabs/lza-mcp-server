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

"""Tool descriptions for AWS service MCP tools.

Each entry maps a tool name to its standard (guidance-enabled) and disable_guidance
(guidance-disabled) description strings. The manage module selects the
appropriate variant at registration time via tool_description().
"""

DESCRIPTIONS = {
    "checkAwsConnectivity": {
        "standard": "Verify AWS credentials and connectivity to ensure proper access to AWS services",
        "disable_guidance": "Verify AWS credentials and connectivity to ensure proper access to AWS services",
    },
    "getDeployedLzaVersion": {
        "standard": "Get the currently deployed LZA version from the environment by reading the SSM parameter",
        "disable_guidance": "Get the currently deployed LZA version from the environment by reading the SSM parameter",
    },
}
