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

"""Tests for config_s3_resolver — bucket/key resolution logic."""

import pytest
from unittest.mock import patch, MagicMock

from awslabs.lza_mcp_server.tools.config.config_s3_resolver import (
    resolve_config_location,
    get_caller_identity,
)


ACCOUNT = "123456789012"
REGION = "us-east-1"


class TestResolveConfigLocation:
    """Test resolve_config_location for all deployment scenarios."""

    @pytest.mark.unit
    def test_standard_deployment_no_qualifier(self):
        """Standard deployment uses aws-accelerator-config bucket and zipped/ key."""
        loc = resolve_config_location(account_id=ACCOUNT, region=REGION)
        assert loc.bucket_name == f"aws-accelerator-config-{ACCOUNT}-{REGION}"
        assert loc.object_key == "zipped/aws-accelerator-config.zip"
        assert loc.qualifier is None

    @pytest.mark.unit
    def test_external_pipeline_with_qualifier(self):
        """External pipeline uses {qualifier}-config bucket and lza/ key."""
        loc = resolve_config_location(
            account_id=ACCOUNT, region=REGION, qualifier="container-dev-1"
        )
        assert loc.bucket_name == f"container-dev-1-config-{ACCOUNT}-{REGION}"
        assert loc.object_key == "lza/aws-accelerator-config.zip"
        assert loc.qualifier == "container-dev-1"

    @pytest.mark.unit
    def test_bucket_override_without_qualifier(self):
        """Explicit bucket override uses standard key when no qualifier."""
        loc = resolve_config_location(
            account_id=ACCOUNT,
            region=REGION,
            bucket_name_override="my-custom-bucket",
        )
        assert loc.bucket_name == "my-custom-bucket"
        assert loc.object_key == "zipped/aws-accelerator-config.zip"
        assert loc.qualifier is None

    @pytest.mark.unit
    def test_bucket_override_with_qualifier(self):
        """Explicit bucket override uses qualifier key when qualifier provided."""
        loc = resolve_config_location(
            account_id=ACCOUNT,
            region=REGION,
            qualifier="env2",
            bucket_name_override="my-custom-bucket",
        )
        assert loc.bucket_name == "my-custom-bucket"
        assert loc.object_key == "lza/aws-accelerator-config.zip"
        assert loc.qualifier == "env2"

    @pytest.mark.unit
    def test_different_regions(self):
        """Bucket name includes the correct region."""
        loc = resolve_config_location(account_id=ACCOUNT, region="eu-north-1")
        assert "eu-north-1" in loc.bucket_name

    @pytest.mark.unit
    def test_location_is_frozen_dataclass(self):
        """ConfigS3Location should be immutable."""
        loc = resolve_config_location(account_id=ACCOUNT, region=REGION)
        with pytest.raises(AttributeError):
            loc.bucket_name = "changed"


class TestGetCallerIdentity:
    """Test get_caller_identity helper."""

    @pytest.mark.unit
    @patch("awslabs.lza_mcp_server.tools.config.config_s3_resolver.get_aws_session")
    def test_returns_account_and_region(self, mock_session_fn):
        """Should return account_id, user_arn, and region."""
        mock_session = MagicMock()
        mock_session.region_name = "us-west-2"
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "111122223333",
            "Arn": "arn:aws:iam::111122223333:user/test",
        }
        mock_session.client.return_value = mock_sts
        mock_session_fn.return_value = mock_session

        result = get_caller_identity()
        assert result["account_id"] == "111122223333"
        assert result["region"] == "us-west-2"
        assert "user_arn" in result
