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

"""Unit tests for server configuration."""

from awslabs.lza_mcp_server.server_config import (
    build_instructions,
    get_base_instructions,
    get_uc_merge_instructions,
    get_workflow_instructions,
    is_instruction_logging_enabled,
    is_resource_tools_disabled,
    is_uc_merge_enabled,
)


class TestIsUcMergeEnabled:
    """Test UC Merge enablement detection."""

    def test_enabled_with_true(self, monkeypatch):
        """Test UC Merge enabled with 'true'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "true")
        assert is_uc_merge_enabled() is True

    def test_enabled_with_1(self, monkeypatch):
        """Test UC Merge enabled with '1'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "1")
        assert is_uc_merge_enabled() is True

    def test_enabled_with_yes(self, monkeypatch):
        """Test UC Merge enabled with 'yes'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "yes")
        assert is_uc_merge_enabled() is True

    def test_enabled_case_insensitive(self, monkeypatch):
        """Test UC Merge enabled is case insensitive."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "TRUE")
        assert is_uc_merge_enabled() is True

        monkeypatch.setenv("ENABLE_UC_MERGE", "Yes")
        assert is_uc_merge_enabled() is True

    def test_disabled_with_false(self, monkeypatch):
        """Test UC Merge disabled with 'false'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "false")
        assert is_uc_merge_enabled() is False

    def test_disabled_with_0(self, monkeypatch):
        """Test UC Merge disabled with '0'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "0")
        assert is_uc_merge_enabled() is False

    def test_disabled_with_no(self, monkeypatch):
        """Test UC Merge disabled with 'no'."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "no")
        assert is_uc_merge_enabled() is False

    def test_disabled_by_default(self, monkeypatch):
        """Test UC Merge disabled by default when env var not set."""
        monkeypatch.delenv("ENABLE_UC_MERGE", raising=False)
        assert is_uc_merge_enabled() is False

    def test_disabled_with_invalid_value(self, monkeypatch):
        """Test UC Merge disabled with invalid value."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "invalid")
        assert is_uc_merge_enabled() is False


class TestIsResourceToolsDisabled:
    """Test resource tools disabled detection."""

    def test_enabled_by_default(self, monkeypatch):
        """Test resource tools enabled by default (DISABLE_RESOURCE_TOOLS defaults to false)."""
        monkeypatch.delenv("DISABLE_RESOURCE_TOOLS", raising=False)
        assert is_resource_tools_disabled() is False

    def test_disabled_with_true(self, monkeypatch):
        """Test resource tools disabled with 'true'."""
        monkeypatch.setenv("DISABLE_RESOURCE_TOOLS", "true")
        assert is_resource_tools_disabled() is True

    def test_enabled_with_false(self, monkeypatch):
        """Test resource tools enabled with 'false'."""
        monkeypatch.setenv("DISABLE_RESOURCE_TOOLS", "false")
        assert is_resource_tools_disabled() is False

    def test_disabled_with_1(self, monkeypatch):
        """Test resource tools disabled with '1'."""
        monkeypatch.setenv("DISABLE_RESOURCE_TOOLS", "1")
        assert is_resource_tools_disabled() is True

    def test_enabled_with_0(self, monkeypatch):
        """Test resource tools enabled with '0'."""
        monkeypatch.setenv("DISABLE_RESOURCE_TOOLS", "0")
        assert is_resource_tools_disabled() is False


class TestIsInstructionLoggingEnabled:
    """Test instruction logging enablement detection."""

    def test_enabled_with_true(self, monkeypatch):
        """Test instruction logging enabled with 'true'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "true")
        assert is_instruction_logging_enabled() is True

    def test_enabled_with_1(self, monkeypatch):
        """Test instruction logging enabled with '1'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "1")
        assert is_instruction_logging_enabled() is True

    def test_enabled_with_yes(self, monkeypatch):
        """Test instruction logging enabled with 'yes'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "yes")
        assert is_instruction_logging_enabled() is True

    def test_enabled_case_insensitive(self, monkeypatch):
        """Test instruction logging enabled is case insensitive."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "TRUE")
        assert is_instruction_logging_enabled() is True

        monkeypatch.setenv("LOG_INSTRUCTIONS", "Yes")
        assert is_instruction_logging_enabled() is True

    def test_disabled_with_false(self, monkeypatch):
        """Test instruction logging disabled with 'false'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "false")
        assert is_instruction_logging_enabled() is False

    def test_disabled_with_0(self, monkeypatch):
        """Test instruction logging disabled with '0'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "0")
        assert is_instruction_logging_enabled() is False

    def test_disabled_with_no(self, monkeypatch):
        """Test instruction logging disabled with 'no'."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "no")
        assert is_instruction_logging_enabled() is False

    def test_disabled_by_default(self, monkeypatch):
        """Test instruction logging disabled by default when env var not set."""
        monkeypatch.delenv("LOG_INSTRUCTIONS", raising=False)
        assert is_instruction_logging_enabled() is False

    def test_disabled_with_invalid_value(self, monkeypatch):
        """Test instruction logging disabled with invalid value."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "invalid")
        assert is_instruction_logging_enabled() is False


class TestGetBaseInstructions:
    """Test base instructions retrieval."""

    def test_returns_string(self):
        """Test base instructions returns a string."""
        result = get_base_instructions()
        assert isinstance(result, str)

    def test_contains_title(self):
        """Test base instructions contains title."""
        result = get_base_instructions()
        assert "AWS Landing Zone Accelerator (LZA) MCP Server" in result

    def test_contains_aws_services_section(self):
        """Test base instructions contains AWS Services section."""
        result = get_base_instructions()
        assert "### AWS Services" in result
        assert "checkAwsConnectivity" in result
        assert "getDeployedLzaVersion" in result

    def test_contains_config_management_section(self):
        """Test base instructions contains Configuration Management section."""
        result = get_base_instructions()
        assert "### Configuration Management" in result
        assert "getMinimumConfiguration" in result
        assert "getLzaConfiguration" in result
        assert "putLzaConfiguration" in result

    def test_contains_pipeline_management_section(self):
        """Test base instructions contains Pipeline Management section."""
        result = get_base_instructions()
        assert "### Pipeline Management" in result
        assert "startDeployment" in result
        assert "getDeploymentStatus" in result
        assert "diagnoseDeploymentErrors" in result

    def test_contains_schema_management_section(self):
        """Test base instructions contains Schema Management section."""
        result = get_base_instructions()
        assert "### Schema Management" in result
        assert "listLzaSupportedVersions" in result
        assert "searchJsonSchema" in result
        assert "getFullSchema" in result


class TestGetUcMergeInstructions:
    """Test UC Merge instructions retrieval."""

    def test_returns_string(self):
        """Test UC Merge instructions returns a string."""
        result = get_uc_merge_instructions()
        assert isinstance(result, str)

    def test_contains_uc_merge_section(self):
        """Test UC Merge instructions contains UC Merge section."""
        result = get_uc_merge_instructions()
        assert "### UC Merge Tools (Universal Configuration)" in result

    def test_contains_uc_merge_tools(self):
        """Test UC Merge instructions contains all UC Merge tools."""
        result = get_uc_merge_instructions()
        assert "validateLzaForUcMerge" in result
        assert "get_uc_releases" in result
        assert "get_uc_network_models" in result
        assert "start_uc_merge_session" in result
        assert "getUcNetworkCustomizationGuide" in result
        assert "copyUcToLzaConfig" in result
        # Dropped tools should NOT be present
        assert "readUcFile" not in result
        assert "updateUcFile" not in result


class TestGetWorkflowInstructions:
    """Test workflow instructions retrieval."""

    def test_returns_string(self):
        """Test workflow instructions returns a string."""
        result = get_workflow_instructions()
        assert isinstance(result, str)

    def test_contains_workflows_section(self):
        """Test workflow instructions contains Typical Workflows section."""
        result = get_workflow_instructions()
        assert "## Typical Workflows" in result

    def test_contains_deployment_workflow(self):
        """Test workflow instructions contains Deployment Workflow."""
        result = get_workflow_instructions()
        assert "### Deployment Workflow" in result
        assert "checkAwsConnectivity" in result
        assert "getMinimumConfiguration" in result
        assert "putLzaConfiguration" in result
        assert "startDeployment" in result
        assert "getDeploymentStatus" in result

    def test_contains_schema_query_workflow(self):
        """Test workflow instructions contains Schema Query Workflow."""
        result = get_workflow_instructions()
        assert "### Schema Query Workflow" in result
        assert "getDeployedLzaVersion" in result
        assert "searchJsonSchema" in result
        assert "getFullSchema" in result
        assert "listLzaSupportedVersions" in result


class TestBuildInstructions:
    """Test complete instructions building."""

    def test_without_uc_merge_explicit(self):
        """Test building instructions without UC Merge (explicit)."""
        result = build_instructions(include_uc_merge=False)

        assert isinstance(result, str)
        assert "AWS Landing Zone Accelerator (LZA) MCP Server" in result
        assert "### AWS Services" in result
        assert "### Configuration Management" in result
        assert "### Pipeline Management" in result
        assert "### Schema Management" in result
        assert "## Typical Workflows" in result
        assert "### UC Merge Tools" not in result

    def test_with_uc_merge_explicit(self):
        """Test building instructions with UC Merge (explicit)."""
        result = build_instructions(include_uc_merge=True)

        assert isinstance(result, str)
        assert "AWS Landing Zone Accelerator (LZA) MCP Server" in result
        assert "### AWS Services" in result
        assert "### UC Merge Tools (Universal Configuration)" in result
        assert "## Typical Workflows" in result

    def test_with_uc_merge_from_env(self, monkeypatch):
        """Test building instructions with UC Merge from environment."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "true")
        result = build_instructions()

        assert "### UC Merge Tools (Universal Configuration)" in result

    def test_without_uc_merge_from_env(self, monkeypatch):
        """Test building instructions without UC Merge from environment."""
        monkeypatch.setenv("ENABLE_UC_MERGE", "false")
        result = build_instructions()

        assert "### UC Merge Tools" not in result

    def test_default_without_uc_merge(self, monkeypatch):
        """Test building instructions defaults to no UC Merge."""
        monkeypatch.delenv("ENABLE_UC_MERGE", raising=False)
        result = build_instructions()

        assert "### UC Merge Tools" not in result

    def test_includes_workspace_instructions(self):
        """Test building instructions includes workspace instructions by default."""
        result = build_instructions(include_uc_merge=False)

        assert "## Workspaces" in result or "workspace" in result.lower()

    def test_includes_resource_instructions(self):
        """Test building instructions includes resource instructions by default."""
        result = build_instructions(include_uc_merge=False)

        assert "## Resources" in result or "resource" in result.lower()

    def test_instructions_order(self):
        """Test instructions are in correct order."""
        result = build_instructions(include_uc_merge=True)

        # Find positions of each section
        base_pos = result.find("### AWS Services")
        uc_pos = result.find("### UC Merge Tools")
        workflow_pos = result.find("## Typical Workflows")

        # Verify order: base < uc_merge < workflows
        assert base_pos < uc_pos < workflow_pos

    def test_instructions_completeness(self):
        """Test instructions contain all expected sections."""
        result = build_instructions(include_uc_merge=True)

        # All major sections should be present
        assert "### AWS Services" in result
        assert "### Configuration Management" in result
        assert "### Pipeline Management" in result
        assert "### Schema Management" in result
        assert "### UC Merge Tools" in result
        assert "### Deployment Workflow" in result
        assert "### Schema Query Workflow" in result

    def test_logging_disabled_by_default(self, monkeypatch, caplog):
        """Test instruction logging is disabled by default."""
        monkeypatch.delenv("LOG_INSTRUCTIONS", raising=False)

        with caplog.at_level("INFO"):
            build_instructions(include_uc_merge=False)

        # Should not log instructions
        assert "MCP SERVER INSTRUCTIONS" not in caplog.text

    def test_logging_enabled(self, monkeypatch, caplog):
        """Test instruction logging when enabled."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "true")

        with caplog.at_level("INFO"):
            build_instructions(include_uc_merge=False)

        # Should log instructions
        assert "MCP SERVER INSTRUCTIONS" in caplog.text
        assert "AWS Landing Zone Accelerator (LZA) MCP Server" in caplog.text

    def test_logging_includes_full_instructions(self, monkeypatch, caplog):
        """Test logged instructions match returned instructions."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "true")

        with caplog.at_level("INFO"):
            result = build_instructions(include_uc_merge=False)

        # Logged content should include the instructions
        assert result in caplog.text

    def test_guidance_disabled_returns_empty_string(self, monkeypatch):
        """When DISABLE_LLM_GUIDANCE=true, build_instructions returns empty string."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        monkeypatch.delenv("ENABLE_UC_MERGE", raising=False)
        result = build_instructions()
        assert result == ""

    def test_guidance_disabled_with_uc_merge_still_empty(self, monkeypatch):
        """Guidance disabled takes precedence even when UC merge is enabled."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        monkeypatch.setenv("ENABLE_UC_MERGE", "true")
        result = build_instructions()
        assert result == ""

    def test_logging_with_uc_merge(self, monkeypatch, caplog):
        """Test instruction logging includes UC Merge when enabled."""
        monkeypatch.setenv("LOG_INSTRUCTIONS", "true")
        monkeypatch.setenv("ENABLE_UC_MERGE", "true")

        with caplog.at_level("INFO"):
            build_instructions()

        # Should log instructions with UC Merge
        assert "MCP SERVER INSTRUCTIONS" in caplog.text
        assert "UC Merge Tools" in caplog.text
