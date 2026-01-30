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

"""Unit tests for manage_pipeline_tools helper functions."""

from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
    truncate_logs,
    format_success_response,
    get_stage_description,
    get_action_description,
    extract_create_failed_error,
    extract_error_line,
)


class TestLogTruncation:
    """Test log truncation functionality."""

    def test_truncate_logs_no_truncation_needed(self):
        """Test log truncation when content is within limits."""
        short_content = "This is a short log message"
        result = truncate_logs(short_content)

        assert result == short_content
        assert "[TRUNCATED:" not in result

    def test_truncate_logs_with_default_max_size(self):
        """Test log truncation with default max size."""
        large_content = "x" * 60000
        result = truncate_logs(large_content)

        assert len(result) < len(large_content)
        assert "[TRUNCATED:" in result
        assert "characters removed" in result

    def test_truncate_logs_with_custom_max_size(self):
        """Test log truncation with custom max size."""
        content = "x" * 2000
        result = truncate_logs(content, max_size=1000)

        assert len(result) < len(content)
        assert "[TRUNCATED:" in result
        assert "characters removed" in result

    def test_truncate_logs_preserves_start_and_end(self):
        """Test that truncation preserves start and end of logs."""
        content = "START" + ("x" * 10000) + "END"
        result = truncate_logs(content, max_size=1000)

        assert result.startswith("START")
        assert result.endswith("END")
        assert "[TRUNCATED:" in result

    def test_truncate_logs_calculates_correct_truncation_size(self):
        """Test that truncation message shows correct character count."""
        content = "x" * 10000
        result = truncate_logs(content, max_size=1000)

        # Extract the truncation count from the message
        import re

        match = re.search(r"\[TRUNCATED: (\d+) characters removed\]", result)
        assert match is not None

        truncated_count = int(match.group(1))
        # Verify the count is reasonable (should be around 9000)
        assert truncated_count > 8000
        assert truncated_count < 10000

    def test_truncate_logs_empty_content(self):
        """Test log truncation with empty content."""
        result = truncate_logs("")
        assert result == ""

    def test_truncate_logs_exactly_at_limit(self):
        """Test log truncation when content is exactly at limit."""
        content = "x" * 1000
        result = truncate_logs(content, max_size=1000)

        assert result == content
        assert "[TRUNCATED:" not in result


class TestResponseFormatting:
    """Test response formatting functionality."""

    def test_format_success_response_basic(self):
        """Test basic success response formatting."""
        data = {"pipeline_name": "test-pipeline"}
        message = "Operation completed successfully"

        result = format_success_response(data, message)

        assert result["success"] is True
        assert result["message"] == message
        assert result["pipeline_name"] == "test-pipeline"

    def test_format_success_response_with_multiple_fields(self):
        """Test success response with multiple data fields."""
        data = {
            "pipeline_name": "test-pipeline",
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "status": "InProgress",
        }
        message = "Pipeline started"

        result = format_success_response(data, message)

        assert result["success"] is True
        assert result["message"] == message
        assert result["pipeline_name"] == "test-pipeline"
        assert result["execution_id"] == "12345678-1234-1234-1234-123456789012"
        assert result["status"] == "InProgress"

    def test_format_success_response_with_nested_data(self):
        """Test success response with nested data structures."""
        data = {
            "pipeline_name": "test-pipeline",
            "stages": [
                {"name": "Source", "status": "Succeeded"},
                {"name": "Build", "status": "InProgress"},
            ],
        }
        message = "Pipeline status retrieved"

        result = format_success_response(data, message)

        assert result["success"] is True
        assert result["message"] == message
        assert len(result["stages"]) == 2
        assert result["stages"][0]["name"] == "Source"

    def test_format_success_response_empty_data(self):
        """Test success response with empty data."""
        data = {}
        message = "Operation completed"

        result = format_success_response(data, message)

        assert result["success"] is True
        assert result["message"] == message
        assert len(result) == 2  # Only success and message


class TestStageDescriptions:
    """Test stage description functionality."""

    def test_get_stage_description_source(self):
        """Test getting description for Source stage."""
        description = get_stage_description("Source")

        assert "GitHub" in description
        assert "configuration files" in description
        assert "aws-accelerator-config" in description

    def test_get_stage_description_build(self):
        """Test getting description for Build stage."""
        description = get_stage_description("Build")

        assert "Transpiles" in description
        assert "validation" in description

    def test_get_stage_description_deploy(self):
        """Test getting description for Deploy stage."""
        description = get_stage_description("Deploy")

        assert "infrastructure" in description
        assert "networking" in description
        assert "security" in description

    def test_get_stage_description_security_audit_variants(self):
        """Test getting description for SecurityAudit stage variants."""
        # Test both naming conventions
        description1 = get_stage_description("SecurityAudit")
        description2 = get_stage_description("Security_Audit")

        assert "Macie" in description1
        assert "GuardDuty" in description1
        assert "Security Hub" in description1

        assert description1 == description2

    def test_get_stage_description_unknown_stage(self):
        """Test getting description for unknown stage."""
        stage_name = "UnknownStage"
        description = get_stage_description(stage_name)

        assert f"Stage: {stage_name}" in description

    def test_get_stage_description_all_known_stages(self):
        """Test that all known stages have descriptions."""
        known_stages = [
            "Source",
            "Build",
            "Prepare",
            "Accounts",
            "Bootstrap",
            "Review",
            "Logging",
            "Organization",
            "SecurityAudit",
            "Security_Audit",
            "Deploy",
        ]

        for stage in known_stages:
            description = get_stage_description(stage)
            assert description is not None
            assert len(description) > 0
            # Should not be the default "Stage: X" format for known stages
            if stage not in ["Security_Audit"]:  # Security_Audit maps to SecurityAudit
                assert not description.startswith("Stage:")


class TestActionDescriptions:
    """Test action description functionality."""

    def test_get_action_description_network_prepare(self):
        """Test getting description for Network_Prepare action."""
        description = get_action_description("Network_Prepare")

        assert "Transit Gateway" in description
        assert "RAM shares" in description

    def test_get_action_description_security(self):
        """Test getting description for Security action."""
        description = get_action_description("Security")

        assert "security services" in description
        assert "member account" in description

    def test_get_action_description_customizations(self):
        """Test getting description for Customizations action."""
        description = get_action_description("Customizations")

        assert "CloudFormation" in description
        assert "optional" in description

    def test_get_action_description_finalize(self):
        """Test getting description for Finalize action."""
        description = get_action_description("Finalize")

        assert "quarantine" in description
        assert "SCPs" in description

    def test_get_action_description_unknown_action(self):
        """Test getting description for unknown action."""
        action_name = "UnknownAction"
        description = get_action_description(action_name)

        assert f"Action: {action_name}" in description

    def test_get_action_description_all_known_actions(self):
        """Test that all known actions have descriptions."""
        known_actions = [
            "Network_Prepare",
            "Security",
            "Operations",
            "Network_VPCs",
            "Security_Resources",
            "Network_Associations",
            "Customizations",
            "Finalize",
        ]

        for action in known_actions:
            description = get_action_description(action)
            assert description is not None
            assert len(description) > 0
            # Should not be the default "Action: X" format for known actions
            assert not description.startswith("Action:")


class TestErrorExtraction:
    """Test error extraction functionality."""

    def test_extract_create_failed_error_found(self):
        """Test extracting CREATE_FAILED error when present."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing CloudFormation stack
        AWSAccelerator-Stack | CREATE_FAILED | Custom::CreatePolicy | Resource
        [2024-01-15 10:31:00] Deployment failed
        """

        error = extract_create_failed_error(logs_content)

        assert error is not None
        assert "CREATE_FAILED" in error
        assert "AWSAccelerator-Stack" in error

    def test_extract_create_failed_error_not_found(self):
        """Test extracting CREATE_FAILED error when not present."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        [2024-01-15 10:31:00] Deployment completed
        """

        error = extract_create_failed_error(logs_content)
        assert error is None

    def test_extract_create_failed_error_empty_logs(self):
        """Test extracting CREATE_FAILED error from empty logs."""
        error = extract_create_failed_error("")
        assert error is None

        error = extract_create_failed_error(None)
        assert error is None

    def test_extract_create_failed_error_first_occurrence(self):
        """Test that only first CREATE_FAILED error is extracted."""
        logs_content = """
        First CREATE_FAILED error line
        Some other content
        Second CREATE_FAILED error line
        """

        error = extract_create_failed_error(logs_content)
        assert error == "First CREATE_FAILED error line"

    def test_extract_create_failed_error_whitespace_handling(self):
        """Test CREATE_FAILED error extraction with whitespace."""
        logs_content = """
        
           CREATE_FAILED error with whitespace   
        
        """

        error = extract_create_failed_error(logs_content)
        assert error == "CREATE_FAILED error with whitespace"

    def test_extract_error_line_found(self):
        """Test extracting | error | line when present."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        2024-01-15T10:30:30.000Z | error | Configuration validation failed
        [2024-01-15 10:31:00] Deployment failed
        """

        error = extract_error_line(logs_content)

        assert error is not None
        assert "| error |" in error
        assert "Configuration validation failed" in error

    def test_extract_error_line_not_found(self):
        """Test extracting | error | line when not present."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        [2024-01-15 10:31:00] Deployment completed
        """

        error = extract_error_line(logs_content)
        assert error is None

    def test_extract_error_line_empty_logs(self):
        """Test extracting | error | line from empty logs."""
        error = extract_error_line("")
        assert error is None

        error = extract_error_line(None)
        assert error is None

    def test_extract_error_line_first_occurrence(self):
        """Test that only first | error | line is extracted."""
        logs_content = """
        First | error | line
        Some other content
        Second | error | line
        """

        error = extract_error_line(logs_content)
        assert error == "First | error | line"

    def test_extract_error_line_whitespace_handling(self):
        """Test | error | line extraction with whitespace."""
        logs_content = """
        
           | error | line with whitespace   
        
        """

        error = extract_error_line(logs_content)
        assert error == "| error | line with whitespace"


class TestErrorExtractionFallback:
    """Test error extraction fallback logic."""

    def test_error_extraction_priority_cloudformation_first(self):
        """Test that CloudFormation errors take priority over general errors."""
        logs_content = """
        2024-01-15T10:30:30.000Z | error | Some general error
        AWSAccelerator-Stack | CREATE_FAILED | Resource creation failed
        """

        cf_error = extract_create_failed_error(logs_content)
        general_error = extract_error_line(logs_content)

        # Both should be found
        assert cf_error is not None
        assert "CREATE_FAILED" in cf_error

        assert general_error is not None
        assert "| error |" in general_error

        # But CloudFormation error should be preferred in actual usage
        assert cf_error != general_error

    def test_error_extraction_fallback_to_general(self):
        """Test fallback to general error when no CloudFormation error."""
        logs_content = """
        2024-01-15T10:30:30.000Z | error | Configuration validation failed
        [2024-01-15 10:31:00] Deployment failed
        """

        cf_error = extract_create_failed_error(logs_content)
        general_error = extract_error_line(logs_content)

        assert cf_error is None
        assert general_error is not None
        assert "Configuration validation failed" in general_error

    def test_error_extraction_no_errors_found(self):
        """Test when neither error pattern is found."""
        logs_content = """
        [2024-01-15 10:30:00] Starting deployment
        [2024-01-15 10:30:30] Processing configuration
        [2024-01-15 10:31:00] Deployment completed
        """

        cf_error = extract_create_failed_error(logs_content)
        general_error = extract_error_line(logs_content)

        assert cf_error is None
        assert general_error is None
