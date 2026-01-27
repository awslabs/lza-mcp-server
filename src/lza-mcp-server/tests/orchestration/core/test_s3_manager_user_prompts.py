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

"""Unit tests for S3Manager user prompt generation."""

import pytest

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager


class TestPromptForCustomBucketName:
    """Test user prompt generation for custom bucket names."""

    @pytest.mark.asyncio
    async def test_prompt_structure(self):
        """Test prompt has correct structure and required fields."""
        manager = S3Manager()
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name="aws-accelerator-config-123456789012-us-east-1",
            account_id="123456789012",
            region="us-east-1",
        )

        assert result["action_required"] == "user_input"
        assert result["input_type"] == "bucket_name"
        assert "prompt" in result
        assert "context" in result
        assert "guidance" in result
        assert "validation_requirements" in result
        assert "suggested_actions" in result

    @pytest.mark.asyncio
    async def test_prompt_contains_bucket_name(self):
        """Test prompt contains the default bucket name."""
        manager = S3Manager()
        bucket_name = "aws-accelerator-config-999888777666-eu-west-1"
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name=bucket_name,
            account_id="999888777666",
            region="eu-west-1",
        )

        assert bucket_name in result["prompt"]
        assert result["context"]["default_bucket"] == bucket_name

    @pytest.mark.asyncio
    async def test_prompt_contains_context(self):
        """Test prompt contains correct context information."""
        manager = S3Manager()
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name="test-bucket",
            account_id="111222333444",
            region="ap-southeast-2",
        )

        assert result["context"]["account_id"] == "111222333444"
        assert result["context"]["region"] == "ap-southeast-2"
        assert "bucket_pattern" in result["context"]

    @pytest.mark.asyncio
    async def test_prompt_contains_guidance(self):
        """Test prompt contains helpful guidance."""
        manager = S3Manager()
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name="test-bucket",
            account_id="123456789012",
            region="us-west-2",
        )

        assert len(result["guidance"]) > 0
        assert any("not found" in g.lower() for g in result["guidance"])

    @pytest.mark.asyncio
    async def test_prompt_contains_validation_requirements(self):
        """Test prompt contains validation requirements."""
        manager = S3Manager()
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name="test-bucket",
            account_id="123456789012",
            region="us-west-2",
        )

        assert len(result["validation_requirements"]) > 0
        assert any("unique" in r.lower() for r in result["validation_requirements"])
        assert any("permission" in r.lower() for r in result["validation_requirements"])

    @pytest.mark.asyncio
    async def test_prompt_contains_suggested_actions(self):
        """Test prompt contains suggested actions."""
        manager = S3Manager()
        bucket_name = "aws-accelerator-config-123456789012-us-east-1"
        result = await manager.prompt_for_custom_bucket_name(
            default_bucket_name=bucket_name,
            account_id="123456789012",
            region="us-east-1",
        )

        assert len(result["suggested_actions"]) > 0
        # Should contain AWS CLI command to create bucket
        assert any("aws s3 mb" in action for action in result["suggested_actions"])
        assert any(bucket_name in action for action in result["suggested_actions"])
