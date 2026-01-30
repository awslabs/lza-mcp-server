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

"""Unit tests for IAM permission guidance in aws_access module."""

from awslabs.lza_mcp_server.aws_access import get_iam_permission_guidance


class TestPipelineReleaseGuidance:
    """Test IAM permission guidance for pipeline release operations."""

    def test_get_iam_guidance_for_pipeline_release(self):
        """Test IAM permission guidance for pipeline release operations."""
        guidance = get_iam_permission_guidance(
            "starting pipeline execution", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)
        assert any("Version" in step for step in guidance)

    def test_get_iam_guidance_for_pipeline_release_with_specific_error(self):
        """Test IAM guidance for pipeline release with specific error message."""
        guidance = get_iam_permission_guidance(
            "starting pipeline",
            "User is not authorized to perform: codepipeline:StartPipelineExecution",
        )

        assert any(
            "StartPipelineExecution permission is missing" in step for step in guidance
        )
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)


class TestPipelineStatusGuidance:
    """Test IAM permission guidance for pipeline status operations."""

    def test_get_iam_guidance_for_pipeline_status(self):
        """Test IAM permission guidance for pipeline status operations."""
        guidance = get_iam_permission_guidance(
            "getting status for pipeline", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:GetPipelineExecution" in step for step in guidance)
        assert any("codepipeline:GetPipelineState" in step for step in guidance)
        assert any("codepipeline:ListPipelineExecutions" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_guidance_for_pipeline_status_with_specific_error(self):
        """Test IAM guidance for pipeline status with specific error message."""
        guidance = get_iam_permission_guidance(
            "getting status",
            "User is not authorized to perform: codepipeline:GetPipeline",
        )

        assert any("GetPipeline permission is missing" in step for step in guidance)
        assert any("codepipeline:GetPipeline" in step for step in guidance)


class TestErrorDiagnosisGuidance:
    """Test IAM permission guidance for error diagnosis operations."""

    def test_get_iam_guidance_for_error_diagnosis(self):
        """Test IAM permission guidance for error diagnosis operations."""
        guidance = get_iam_permission_guidance(
            "diagnosing pipeline errors", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:GetPipelineExecution" in step for step in guidance)
        assert any("codepipeline:ListPipelineExecutions" in step for step in guidance)
        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_guidance_for_codebuild_operations(self):
        """Test IAM permission guidance for CodeBuild operations."""
        guidance = get_iam_permission_guidance(
            "retrieving build logs", "codebuild:BatchGetBuilds"
        )

        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("logs:GetLogEvents" in step for step in guidance)

    def test_get_iam_guidance_for_codebuild_with_specific_error(self):
        """Test IAM guidance for CodeBuild with specific error message."""
        guidance = get_iam_permission_guidance(
            "error diagnosis",
            "User is not authorized to perform: codebuild:BatchGetBuilds",
        )

        assert any(
            "CodeBuild access permission is missing" in step for step in guidance
        )
        assert any("codebuild:BatchGetBuilds" in step for step in guidance)


class TestLogsGuidance:
    """Test IAM permission guidance for CloudWatch Logs operations."""

    def test_get_iam_guidance_for_logs_operations(self):
        """Test IAM permission guidance for CloudWatch Logs operations."""
        guidance = get_iam_permission_guidance(
            "accessing build logs", "logs:GetLogEvents"
        )

        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("codebuild:BatchGetBuilds" in step for step in guidance)

    def test_get_iam_guidance_for_logs_with_specific_error(self):
        """Test IAM guidance for CloudWatch Logs with specific error message."""
        guidance = get_iam_permission_guidance(
            "error diagnosis",
            "User is not authorized to perform: logs:GetLogEvents",
        )

        assert any(
            "CloudWatch Logs access permission is missing" in step for step in guidance
        )
        assert any("logs:GetLogEvents" in step for step in guidance)


class TestGeneralOperationsGuidance:
    """Test IAM permission guidance for general operations."""

    def test_get_iam_guidance_for_general_operations(self):
        """Test IAM guidance for general operations without specific context."""
        guidance = get_iam_permission_guidance(
            "general pipeline operation", "Access denied"
        )

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:GetPipelineExecution" in step for step in guidance)
        assert any("codepipeline:GetPipelineState" in step for step in guidance)
        assert any("codepipeline:ListPipelineExecutions" in step for step in guidance)
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)
        assert any("codebuild:BatchGetBuilds" in step for step in guidance)
        assert any("logs:GetLogEvents" in step for step in guidance)
        assert any("Sample IAM policy" in step for step in guidance)

    def test_get_iam_guidance_includes_base_guidance(self):
        """Test that IAM guidance includes base guidance for all operations."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any("IAM permissions" in step for step in guidance)
        assert any("IAM user, role, or group" in step for step in guidance)


class TestIAMPolicyStructure:
    """Test IAM policy structure in guidance."""

    def test_iam_policy_includes_version(self):
        """Test that IAM policy includes version field."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any('"Version": "2012-10-17"' in step for step in guidance)

    def test_iam_policy_includes_statement(self):
        """Test that IAM policy includes statement field."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any('"Statement"' in step for step in guidance)

    def test_iam_policy_includes_effect(self):
        """Test that IAM policy includes effect field."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any('"Effect": "Allow"' in step for step in guidance)

    def test_iam_policy_includes_action(self):
        """Test that IAM policy includes action field."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any('"Action"' in step for step in guidance)

    def test_iam_policy_includes_resource(self):
        """Test that IAM policy includes resource field."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any('"Resource"' in step for step in guidance)

    def test_iam_policy_includes_codepipeline_actions(self):
        """Test that IAM policy includes CodePipeline actions."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any("codepipeline:GetPipeline" in step for step in guidance)
        assert any("codepipeline:StartPipelineExecution" in step for step in guidance)

    def test_iam_policy_includes_codebuild_actions(self):
        """Test that IAM policy includes CodeBuild actions."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any("codebuild:BatchGetBuilds" in step for step in guidance)

    def test_iam_policy_includes_logs_actions(self):
        """Test that IAM policy includes CloudWatch Logs actions."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert any("logs:GetLogEvents" in step for step in guidance)


class TestResourceARNs:
    """Test resource ARN formatting in guidance."""

    def test_guidance_includes_codepipeline_arn(self):
        """Test that guidance includes CodePipeline resource ARN."""
        guidance = get_iam_permission_guidance("pipeline release", "Access denied")

        assert any("arn:aws:codepipeline:" in step for step in guidance)

    def test_guidance_includes_codebuild_arn(self):
        """Test that guidance includes CodeBuild resource ARN."""
        guidance = get_iam_permission_guidance("error diagnosis", "Access denied")

        assert any("arn:aws:codebuild:" in step for step in guidance)

    def test_guidance_includes_logs_arn(self):
        """Test that guidance includes CloudWatch Logs resource ARN."""
        guidance = get_iam_permission_guidance("error diagnosis", "Access denied")

        assert any("arn:aws:logs:" in step for step in guidance)

    def test_guidance_includes_wildcard_resource(self):
        """Test that guidance includes wildcard resource."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        # Check for wildcard in pipeline ARN
        assert any(":pipeline/*" in step for step in guidance)


class TestEdgeCases:
    """Test edge cases in IAM permission guidance."""

    def test_guidance_with_empty_operation(self):
        """Test IAM guidance with empty operation string."""
        guidance = get_iam_permission_guidance("", "Access denied")

        # Should still return general guidance
        assert len(guidance) > 0
        assert any("IAM permissions" in step for step in guidance)

    def test_guidance_with_empty_error_message(self):
        """Test IAM guidance with empty error message."""
        guidance = get_iam_permission_guidance("test operation", "")

        # Should still return guidance
        assert len(guidance) > 0
        assert any("IAM permissions" in step for step in guidance)

    def test_guidance_with_case_variations(self):
        """Test IAM guidance with case variations in operation."""
        guidance_lower = get_iam_permission_guidance(
            "pipeline release", "Access denied"
        )
        guidance_mixed = get_iam_permission_guidance(
            "Pipeline Release", "Access denied"
        )

        # Both should contain similar guidance
        assert any(
            "codepipeline:StartPipelineExecution" in step for step in guidance_lower
        )
        assert any(
            "codepipeline:StartPipelineExecution" in step for step in guidance_mixed
        )

    def test_guidance_returns_list(self):
        """Test that IAM guidance returns a list."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert isinstance(guidance, list)
        assert len(guidance) > 0

    def test_guidance_returns_strings(self):
        """Test that IAM guidance returns list of strings."""
        guidance = get_iam_permission_guidance("test operation", "Access denied")

        assert all(isinstance(step, str) for step in guidance)
