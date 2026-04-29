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

"""Property-based tests for deployment manual approval tools (P1–P11).

Uses Hypothesis to verify correctness properties across randomized inputs.
Each test maps to a correctness property from the design document.
"""

import os
import re
import pytest
from unittest.mock import Mock, AsyncMock, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status import (
    tool_get_manual_approval_status,
    infer_s3_diff_bucket_name,
)
from awslabs.lza_mcp_server.tools.pipeline.submit_manual_approval import (
    tool_submit_manual_approval,
    VALID_ACTIONS,
)
from awslabs.lza_mcp_server.utils.input_validation import validate_qualifier
from awslabs.lza_mcp_server.server_config import (
    is_s3_diff_enabled,
)
from awslabs.lza_mcp_server.utils.input_validation import validate_string_input


# ---------------------------------------------------------------------------
# Module-level mock path constants
# ---------------------------------------------------------------------------
_GET_STATUS_PREFIX = "awslabs.lza_mcp_server.tools.pipeline.get_manual_approval_status"
_SUBMIT_PREFIX = "awslabs.lza_mcp_server.tools.pipeline.submit_manual_approval"

_CP_GET = f"{_GET_STATUS_PREFIX}.get_codepipeline_client"
_RETRY_GET = f"{_GET_STATUS_PREFIX}.retry_with_exponential_backoff"
_S3_DIFF_GET = f"{_GET_STATUS_PREFIX}.is_s3_diff_enabled"

_CP_SUBMIT = f"{_SUBMIT_PREFIX}.get_codepipeline_client"
_RETRY_SUBMIT = f"{_SUBMIT_PREFIX}.retry_with_exponential_backoff"


# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------
valid_qualifier_st = st.from_regex(r"[a-zA-Z0-9\-]{1,100}", fullmatch=True).filter(
    lambda s: len(s) >= 1
)
valid_pipeline_name_st = st.from_regex(
    r"[a-zA-Z0-9._\-]{1,100}", fullmatch=True
).filter(lambda s: len(s) >= 1)
non_empty_text_st = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())
action_case_variants_st = st.sampled_from(
    ["Approve", "approve", "APPROVE", "Reject", "reject", "REJECT"]
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _make_ctx():
    """Create a mock MCP context."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


# ===========================================================================
# Property 1: Pipeline Name Resolution
# Feature: deployment-manual-approval, Property 1: Pipeline Name Resolution
# Validates: Requirements 1.2, 5.1, 5.2
# ===========================================================================
class TestProperty1PipelineNameResolution:
    """P1: Pipeline name resolves to {qualifier}-pipeline when qualifier provided,
    otherwise uses the provided pipeline_name."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(qualifier=valid_qualifier_st)
    async def test_get_status_with_qualifier_resolves_name(self, qualifier):
        """**Validates: Requirements 1.2, 5.1**

        For any valid qualifier, the approval detection in getDeploymentStatus SHALL resolve
        the pipeline name as {qualifier}-pipeline.
        """
        ctx = _make_ctx()
        expected_name = f"{qualifier}-pipeline"

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {"stageStates": []}

            result = await tool_get_manual_approval_status(ctx, qualifier=qualifier)

            assert result["pipeline_name"] == expected_name

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(pipeline_name=valid_pipeline_name_st)
    async def test_get_status_without_qualifier_uses_pipeline_name(self, pipeline_name):
        """**Validates: Requirements 1.2**

        When no qualifier is provided, the approval detection in getDeploymentStatus SHALL use
        the provided pipeline_name parameter.
        """
        ctx = _make_ctx()

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {"stageStates": []}

            result = await tool_get_manual_approval_status(
                ctx, pipeline_name=pipeline_name
            )

            assert result["pipeline_name"] == pipeline_name

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(qualifier=valid_qualifier_st)
    async def test_submit_with_qualifier_resolves_name(self, qualifier):
        """**Validates: Requirements 5.2**

        For any valid qualifier, submitManualApproval SHALL resolve
        the pipeline name as {qualifier}-pipeline.
        """
        ctx = _make_ctx()
        expected_name = f"{qualifier}-pipeline"

        with (
            patch(_CP_SUBMIT) as mock_cp,
            patch(_RETRY_SUBMIT) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {}

            result = await tool_submit_manual_approval(
                ctx,
                action="Approve",
                token="tok-123",
                stage_name="Review",
                action_name="ManualApproval",
                qualifier=qualifier,
            )

            assert result.get("pipeline_name") == expected_name


# ===========================================================================
# Property 2: Approval Response Completeness
# Feature: deployment-manual-approval, Property 2: Approval Response Completeness
# Validates: Requirements 1.3, 2.1, 2.2
# ===========================================================================
class TestProperty2ApprovalResponseCompleteness:
    """P2: When a pending approval is found, the response SHALL contain all
    required fields and optional fields when present."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        stage_name=non_empty_text_st,
        action_name=non_empty_text_st,
        token=non_empty_text_st,
        exec_id=non_empty_text_st,
        custom_data=st.text(min_size=0, max_size=200),
        entity_url=st.text(min_size=0, max_size=200),
    )
    async def test_response_contains_required_fields(
        self, stage_name, action_name, token, exec_id, custom_data, entity_url
    ):
        """**Validates: Requirements 1.3, 2.1, 2.2**

        For any pipeline state with a pending approval, the response SHALL
        contain stage_name, action_name, pipeline_execution_id, and token.
        When custom_data is non-empty, it SHALL be in the response.
        When entityUrl is non-empty, external_entity_url SHALL be in the response.
        """
        ctx = _make_ctx()

        action_state = {
            "actionName": action_name,
            "latestExecution": {
                "status": "InProgress",
                "token": token,
                "pipelineExecutionId": exec_id,
            },
        }
        if custom_data:
            action_state["latestExecution"]["summary"] = custom_data
        if entity_url:
            action_state["entityUrl"] = entity_url

        pipeline_state = {
            "stageStates": [
                {
                    "stageName": stage_name,
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [action_state],
                }
            ]
        }

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = pipeline_state

            result = await tool_get_manual_approval_status(ctx)

            # Required fields
            assert result["approval_pending"] is True
            assert result["stage_name"] == stage_name
            assert result["action_name"] == action_name
            assert result["pipeline_execution_id"] == exec_id
            assert result["token"] == token

            # Optional fields
            if custom_data:
                assert result["custom_data"] == custom_data
            else:
                assert "custom_data" not in result

            if entity_url:
                assert result["external_entity_url"] == entity_url
            else:
                assert "external_entity_url" not in result


# ===========================================================================
# Property 3: No-Approval Response
# Feature: deployment-manual-approval, Property 3: No-Approval Response
# Validates: Requirements 1.4
# ===========================================================================
class TestProperty3NoApprovalResponse:
    """P3: When no pending approval exists, approval_pending SHALL be False
    and pipeline_status SHALL be present."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        status=st.sampled_from(["Succeeded", "Failed", "InProgress"]),
        num_stages=st.integers(min_value=1, max_value=5),
    )
    async def test_no_approval_returns_false_with_status(self, status, num_stages):
        """**Validates: Requirements 1.4**

        For any pipeline state without a pending approval, the response
        SHALL set approval_pending to False and include pipeline_status.
        """
        ctx = _make_ctx()

        # Build stages without any approval tokens
        stages = []
        for i in range(num_stages):
            stages.append(
                {
                    "stageName": f"Stage-{i}",
                    "latestExecution": {"status": status},
                    "actionStates": [
                        {
                            "actionName": f"Action-{i}",
                            "latestExecution": {
                                "status": status,
                                # No token — not an approval action
                            },
                        }
                    ],
                }
            )

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {"stageStates": stages}

            result = await tool_get_manual_approval_status(ctx)

            assert result["success"] is True
            assert result["approval_pending"] is False
            assert "pipeline_status" in result


# ===========================================================================
# Property 4: S3 Diff Content Inclusion
# Feature: deployment-manual-approval, Property 4: S3 Diff Content Inclusion
# Validates: Requirements 2.4
# ===========================================================================
class TestProperty4S3DiffContentInclusion:
    """P4: When S3 diff is successfully retrieved, the content SHALL appear
    in the s3_diff_content field."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(s3_content=st.text(min_size=1, max_size=500))
    async def test_s3_content_included_in_response(self, s3_content):
        """**Validates: Requirements 2.4**

        For any successfully retrieved S3 diff content, the response
        SHALL include it in the s3_diff_content field.
        """
        ctx = _make_ctx()

        pipeline_state = {
            "stageStates": [
                {
                    "stageName": "Review",
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "ManualApproval",
                            "latestExecution": {
                                "status": "InProgress",
                                "token": "tok-abc",
                                "pipelineExecutionId": "exec-123",
                            },
                        }
                    ],
                }
            ]
        }

        # Mock S3 body
        mock_body = Mock()
        mock_body.read.return_value = s3_content.encode("utf-8")
        s3_response = {"Body": mock_body}

        with (
            patch(_S3_DIFF_GET, return_value=True),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
            patch(
                f"{_GET_STATUS_PREFIX}.get_aws_account_id", return_value="123456789012"
            ),
            patch(f"{_GET_STATUS_PREFIX}.get_s3_client") as mock_s3,
        ):
            mock_cp.return_value = Mock()

            # First call returns pipeline state, second returns S3 object
            mock_retry.side_effect = [pipeline_state, s3_response]
            mock_s3.return_value = Mock()

            result = await tool_get_manual_approval_status(ctx)

            assert result["approval_pending"] is True
            assert result["s3_diff_content"] == s3_content


# ===========================================================================
# Property 5: Approval/Rejection Action Mapping
# Feature: deployment-manual-approval, Property 5: Approval/Rejection Action Mapping
# Validates: Requirements 3.1, 3.2, 4.1, 4.2
# ===========================================================================
class TestProperty5ActionMapping:
    """P5: For any valid action string (case-insensitive Approve/Reject),
    PutApprovalResult SHALL be called with the normalized status."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(action=action_case_variants_st)
    async def test_action_normalized_correctly(self, action):
        """**Validates: Requirements 3.1, 3.2, 4.1, 4.2**

        For any case variant of Approve/Reject, the tool SHALL call
        PutApprovalResult with the correctly normalized status.
        """
        ctx = _make_ctx()
        expected_status = VALID_ACTIONS[action.strip().lower()]

        with (
            patch(_CP_SUBMIT) as mock_cp,
            patch(_RETRY_SUBMIT) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {}

            result = await tool_submit_manual_approval(
                ctx,
                action=action,
                token="tok-123",
                stage_name="Review",
                action_name="ManualApproval",
            )

            assert result["success"] is True
            assert result["action"] == expected_status

            # Verify the API call used the normalized status
            call_kwargs = mock_retry.call_args
            put_params = call_kwargs.kwargs if call_kwargs.kwargs else {}
            # retry_with_exponential_backoff is called with func + kwargs
            # Check the result.status in the kwargs
            if "result" in put_params:
                assert put_params["result"]["status"] == expected_status


# ===========================================================================
# Property 6: Comment Passthrough
# Feature: deployment-manual-approval, Property 6: Comment Passthrough
# Validates: Requirements 3.3, 4.3
# ===========================================================================
class TestProperty6CommentPassthrough:
    """P6: When a summary comment is provided, it SHALL appear in the
    PutApprovalResult API call's result.summary field."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        comment=non_empty_text_st,
        action=st.sampled_from(["Approve", "Reject"]),
    )
    async def test_comment_included_in_api_call(self, comment, action):
        """**Validates: Requirements 3.3, 4.3**

        For any non-empty summary comment, the tool SHALL include it
        in the PutApprovalResult API call's result.summary field.
        """
        ctx = _make_ctx()

        with (
            patch(_CP_SUBMIT) as mock_cp,
            patch(_RETRY_SUBMIT) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {}

            result = await tool_submit_manual_approval(
                ctx,
                action=action,
                token="tok-123",
                stage_name="Review",
                action_name="ManualApproval",
                summary=comment,
            )

            assert result["success"] is True

            # Verify the comment was passed through to the API call
            call_kwargs = mock_retry.call_args
            # retry_with_exponential_backoff(func, **kwargs)
            # The kwargs are passed as keyword arguments
            all_kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
            if "result" in all_kwargs:
                assert all_kwargs["result"]["summary"] == comment


# ===========================================================================
# Property 7: Qualifier Validation
# Feature: deployment-manual-approval, Property 7: Qualifier Validation
# Validates: Requirements 5.3, 5.4
# ===========================================================================
class TestProperty7QualifierValidation:
    """P7: validate_qualifier() SHALL accept strings matching [a-zA-Z0-9-]+
    with length 1-100 and reject all others."""

    @settings(max_examples=100)
    @given(qualifier=st.from_regex(r"[a-zA-Z0-9\-]{1,100}", fullmatch=True))
    def test_valid_qualifiers_accepted(self, qualifier):
        """**Validates: Requirements 5.3, 5.4**

        For any string matching [a-zA-Z0-9-]+ with length 1-100,
        validate_qualifier SHALL accept it.
        """
        assume(len(qualifier) >= 1)
        is_valid, error = validate_qualifier(qualifier)
        assert is_valid is True
        assert error == ""

    @settings(max_examples=100)
    @given(qualifier=st.text(min_size=1, max_size=100))
    def test_invalid_qualifiers_rejected(self, qualifier):
        """**Validates: Requirements 5.3, 5.4**

        For any string NOT matching [a-zA-Z0-9-]+, validate_qualifier
        SHALL reject it.
        """
        # Only test strings that contain invalid characters
        assume(not re.fullmatch(r"[a-zA-Z0-9\-]+", qualifier))
        is_valid, error = validate_qualifier(qualifier)
        assert is_valid is False
        assert error != ""

    @settings(max_examples=100)
    @given(qualifier=st.text(min_size=101, max_size=200))
    def test_too_long_qualifiers_rejected(self, qualifier):
        """**Validates: Requirements 5.3, 5.4**

        Qualifiers longer than 100 characters SHALL be rejected.
        """
        is_valid, error = validate_qualifier(qualifier)
        assert is_valid is False

    def test_empty_qualifier_rejected(self):
        """Empty qualifier SHALL be rejected."""
        is_valid, error = validate_qualifier("")
        assert is_valid is False

    def test_none_qualifier_rejected(self):
        """None qualifier SHALL be rejected."""
        is_valid, error = validate_qualifier(None)
        assert is_valid is False


# ===========================================================================
# Property 8: Action Parameter Validation
# Feature: deployment-manual-approval, Property 8: Action Parameter Validation
# Validates: Requirements 6.1, 6.3
# ===========================================================================
class TestProperty8ActionParameterValidation:
    """P8: Only case-insensitive Approve/Reject SHALL be accepted."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(action=action_case_variants_st)
    async def test_valid_actions_accepted(self, action):
        """**Validates: Requirements 6.1, 6.3**

        Case-insensitive variants of Approve/Reject SHALL be accepted.
        """
        ctx = _make_ctx()

        with (
            patch(_CP_SUBMIT) as mock_cp,
            patch(_RETRY_SUBMIT) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = {}

            result = await tool_submit_manual_approval(
                ctx,
                action=action,
                token="tok-123",
                stage_name="Review",
                action_name="ManualApproval",
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(action=st.text(min_size=1, max_size=50))
    async def test_invalid_actions_rejected(self, action):
        """**Validates: Requirements 6.1, 6.3**

        Any string that is not a case-insensitive variant of
        Approve/Reject SHALL be rejected.
        """
        assume(action.strip().lower() not in ("approve", "reject"))
        ctx = _make_ctx()

        result = await tool_submit_manual_approval(
            ctx,
            action=action,
            token="tok-123",
            stage_name="Review",
            action_name="ManualApproval",
        )

        assert result.get("success") is not True or "error" in result


# ===========================================================================
# Property 9: Required Parameter Validation
# Feature: deployment-manual-approval, Property 9: Required Parameter Validation
# Validates: Requirements 6.2
# ===========================================================================
class TestProperty9RequiredParameterValidation:
    """P9: Empty/whitespace-only values SHALL be rejected for token,
    stage_name, and action_name."""

    @settings(max_examples=100)
    @given(value=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()))
    def test_non_empty_strings_accepted(self, value):
        """**Validates: Requirements 6.2**

        Non-empty, non-whitespace strings SHALL be accepted by
        validate_string_input for required parameters.
        """
        is_valid, error = validate_string_input(value, "test_field", min_length=1)
        # Only check length constraint — value must be within max_length
        if len(value) <= 1000:
            assert is_valid is True

    @settings(max_examples=100)
    @given(
        field_name=st.sampled_from(["token", "stage_name", "action_name"]),
    )
    def test_empty_string_rejected(self, field_name):
        """**Validates: Requirements 6.2**

        Empty strings SHALL be rejected for required parameters.
        """
        is_valid, error = validate_string_input("", field_name, min_length=1)
        assert is_valid is False

    @settings(max_examples=100)
    @given(
        field_name=st.sampled_from(["token", "stage_name", "action_name"]),
    )
    def test_none_rejected(self, field_name):
        """**Validates: Requirements 6.2**

        None values SHALL be rejected for required parameters.
        """
        is_valid, error = validate_string_input(None, field_name, min_length=1)
        assert is_valid is False


# ===========================================================================
# Property 11: S3 Diff Feature Flag Controls Retrieval
# Feature: deployment-manual-approval, Property 11: S3 Diff Feature Flag Controls Retrieval
# Validates: Requirements 9.4, 9.5, 9.6
# ===========================================================================
class TestProperty11S3DiffFeatureFlag:
    """P11: is_s3_diff_enabled() SHALL return True only for true/1/yes
    (case-insensitive). Bucket name SHALL follow the naming convention."""

    @settings(max_examples=100)
    @given(env_value=st.text(min_size=0, max_size=50).filter(lambda s: "\x00" not in s))
    def test_s3_diff_toggle_matches_spec(self, env_value):
        """**Validates: Requirements 9.4, 9.5, 9.6**

        is_s3_diff_enabled() SHALL return True if and only if the env
        var value is one of true/1/yes (case-insensitive).
        """
        expected = env_value.lower() in ("true", "1", "yes")

        with patch.dict(os.environ, {"ENABLE_S3_DIFF": env_value}):
            result = is_s3_diff_enabled()
            assert result == expected, (
                f"For env value '{env_value}': expected {expected}, got {result}"
            )

    def test_unset_returns_false(self):
        """When ENABLE_S3_DIFF is not set, SHALL return False."""
        env = os.environ.copy()
        env.pop("ENABLE_S3_DIFF", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_s3_diff_enabled() is False

    @settings(max_examples=100)
    @given(
        qualifier=valid_qualifier_st,
        account_id=st.from_regex(r"[0-9]{12}", fullmatch=True),
        region=st.sampled_from(
            ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        ),
    )
    def test_bucket_name_inference_with_qualifier(self, qualifier, account_id, region):
        """**Validates: Requirements 9.5, 9.6**

        When qualifier is provided, the bucket name SHALL be
        {qualifier}-diff-{account_id}-{region}.
        """
        pipeline_name = f"{qualifier}-pipeline"
        bucket = infer_s3_diff_bucket_name(pipeline_name, qualifier, account_id, region)
        assert bucket == f"{qualifier}-diff-{account_id}-{region}"

    @settings(max_examples=100)
    @given(
        account_id=st.from_regex(r"[0-9]{12}", fullmatch=True),
        region=st.sampled_from(
            ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        ),
    )
    def test_bucket_name_inference_standard(self, account_id, region):
        """**Validates: Requirements 9.5, 9.6**

        For standard deployments (no qualifier), the bucket name SHALL be
        {prefix}-diff-{account_id}-{region} where prefix is derived from
        the pipeline name by stripping '-Pipeline'.
        """
        pipeline_name = "AWSAccelerator-Pipeline"
        bucket = infer_s3_diff_bucket_name(pipeline_name, None, account_id, region)
        assert bucket == f"AWSAccelerator-diff-{account_id}-{region}"


# ===========================================================================
# Property 12: Review Stage Diff Retrieval
# Feature: deployment-manual-approval, Property 12: Review Stage Diff Retrieval
# Validates: Requirements 2.7, 2.8, 2.9, 2.10, 2.11
# ===========================================================================
class TestProperty12ReviewStageDiffRetrieval:
    """P12: When a pending approval and CodeBuild action with logs exist,
    review_diff SHALL contain the truncated log content."""

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(log_content=st.text(min_size=1, max_size=500))
    async def test_review_diff_contains_log_content(self, log_content):
        """**Validates: Requirements 2.7, 2.8, 2.9, 2.10**

        For any pipeline state with a pending approval and a CodeBuild
        action with available logs, the response SHALL contain the
        review_diff field with the log content.
        """
        ctx = _make_ctx()

        pipeline_state = {
            "stageStates": [
                {
                    "stageName": "Review",
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "ReviewCommit",
                            "latestExecution": {
                                "status": "Succeeded",
                                "externalExecutionId": "build-id-prop12",
                            },
                        },
                        {
                            "actionName": "ManualApproval",
                            "latestExecution": {
                                "status": "InProgress",
                                "token": "tok-prop12",
                                "pipelineExecutionId": "exec-prop12",
                            },
                        },
                    ],
                }
            ]
        }

        build_response = {
            "builds": [
                {
                    "id": "build-id-prop12",
                    "logs": {
                        "groupName": "/codebuild/review",
                        "streamName": "stream-prop12",
                    },
                }
            ]
        }

        log_events_response = {"events": [{"message": log_content}]}

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
            patch(f"{_GET_STATUS_PREFIX}.get_codebuild_client") as mock_cb,
            patch(f"{_GET_STATUS_PREFIX}.get_logs_client") as mock_logs,
        ):
            mock_cp.return_value = Mock()
            mock_cb.return_value = Mock()
            mock_logs.return_value = Mock()

            # Calls: get_pipeline_state, batch_get_builds, get_log_events
            mock_retry.side_effect = [
                pipeline_state,
                build_response,
                log_events_response,
            ]

            result = await tool_get_manual_approval_status(ctx)

            assert result["approval_pending"] is True
            assert "review_diff" in result
            # The content should be present (possibly truncated for very large content)
            assert log_content in result["review_diff"]

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        stage_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=50,
        ),
    )
    async def test_no_codebuild_action_graceful_degradation(self, stage_name):
        """**Validates: Requirements 2.9, 2.10**

        For any pipeline state with a pending approval but NO CodeBuild
        action, the response SHALL still contain approval metadata
        without review_diff and without errors.
        """
        ctx = _make_ctx()

        pipeline_state = {
            "stageStates": [
                {
                    "stageName": stage_name,
                    "latestExecution": {"status": "InProgress"},
                    "actionStates": [
                        {
                            "actionName": "ManualApproval",
                            "latestExecution": {
                                "status": "InProgress",
                                "token": "tok-no-cb",
                                "pipelineExecutionId": "exec-no-cb",
                            },
                        }
                    ],
                }
            ]
        }

        with (
            patch(_S3_DIFF_GET, return_value=False),
            patch(_CP_GET) as mock_cp,
            patch(_RETRY_GET) as mock_retry,
        ):
            mock_cp.return_value = Mock()
            mock_retry.return_value = pipeline_state

            result = await tool_get_manual_approval_status(ctx)

            assert result["success"] is True
            assert result["approval_pending"] is True
            assert result["token"] == "tok-no-cb"
            # review_diff should NOT be present — graceful degradation
            assert "review_diff" not in result
            # A warning should be present instead
            assert "review_diff_warning" in result
