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

"""Additional tests for server_config.py to cover branch gaps."""

from awslabs.lza_mcp_server.server_config import (
    build_instructions,
    get_resource_instructions,
    get_workspace_instructions,
)


class TestBuildInstructionsBranches:
    """Test build_instructions branch coverage."""

    def test_without_workspaces(self):
        """Test build_instructions with include_workspaces=False."""
        result = build_instructions(
            include_uc_merge=False,
            include_workspaces=False,
            include_resources=False,
        )
        # Should not contain workspace instructions
        workspace_content = get_workspace_instructions()
        assert workspace_content not in result

    def test_without_resources(self):
        """Test build_instructions with include_resources=False."""
        result = build_instructions(
            include_uc_merge=False,
            include_workspaces=True,
            include_resources=False,
        )
        resource_content = get_resource_instructions()
        assert resource_content not in result

    def test_include_resources_default_is_true(self):
        """Test include_resources defaults to True when None."""
        result = build_instructions(
            include_uc_merge=False,
            include_workspaces=True,
            include_resources=None,
        )
        resource_content = get_resource_instructions()
        assert resource_content in result
