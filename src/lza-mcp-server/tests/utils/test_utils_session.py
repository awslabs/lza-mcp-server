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

"""Unit tests for utils AWS session creation."""

from unittest.mock import patch, Mock

from awslabs.lza_mcp_server.utils.utils import get_aws_session


class TestUtilsSession:
    """Test AWS session creation."""

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_with_region(self, mock_session_class, mock_get_region):
        """Test session creation with resolved region."""
        mock_get_region.return_value = "us-west-2"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session == mock_session
        mock_get_region.assert_called_once()
        mock_session_class.assert_called_once_with(region_name="us-west-2")

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_with_default_region(
        self, mock_session_class, mock_get_region
    ):
        """Test session creation with default region."""
        mock_get_region.return_value = "us-east-1"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session == mock_session
        mock_session_class.assert_called_once_with(region_name="us-east-1")

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_with_gov_cloud_region(
        self, mock_session_class, mock_get_region
    ):
        """Test session creation with GovCloud region."""
        mock_get_region.return_value = "us-gov-west-1"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session == mock_session
        mock_session_class.assert_called_once_with(region_name="us-gov-west-1")

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_with_china_region(
        self, mock_session_class, mock_get_region
    ):
        """Test session creation with China region."""
        mock_get_region.return_value = "cn-north-1"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session == mock_session
        mock_session_class.assert_called_once_with(region_name="cn-north-1")

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_calls_get_region_once(
        self, mock_session_class, mock_get_region
    ):
        """Test that get_aws_region is called exactly once."""
        mock_get_region.return_value = "eu-west-1"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        get_aws_session()

        mock_get_region.assert_called_once()

    @patch("awslabs.lza_mcp_server.utils.utils.get_aws_region")
    @patch("boto3.Session")
    def test_get_aws_session_returns_boto3_session(
        self, mock_session_class, mock_get_region
    ):
        """Test that function returns a boto3 Session object."""
        mock_get_region.return_value = "ap-southeast-2"
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = get_aws_session()

        assert session is not None
        assert session == mock_session
