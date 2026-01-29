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

"""Unit tests for S3Manager initialization and session management."""

from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.orchestration.core.s3_manager import S3Manager


class TestS3ManagerInitialization:
    """Test S3Manager initialization and session management."""

    def test_init_creates_instance(self):
        """Test S3Manager initialization."""
        manager = S3Manager()

        assert manager is not None
        assert manager._session is None
        assert manager._s3_client is None
        assert manager.logger is not None

    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    def test_get_session_creates_new_session(self, mock_get_session):
        """Test _get_session creates a new session when none exists."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        session = manager._get_session()

        assert session == mock_session
        assert manager._session == mock_session
        mock_get_session.assert_called_once()

    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    def test_get_session_reuses_existing_session(self, mock_get_session):
        """Test _get_session reuses existing session."""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        session1 = manager._get_session()
        session2 = manager._get_session()

        assert session1 == session2
        assert session1 == mock_session
        mock_get_session.assert_called_once()  # Only called once

    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    def test_get_s3_client_creates_new_client(self, mock_get_session):
        """Test _get_s3_client creates a new S3 client."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        client = manager._get_s3_client()

        assert client == mock_s3_client
        assert manager._s3_client == mock_s3_client
        mock_session.client.assert_called_once_with("s3")

    @patch("awslabs.lza_mcp_server.orchestration.core.s3_manager.get_aws_session")
    def test_get_s3_client_reuses_existing_client(self, mock_get_session):
        """Test _get_s3_client reuses existing client."""
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        mock_get_session.return_value = mock_session

        manager = S3Manager()
        client1 = manager._get_s3_client()
        client2 = manager._get_s3_client()

        assert client1 == client2
        assert client1 == mock_s3_client
        mock_session.client.assert_called_once()  # Only called once
