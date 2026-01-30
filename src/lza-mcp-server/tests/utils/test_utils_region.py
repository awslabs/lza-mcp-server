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

"""Unit tests for utils region resolution."""

from unittest.mock import patch, Mock

from awslabs.lza_mcp_server.utils.utils import get_aws_region, DEFAULT_REGION


class TestUtilsRegion:
    """Test AWS region resolution."""

    @patch.dict("os.environ", {"AWS_REGION": "us-west-2"}, clear=True)
    def test_get_aws_region_from_aws_region_env(self):
        """Test region resolution from AWS_REGION environment variable."""
        region = get_aws_region()
        assert region == "us-west-2"

    @patch.dict("os.environ", {"AWS_DEFAULT_REGION": "eu-west-1"}, clear=True)
    def test_get_aws_region_from_aws_default_region_env(self):
        """Test region resolution from AWS_DEFAULT_REGION environment variable."""
        region = get_aws_region()
        assert region == "eu-west-1"

    @patch.dict(
        "os.environ",
        {"AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "eu-west-1"},
        clear=True,
    )
    def test_get_aws_region_prefers_aws_region(self):
        """Test that AWS_REGION takes precedence over AWS_DEFAULT_REGION."""
        region = get_aws_region()
        assert region == "us-west-2"

    @patch.dict("os.environ", {}, clear=True)
    @patch("boto3.Session")
    def test_get_aws_region_from_boto3_session(self, mock_session_class):
        """Test region resolution from boto3 session."""
        mock_session = Mock()
        mock_session.region_name = "ap-southeast-1"
        mock_session_class.return_value = mock_session

        region = get_aws_region()
        assert region == "ap-southeast-1"
        mock_session_class.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    @patch("boto3.Session")
    def test_get_aws_region_boto3_session_no_region(self, mock_session_class):
        """Test fallback to default when boto3 session has no region."""
        mock_session = Mock()
        mock_session.region_name = None
        mock_session_class.return_value = mock_session

        region = get_aws_region()
        assert region == DEFAULT_REGION

    @patch.dict("os.environ", {}, clear=True)
    @patch("boto3.Session")
    def test_get_aws_region_boto3_session_exception(self, mock_session_class):
        """Test fallback to default when boto3 session raises exception."""
        mock_session_class.side_effect = Exception("Session creation failed")

        region = get_aws_region()
        assert region == DEFAULT_REGION

    @patch.dict("os.environ", {}, clear=True)
    @patch("boto3.Session")
    def test_get_aws_region_fallback_to_default(self, mock_session_class):
        """Test fallback to default region when no configuration found."""
        mock_session = Mock()
        mock_session.region_name = None
        mock_session_class.return_value = mock_session

        region = get_aws_region()
        assert region == DEFAULT_REGION
        assert region == "us-east-1"

    @patch.dict("os.environ", {"AWS_REGION": ""}, clear=True)
    @patch("boto3.Session")
    def test_get_aws_region_empty_env_var(self, mock_session_class):
        """Test that empty AWS_REGION env var is ignored."""
        mock_session = Mock()
        mock_session.region_name = "ap-northeast-1"
        mock_session_class.return_value = mock_session

        region = get_aws_region()
        # Empty string is falsy, so should fall through to boto3 session
        assert region == "ap-northeast-1"

    @patch.dict("os.environ", {"AWS_REGION": "   "}, clear=True)
    def test_get_aws_region_whitespace_env_var(self):
        """Test that whitespace-only AWS_REGION is treated as valid."""
        region = get_aws_region()
        # Whitespace string is truthy, so it will be returned
        assert region == "   "

    @patch.dict("os.environ", {"AWS_REGION": "us-gov-west-1"}, clear=True)
    def test_get_aws_region_gov_cloud(self):
        """Test region resolution with GovCloud region."""
        region = get_aws_region()
        assert region == "us-gov-west-1"

    @patch.dict("os.environ", {"AWS_REGION": "cn-north-1"}, clear=True)
    def test_get_aws_region_china_region(self):
        """Test region resolution with China region."""
        region = get_aws_region()
        assert region == "cn-north-1"
