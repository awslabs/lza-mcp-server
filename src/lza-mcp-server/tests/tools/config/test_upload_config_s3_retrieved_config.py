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

"""Unit tests for upload_config_s3 retrieved config handling."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, AsyncMock

from awslabs.lza_mcp_server.tools.config.upload_config_s3 import (
    tool_upload_configuration_to_s3,
    _detect_retrieved_config_context,
    _handle_retrieved_config_upload,
)


class TestDetectRetrievedConfig:
    """Test detection of retrieved configuration context."""

    @pytest.mark.asyncio
    async def test_detect_no_extracted_path(self, mock_mcp_context):
        """Test detection when no extracted path is set."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
        ) as mock_get_path:
            mock_get_path.return_value = None

            result = await _detect_retrieved_config_context(mock_mcp_context)

        assert result["detected"] is False

    @pytest.mark.asyncio
    async def test_detect_path_not_exists(self, mock_mcp_context):
        """Test detection when extracted path doesn't exist."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
        ) as mock_get_path:
            mock_get_path.return_value = "/nonexistent/path"

            result = await _detect_retrieved_config_context(mock_mcp_context)

        assert result["detected"] is False

    @pytest.mark.asyncio
    async def test_detect_path_is_file(self, mock_mcp_context):
        """Test detection when extracted path is a file, not directory."""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()

        try:
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_file.name

                result = await _detect_retrieved_config_context(mock_mcp_context)

            assert result["detected"] is False
        finally:
            os.unlink(temp_file.name)

    @pytest.mark.asyncio
    async def test_detect_missing_required_files(self, mock_mcp_context):
        """Test detection when directory exists but missing required config files."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create only one file, missing required files
            with open(os.path.join(temp_dir, "network-config.yaml"), "w") as f:
                f.write("test: config\n")

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

                result = await _detect_retrieved_config_context(mock_mcp_context)

            assert result["detected"] is False
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_detect_success(self, mock_mcp_context):
        """Test successful detection of retrieved config."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create required files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\ntest: config\n")

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

                result = await _detect_retrieved_config_context(mock_mcp_context)

            assert result["detected"] is True
            assert result["config_path"] == str(temp_dir)
            assert "age_seconds" in result
            assert result["source"] == "getConfigurationFromS3"
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_detect_exception_handling(self, mock_mcp_context):
        """Test exception handling in detection."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
        ) as mock_get_path:
            mock_get_path.side_effect = Exception("Test error")

            result = await _detect_retrieved_config_context(mock_mcp_context)

        assert result["detected"] is False
        assert "error" in result
        assert result["error"] == "Test error"


class TestHandleRetrievedConfigUpload:
    """Test handling of retrieved config upload."""

    @pytest.mark.asyncio
    async def test_zip_creation_error(self, mock_mcp_context):
        """Test handling of ZIP creation errors."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create config files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\n")

            retrieved_context = {
                "detected": True,
                "config_path": temp_dir,
                "age_seconds": 100,
                "source": "getConfigurationFromS3",
            }

            # Mock zipfile to raise error
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.zipfile.ZipFile"
            ) as mock_zipfile:
                mock_zipfile.side_effect = Exception("ZIP creation failed")

                result = await _handle_retrieved_config_upload(
                    mock_mcp_context,
                    retrieved_context,
                    bucket_name=None,
                    offer_pipeline_release=False,
                )

            assert result["success"] is False
            assert "error" in result
            assert "ZIP creation failed" in result["error"]
            assert result["error_code"] == "RETRIEVED_CONFIG_UPLOAD_ERROR"
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_aws_connectivity_error(self, mock_mcp_context):
        """Test handling of AWS connectivity errors."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create config files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\n")

            retrieved_context = {
                "detected": True,
                "config_path": temp_dir,
                "age_seconds": 100,
                "source": "getConfigurationFromS3",
            }

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_upload_utils:
                mock_instance = Mock()
                mock_upload_utils.return_value = mock_instance
                mock_instance.ensure_aws_connectivity = AsyncMock(
                    side_effect=Exception("AWS connectivity failed")
                )

                result = await _handle_retrieved_config_upload(
                    mock_mcp_context,
                    retrieved_context,
                    bucket_name=None,
                    offer_pipeline_release=False,
                )

            assert result["success"] is False
            assert "error" in result
            assert "AWS connectivity failed" in result["error"]
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_s3_upload_failure(self, mock_mcp_context):
        """Test handling of S3 upload failures."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create config files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\n")

            retrieved_context = {
                "detected": True,
                "config_path": temp_dir,
                "age_seconds": 100,
                "source": "getConfigurationFromS3",
            }

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_upload_utils:
                mock_instance = Mock()
                mock_upload_utils.return_value = mock_instance
                mock_instance.ensure_aws_connectivity = AsyncMock(
                    return_value={
                        "account_id": "123456789012",
                        "region": "us-east-1",
                    }
                )

                with patch(
                    "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3Manager"
                ) as mock_s3_manager:
                    mock_s3_instance = Mock()
                    mock_s3_manager.return_value = mock_s3_instance
                    mock_s3_instance.upload_zip_file = AsyncMock(
                        return_value={
                            "success": False,
                            "error": "Upload failed",
                        }
                    )

                    result = await _handle_retrieved_config_upload(
                        mock_mcp_context,
                        retrieved_context,
                        bucket_name="test-bucket",
                        offer_pipeline_release=False,
                    )

            # Should return the upload failure result
            assert result["success"] is False
            assert result["error"] == "Upload failed"
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_cleanup_temp_file_error(self, mock_mcp_context):
        """Test handling of temporary file cleanup errors."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create config files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\n")

            retrieved_context = {
                "detected": True,
                "config_path": temp_dir,
                "age_seconds": 100,
                "source": "getConfigurationFromS3",
            }

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_upload_utils:
                mock_instance = Mock()
                mock_upload_utils.return_value = mock_instance
                mock_instance.ensure_aws_connectivity = AsyncMock(
                    return_value={
                        "account_id": "123456789012",
                        "region": "us-east-1",
                    }
                )

                with patch(
                    "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3Manager"
                ) as mock_s3_manager:
                    mock_s3_instance = Mock()
                    mock_s3_manager.return_value = mock_s3_instance
                    mock_s3_instance.upload_zip_file = AsyncMock(
                        return_value={"success": True}
                    )

                    # Mock os.remove to raise error
                    with patch(
                        "awslabs.lza_mcp_server.tools.config.upload_config_s3.os.remove"
                    ) as mock_remove:
                        mock_remove.side_effect = Exception("Cleanup failed")

                        result = await _handle_retrieved_config_upload(
                            mock_mcp_context,
                            retrieved_context,
                            bucket_name="test-bucket",
                            offer_pipeline_release=False,
                        )

            # Should succeed despite cleanup error
            assert result["success"] is True
            assert result["source"] == "retrieved_config"
        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_successful_upload_with_pipeline_release(self, mock_mcp_context):
        """Test successful upload with pipeline release offer."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create config files
            for filename in ["accounts-config.yaml", "global-config.yaml"]:
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(f"# {filename}\n")

            retrieved_context = {
                "detected": True,
                "config_path": temp_dir,
                "age_seconds": 100,
                "source": "getConfigurationFromS3",
            }

            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_upload_utils:
                mock_instance = Mock()
                mock_upload_utils.return_value = mock_instance
                mock_instance.ensure_aws_connectivity = AsyncMock(
                    return_value={
                        "account_id": "123456789012",
                        "region": "us-west-2",
                    }
                )

                with patch(
                    "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3Manager"
                ) as mock_s3_manager:
                    mock_s3_instance = Mock()
                    mock_s3_manager.return_value = mock_s3_instance
                    mock_s3_instance.upload_zip_file = AsyncMock(
                        return_value={"success": True}
                    )

                    result = await _handle_retrieved_config_upload(
                        mock_mcp_context,
                        retrieved_context,
                        bucket_name=None,
                        offer_pipeline_release=True,
                    )

            assert result["success"] is True
            assert result["source"] == "retrieved_config"
            assert result["config_path"] == temp_dir
            assert "zip_size" in result
            assert (
                result["bucket_name"] == "aws-accelerator-config-123456789012-us-west-2"
            )
            assert result["object_key"] == "zipped/aws-accelerator-config.zip"
        finally:
            shutil.rmtree(temp_dir)


class TestUploadConfigIntegration:
    """Test integration scenarios for upload configuration."""

    @pytest.mark.asyncio
    async def test_general_exception_handling(self, mock_mcp_context):
        """Test handling of unexpected exceptions."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.validate_file_path"
        ) as mock_validate:
            mock_validate.side_effect = Exception("Unexpected error")

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path="./config",
                bucket_name=None,
                offer_pipeline_release=False,
            )

        assert result["success"] is False
        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert result["error_code"] == "UPLOAD_ERROR"

    @pytest.mark.asyncio
    async def test_s3_upload_utils_exception(self, mock_mcp_context):
        """Test handling of S3UploadUtils exceptions."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_upload_utils:
            mock_upload_utils.side_effect = Exception(
                "S3UploadUtils initialization failed"
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path="./config",
                bucket_name="test-bucket",
                offer_pipeline_release=False,
            )

        assert result["success"] is False
        assert "error" in result
        assert "S3UploadUtils initialization failed" in result["error"]
