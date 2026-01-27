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

"""Unit tests for S3UploadUtils initialization."""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils


class TestS3UploadUtilsInit:
    """Test S3UploadUtils initialization and instance setup."""

    def test_init_creates_instance(self):
        """Test successful initialization of S3UploadUtils."""
        # Act
        utils = S3UploadUtils()

        # Assert
        assert utils is not None
        assert hasattr(utils, "logger")
        assert hasattr(utils, "s3_manager")
        assert hasattr(utils, "config_manager")

    def test_init_sets_aws_connectivity_state(self):
        """Test initialization sets AWS connectivity state to False."""
        # Act
        utils = S3UploadUtils()

        # Assert
        assert utils._aws_connectivity_verified is False
        assert utils._aws_context is None

    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.S3Manager")
    def test_init_creates_s3_manager(self, mock_s3_manager_class):
        """Test initialization creates S3Manager instance."""
        # Arrange
        mock_s3_manager = Mock()
        mock_s3_manager_class.return_value = mock_s3_manager

        # Act
        utils = S3UploadUtils()

        # Assert
        mock_s3_manager_class.assert_called_once()
        assert utils.s3_manager == mock_s3_manager

    @patch("awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.ConfigurationManager")
    def test_init_creates_config_manager(self, mock_config_manager_class):
        """Test initialization creates ConfigurationManager instance."""
        # Arrange
        mock_config_manager = Mock()
        mock_config_manager_class.return_value = mock_config_manager

        # Act
        utils = S3UploadUtils()

        # Assert
        mock_config_manager_class.assert_called_once()
        assert utils.config_manager == mock_config_manager

    def test_init_logger_is_configured(self):
        """Test initialization configures logger."""
        # Act
        utils = S3UploadUtils()

        # Assert
        assert utils.logger is not None
        assert utils.logger.name == "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils"
