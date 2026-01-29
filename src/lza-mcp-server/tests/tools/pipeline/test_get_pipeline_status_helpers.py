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

"""Unit tests for get_pipeline_status helper functions."""

from awslabs.lza_mcp_server.tools.pipeline.get_pipeline_status import (
    get_stage_description,
    get_action_description,
    get_cached_pipeline_metadata,
    cache_pipeline_metadata,
)


class TestStageDescriptions:
    """Test stage and action description functions."""

    def test_get_stage_description_known_stages(self):
        """Test getting descriptions for known LZA pipeline stages."""
        known_stages = {
            "Source": "Retrieves LZA source code",
            "Prepare": "Creates and validates AWS accounts",
            "Accounts": "Validates all accounts",
            "Bootstrap": "Runs AWS CDK bootstrap",
            "Logging": "Deploys centralized KMS keys",
            "Organization": "Deploys AWS Organization-wide resources",
            "SecurityAudit": "Deploys security service dependencies",
            "Deploy": "Deploys infrastructure",
        }

        for stage_name, expected_substring in known_stages.items():
            description = get_stage_description(stage_name)
            assert expected_substring in description
            assert len(description) > 0

    def test_get_stage_description_unknown_stage(self):
        """Test getting description for unknown stage."""
        description = get_stage_description("UnknownStage")
        assert description == "Stage: UnknownStage"

    def test_get_action_description_known_actions(self):
        """Test getting descriptions for known LZA pipeline actions."""
        known_actions = {
            "Network_Prepare": "Creates Transit Gateway",
            "Network_VPCs": "Deploys VPCs",
        }

        for action_name, expected_substring in known_actions.items():
            description = get_action_description(action_name)
            assert expected_substring in description
            assert len(description) > 0

    def test_get_action_description_unknown_action(self):
        """Test getting description for unknown action."""
        description = get_action_description("UnknownAction")
        assert description == "Action: UnknownAction"


class TestCacheFunctions:
    """Test pipeline metadata caching functions."""

    def test_cache_and_retrieve_pipeline_metadata(self):
        """Test caching and retrieving pipeline metadata."""
        pipeline_name = "test-pipeline"
        metadata = {
            "stages": [{"name": "Source"}, {"name": "Build"}],
            "total_stages": 2,
        }

        cache_pipeline_metadata(pipeline_name, metadata)
        cached = get_cached_pipeline_metadata(pipeline_name)

        assert cached is not None
        assert cached == metadata
        assert cached["total_stages"] == 2
        assert len(cached["stages"]) == 2

    def test_get_cached_pipeline_metadata_not_found(self):
        """Test retrieving non-existent cached metadata."""
        result = get_cached_pipeline_metadata("non-existent-pipeline-xyz")
        assert result is None
