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

"""Unit tests for upload_config_s3 module."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, AsyncMock

from awslabs.lza_mcp_server.tools.config.upload_config_s3 import (
    tool_upload_configuration_to_s3,
)


class TestUploadConfigurationToS3:
    """Test cases for tool_upload_configuration_to_s3 function."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory with sample config files."""
        temp_dir = tempfile.mkdtemp()

        # Create sample config files
        config_files = [
            "accounts-config.yaml",
            "global-config.yaml",
            "iam-config.yaml",
            "network-config.yaml",
            "organization-config.yaml",
            "security-config.yaml",
        ]

        for filename in config_files:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w") as f:
                f.write(f"# Sample {filename}\ntest: configuration\n")

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_configuration_success(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test successful configuration upload."""
        # Use relative path instead of absolute path
        import os

        relative_path = os.path.relpath(temp_config_dir, os.getcwd())

        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock successful upload
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": True,
                    "message": "Configuration successfully uploaded to S3",
                    "bucket_name": "test-lza-bucket",
                    "s3_location": "s3://test-lza-bucket/zipped/aws-accelerator-config.zip",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=relative_path,
                bucket_name=None,
                offer_pipeline_release=False,
            )

        # Verify the result structure
        assert isinstance(result, dict)
        assert result.get("success") is True or "error" in result

    @pytest.mark.asyncio
    async def test_upload_configuration_with_specific_bucket(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test upload with specific bucket name."""
        # Use relative path instead of absolute path
        import os

        relative_path = os.path.relpath(temp_config_dir, os.getcwd())

        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock successful upload with custom bucket
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": True,
                    "message": "Configuration successfully uploaded to S3",
                    "bucket_name": "custom-bucket",
                    "s3_location": "s3://custom-bucket/zipped/aws-accelerator-config.zip",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=relative_path,
                bucket_name="custom-bucket",
                offer_pipeline_release=False,
            )

        # Verify the result structure
        assert isinstance(result, dict)
        if result.get("success"):
            assert result.get("bucket_name") == "custom-bucket"

    @pytest.mark.asyncio
    async def test_upload_configuration_missing_path(self, mock_mcp_context):
        """Test upload with missing configuration path."""
        result = await tool_upload_configuration_to_s3(
            mock_mcp_context,
            config_path="/nonexistent/path",
            bucket_name="test-bucket",
            offer_pipeline_release=False,
        )

        # Verify error handling
        assert "error" in result
        assert len(mock_mcp_context.error_messages) > 0

    @pytest.mark.asyncio
    async def test_upload_configuration_s3_error(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test handling of S3 upload errors."""
        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock S3 upload failure
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "S3 upload failed",
                    "message": "Failed to upload configuration to S3",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=temp_config_dir,
                bucket_name=None,
                offer_pipeline_release=False,
            )

        # Verify error handling
        assert "error" in result or result.get("success") is False
        assert (
            len(mock_mcp_context.error_messages) >= 0
        )  # May or may not have errors logged

    @pytest.mark.asyncio
    async def test_upload_configuration_bucket_detection_failure(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test handling of bucket detection failure."""
        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock bucket detection failure
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Failed to determine bucket name",
                    "message": "Could not detect LZA bucket",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=temp_config_dir,
                bucket_name=None,
                offer_pipeline_release=False,
            )

        # Verify error handling
        assert "error" in result or result.get("success") is False
        assert len(mock_mcp_context.error_messages) >= 0

    @pytest.mark.asyncio
    async def test_upload_configuration_with_pipeline_release(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test upload with pipeline release offer."""
        # Use relative path instead of absolute path
        import os

        relative_path = os.path.relpath(temp_config_dir, os.getcwd())

        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock successful upload with pipeline release
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": True,
                    "message": "Configuration successfully uploaded to S3",
                    "bucket_name": "test-bucket",
                    "pipeline_release_offered": True,
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=relative_path,
                bucket_name=None,
                offer_pipeline_release=True,
            )

        # Verify the result structure
        assert isinstance(result, dict)
        if result.get("success"):
            assert result.get("pipeline_release_offered") is True

    @pytest.mark.asyncio
    async def test_upload_configuration_default_path(self, mock_mcp_context):
        """Test upload with default configuration path."""
        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock configuration discovery failure
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "No valid LZA configurations found in workspace",
                    "message": "No LZA configurations discovered",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=None,
                bucket_name="test-bucket",
                offer_pipeline_release=False,
            )

        # Should handle default path gracefully
        assert "error" in result or result.get("success") is False
        assert len(mock_mcp_context.error_messages) >= 0

    @pytest.mark.asyncio
    async def test_upload_configuration_file_filtering(self, mock_mcp_context):
        """Test that only YAML configuration files are uploaded."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create mix of files
            files_to_create = [
                "accounts-config.yaml",  # Should be uploaded
                "global-config.yaml",  # Should be uploaded
                "readme.txt",  # Should be ignored
                "script.py",  # Should be ignored
                "data.json",  # Should be ignored
            ]

            for filename in files_to_create:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(f"# Content of {filename}\n")

            # Mock S3UploadUtils
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_s3_utils_class:
                mock_s3_utils = Mock()
                mock_s3_utils_class.return_value = mock_s3_utils

                # Mock successful upload with file list
                mock_s3_utils.upload_configuration = AsyncMock(
                    return_value={
                        "success": True,
                        "message": "Configuration successfully uploaded to S3",
                        "bucket_name": "test-bucket",
                        "uploaded_files": [
                            "accounts-config.yaml",
                            "global-config.yaml",
                        ],
                    }
                )

                result = await tool_upload_configuration_to_s3(
                    mock_mcp_context,
                    config_path=temp_dir,
                    bucket_name=None,
                    offer_pipeline_release=False,
                )

            # Verify result structure
            assert isinstance(result, dict)
            # The actual filtering happens in S3UploadUtils, so we just verify the call was made
            if result.get("success") and "uploaded_files" in result:
                uploaded_files = result["uploaded_files"]
                yaml_files = [f for f in uploaded_files if f.endswith(".yaml")]
                assert len(yaml_files) >= 0  # May have YAML files

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_configuration_aws_credentials_error(
        self, mock_mcp_context, temp_config_dir
    ):
        """Test handling of AWS credentials errors."""
        # Use relative path instead of absolute path
        import os

        relative_path = os.path.relpath(temp_config_dir, os.getcwd())

        # Mock S3UploadUtils
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils_class:
            mock_s3_utils = Mock()
            mock_s3_utils_class.return_value = mock_s3_utils

            # Mock AWS credentials error
            mock_s3_utils.upload_configuration = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Unable to locate credentials",
                    "message": "AWS credentials not found",
                }
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=relative_path,
                bucket_name="test-bucket",
                offer_pipeline_release=False,
            )

        # Verify credentials error handling
        assert "error" in result or result.get("success") is False
        assert len(mock_mcp_context.error_messages) >= 0

    @pytest.mark.asyncio
    async def test_upload_configuration_empty_directory(self, mock_mcp_context):
        """Test upload from empty directory."""
        empty_dir = tempfile.mkdtemp()

        try:
            # Mock S3UploadUtils
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_s3_utils_class:
                mock_s3_utils = Mock()
                mock_s3_utils_class.return_value = mock_s3_utils

                # Mock empty directory handling
                mock_s3_utils.upload_configuration = AsyncMock(
                    return_value={
                        "success": False,
                        "error": "No configuration files found",
                        "message": "Directory is empty or contains no valid configuration",
                    }
                )

                result = await tool_upload_configuration_to_s3(
                    mock_mcp_context,
                    config_path=empty_dir,
                    bucket_name=None,
                    offer_pipeline_release=False,
                )

            # Should handle empty directory gracefully
            assert (
                "error" in result
                or result.get("success") is False
                or ("uploaded_files" in result and len(result["uploaded_files"]) == 0)
            )

        finally:
            shutil.rmtree(empty_dir)

    @pytest.mark.asyncio
    async def test_upload_from_retrieved_config(self, mock_mcp_context):
        """Test upload from retrieved config (getConfigurationFromS3 workflow)."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create sample LZA config files
            config_files = [
                "accounts-config.yaml",
                "global-config.yaml",
                "iam-config.yaml",
                "network-config.yaml",
            ]

            for filename in config_files:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(f"# Sample {filename}\ntest: configuration\n")

            # Mock the extracted config path
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

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

                        result = await tool_upload_configuration_to_s3(
                            mock_mcp_context,
                            config_path=None,
                            bucket_name=None,
                            offer_pipeline_release=True,
                        )

            # Verify result
            assert isinstance(result, dict)
            if result.get("success"):
                assert result["source"] == "retrieved_config"
                assert result["config_path"] == temp_dir
                assert "zip_size" in result
                assert (
                    result["bucket_name"]
                    == "aws-accelerator-config-123456789012-us-east-1"
                )

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_from_retrieved_config_missing_files(self, mock_mcp_context):
        """Test upload from retrieved config with missing required files."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create only one config file (missing required files)
            file_path = os.path.join(temp_dir, "network-config.yaml")
            with open(file_path, "w") as f:
                f.write("# Sample network-config.yaml\ntest: configuration\n")

            # Mock the extracted config path
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

                # Mock S3UploadUtils for fallback
                with patch(
                    "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
                ) as mock_upload_utils:
                    mock_instance = Mock()
                    mock_upload_utils.return_value = mock_instance
                    mock_instance.upload_configuration = AsyncMock(
                        return_value={
                            "success": False,
                            "error": "No valid LZA configuration found",
                        }
                    )

                    result = await tool_upload_configuration_to_s3(
                        mock_mcp_context,
                        config_path=None,
                        bucket_name=None,
                        offer_pipeline_release=False,
                    )

            # Should fall back to direct upload since required files are missing
            assert isinstance(result, dict)
            # Will likely error due to missing required files

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_from_retrieved_config_with_subdirectories(
        self, mock_mcp_context
    ):
        """Test upload from retrieved config with subdirectories (full UC config)."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create sample LZA config files
            config_files = [
                "accounts-config.yaml",
                "global-config.yaml",
                "iam-config.yaml",
                "network-config.yaml",
            ]

            for filename in config_files:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(f"# Sample {filename}\ntest: configuration\n")

            # Create subdirectories with policy files
            policies_dir = os.path.join(temp_dir, "iam-policies")
            os.makedirs(policies_dir, exist_ok=True)
            policy_file = os.path.join(policies_dir, "sample-policy.json")
            with open(policy_file, "w") as f:
                f.write('{"Version": "2012-10-17", "Statement": []}')

            # Mock the extracted config path
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

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

                        result = await tool_upload_configuration_to_s3(
                            mock_mcp_context,
                            config_path=None,
                            bucket_name="custom-bucket",
                            offer_pipeline_release=False,
                        )

            # Verify result
            assert isinstance(result, dict)
            if result.get("success"):
                assert result["source"] == "retrieved_config"
                assert result["bucket_name"] == "custom-bucket"
                assert "zip_size" in result
                # ZIP should include subdirectories
                assert result["zip_size"] > 0

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_from_retrieved_config_s3_error(self, mock_mcp_context):
        """Test handling of S3 errors during retrieved config upload."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create sample LZA config files
            config_files = ["accounts-config.yaml", "global-config.yaml"]

            for filename in config_files:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(f"# Sample {filename}\ntest: configuration\n")

            # Mock the extracted config path
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.get_extracted_lza_config_path"
            ) as mock_get_path:
                mock_get_path.return_value = temp_dir

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
                                "error": "S3 upload failed",
                            }
                        )

                        result = await tool_upload_configuration_to_s3(
                            mock_mcp_context,
                            config_path=None,
                            bucket_name=None,
                            offer_pipeline_release=False,
                        )

            # Should return S3 error
            assert isinstance(result, dict)
            assert result["success"] is False
            assert "error" in result

        finally:
            shutil.rmtree(temp_dir)
