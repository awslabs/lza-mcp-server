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

"""Unit tests for S3ConfigRetrieval initialization and cleanup."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestS3ConfigRetrievalInitialization:
    """Test S3ConfigRetrieval initialization."""

    def test_init_creates_instance(self):
        """Test S3ConfigRetrieval initialization."""
        retrieval = S3ConfigRetrieval()

        assert retrieval is not None
        assert retrieval.logger is not None
        assert retrieval.s3_manager is not None
        assert retrieval._temp_directories == {}
        assert retrieval._last_temp_directory is None

    @pytest.mark.asyncio
    async def test_cleanup_previous_temp_directory_no_previous(self):
        """Test cleanup when no previous temp directory exists."""
        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        mock_ctx.warning = AsyncMock()

        # Should not raise any errors
        await retrieval._cleanup_previous_temp_directory(mock_ctx)

        # Should not call any context methods
        mock_ctx.info.assert_not_called()
        mock_ctx.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_previous_temp_directory_exists(self):
        """Test cleanup of existing previous temp directory."""
        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()

        # Create a real temp directory
        temp_dir = tempfile.mkdtemp(prefix="test-cleanup-")
        retrieval._last_temp_directory = temp_dir
        retrieval._temp_directories[temp_dir] = {"test": "data"}

        # Cleanup should remove it
        await retrieval._cleanup_previous_temp_directory(mock_ctx)

        assert not os.path.exists(temp_dir)
        assert temp_dir not in retrieval._temp_directories
        mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_previous_temp_directory_already_removed(self):
        """Test cleanup when previous temp directory was already removed."""
        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()

        # Set a path that doesn't exist
        retrieval._last_temp_directory = "/nonexistent/path"

        # Should not raise errors
        await retrieval._cleanup_previous_temp_directory(mock_ctx)

        mock_ctx.info.assert_not_called()

    @pytest.mark.asyncio
    @patch("shutil.rmtree")
    async def test_cleanup_previous_temp_directory_removal_fails(self, mock_rmtree):
        """Test cleanup handles removal failures gracefully."""
        mock_rmtree.side_effect = OSError("Permission denied")

        retrieval = S3ConfigRetrieval()
        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()
        mock_ctx.warning = AsyncMock()

        # Create a real temp directory
        temp_dir = tempfile.mkdtemp(prefix="test-cleanup-fail-")
        retrieval._last_temp_directory = temp_dir

        # Cleanup should handle the error
        await retrieval._cleanup_previous_temp_directory(mock_ctx)

        mock_ctx.warning.assert_called()
        # Directory should still exist since removal failed
        assert os.path.exists(temp_dir)

        # Clean up manually
        os.rmdir(temp_dir)
