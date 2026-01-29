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

"""Unit tests for S3ConfigRetrieval successful configuration retrieval."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestGetConfigurationSuccess:
    """Test successful configuration retrieval scenarios."""

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.config.get_config_s3.set_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.is_zipfile")
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.ZipFile")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_with_custom_bucket(
        self,
        mock_cleanup,
        mock_mkstemp,
        mock_exists,
        mock_makedirs,
        mock_zipfile_class,
        mock_is_zipfile,
        mock_set_path,
    ):
        """Test successful configuration retrieval with custom bucket."""
        # Setup mocks
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        mock_exists.return_value = False
        mock_is_zipfile.return_value = True

        mock_zip = MagicMock()
        mock_zipfile_class.return_value.__enter__.return_value = mock_zip

        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None

        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval._validate_bucket_name = Mock(return_value={"valid": True})
        retrieval._extract_zip_metadata = Mock(
            return_value={
                "file_count": 5,
                "directory_count": 2,
                "root_files": ["file1.yaml"],
                "root_folders": ["folder1"],
                "structure": {"root": {"files": [], "directories": {}}},
                "zip_size": 1024,
            }
        )

        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()

        result = await retrieval.get_configuration(
            mock_ctx, bucket_name="custom-bucket"
        )

        assert result["success"] is True
        assert result["bucket_name"] == "custom-bucket"
        assert result["file_count"] == 5
        assert "container_path" in result
        assert "host_path" in result
        assert "llm_instructions" in result

    @pytest.mark.asyncio
    @patch(
        "awslabs.lza_mcp_server.tools.config.get_config_s3.set_extracted_lza_config_path"
    )
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.is_zipfile")
    @patch("awslabs.lza_mcp_server.tools.config.get_config_s3.zipfile.ZipFile")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("tempfile.mkstemp")
    @patch.object(S3ConfigRetrieval, "_cleanup_previous_temp_directory")
    async def test_get_configuration_with_default_bucket(
        self,
        mock_cleanup,
        mock_mkstemp,
        mock_exists,
        mock_makedirs,
        mock_zipfile_class,
        mock_is_zipfile,
        mock_set_path,
    ):
        """Test successful configuration retrieval with default bucket."""
        # Setup mocks
        mock_cleanup.return_value = None
        mock_mkstemp.return_value = (1, "/tmp/test.zip")
        mock_exists.return_value = False
        mock_is_zipfile.return_value = True

        mock_zip = MagicMock()
        mock_zipfile_class.return_value.__enter__.return_value = mock_zip

        mock_s3_client = Mock()
        mock_s3_client.download_file.return_value = None

        retrieval = S3ConfigRetrieval()
        retrieval.s3_manager._get_s3_client = Mock(return_value=mock_s3_client)
        retrieval.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        retrieval.s3_manager.determine_bucket_name = AsyncMock(
            return_value="aws-accelerator-config-123456789012-us-east-1"
        )
        retrieval._extract_zip_metadata = Mock(
            return_value={
                "file_count": 3,
                "directory_count": 1,
                "root_files": [],
                "root_folders": [],
                "structure": {"root": {"files": [], "directories": {}}},
                "zip_size": 512,
            }
        )

        mock_ctx = Mock()
        mock_ctx.info = AsyncMock()

        result = await retrieval.get_configuration(mock_ctx)

        assert result["success"] is True
        assert "aws-accelerator-config" in result["bucket_name"]
        assert result["file_count"] == 3
        mock_ctx.info.assert_called()
