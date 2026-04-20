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

"""Additional tests for pipeline/common.py to cover branch gaps."""

from awslabs.lza_mcp_server.tools.pipeline.common import (
    determine_ecs_deployment_status,
    extract_create_failed_error,
    truncate_logs,
)


class TestDetermineEcsDeploymentStatusBranches:
    """Test branch coverage for determine_ecs_deployment_status."""

    def test_complete_in_tail(self):
        """Test DEPLOYMENT COMPLETE found in tail."""
        lines = ["starting...", "running...", "DEPLOYMENT COMPLETE"]
        assert determine_ecs_deployment_status(lines) == "COMPLETE"

    def test_failed_in_tail(self):
        """Test DEPLOYMENT FAILED found in tail."""
        lines = ["starting...", "running...", "DEPLOYMENT FAILED"]
        assert determine_ecs_deployment_status(lines) == "FAILED"

    def test_exit_code_failure_in_tail(self):
        """Test exit code failure marker in tail."""
        lines = ["starting...", "Error: Process completed with exit code 1"]
        assert determine_ecs_deployment_status(lines) == "FAILED"

    def test_yarn_failure_in_tail(self):
        """Test yarn/npm failure marker in tail."""
        lines = ["starting...", "error Command failed with exit code 1"]
        assert determine_ecs_deployment_status(lines) == "FAILED"

    def test_failure_in_full_log_not_tail(self):
        """Test failure marker found in full log but not in tail (>50 lines)."""
        lines = ["DEPLOYMENT FAILED"] + ["normal line"] * 60
        assert determine_ecs_deployment_status(lines) == "FAILED"

    def test_in_progress_no_markers(self):
        """Test IN_PROGRESS when no terminal markers found."""
        lines = ["starting...", "running...", "still going..."]
        assert determine_ecs_deployment_status(lines) == "IN_PROGRESS"

    def test_empty_lines(self):
        """Test empty log lines returns IN_PROGRESS."""
        assert determine_ecs_deployment_status([]) == "IN_PROGRESS"

    def test_complete_takes_priority_over_failed_in_tail(self):
        """Test COMPLETE found after FAILED in tail (last wins in reverse scan)."""
        lines = ["DEPLOYMENT FAILED", "recovery...", "DEPLOYMENT COMPLETE"]
        assert determine_ecs_deployment_status(lines) == "COMPLETE"


class TestExtractCreateFailedError:
    """Test extract_create_failed_error."""

    def test_returns_none_for_empty(self):
        """Test returns None for empty content."""
        assert extract_create_failed_error("") is None
        assert extract_create_failed_error(None) is None

    def test_returns_none_when_no_match(self):
        """Test returns None when no CREATE_FAILED found."""
        assert extract_create_failed_error("all good\nno errors") is None

    def test_extracts_first_create_failed(self):
        """Test extracts the first CREATE_FAILED line."""
        content = "line1\n  CREATE_FAILED: some resource\nCREATE_FAILED: another"
        result = extract_create_failed_error(content)
        assert result == "CREATE_FAILED: some resource"


class TestTruncateLogs:
    """Test truncate_logs."""

    def test_no_truncation_needed(self):
        """Test content under max_size is returned as-is."""
        content = "short log"
        assert truncate_logs(content) == content

    def test_truncation_applied(self):
        """Test content over max_size is truncated."""
        content = "x" * 100000
        result = truncate_logs(content, max_size=1000)
        assert len(result) < len(content)
        assert "TRUNCATED" in result

    def test_truncation_preserves_start_and_end(self):
        """Test truncation keeps first and last parts."""
        content = "START" + "x" * 100000 + "END"
        result = truncate_logs(content, max_size=1000)
        assert result.startswith("START")
        assert result.endswith("END")
