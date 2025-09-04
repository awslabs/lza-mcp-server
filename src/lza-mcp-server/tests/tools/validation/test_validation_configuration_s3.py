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

"""Unit tests for validation configuration S3 module."""

import pytest
import os
import tempfile
import zipfile
from unittest.mock import patch, AsyncMock

from awslabs.lza_mcp_server.tools.validation.validation_configuration_s3 import (
    tool_validate_configuration_from_s3,
    _offer_s3_upload_after_validation,
    _integrate_s3_upload_workflow,
)


class MockContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info = AsyncMock()
        self.error = AsyncMock()


class TestOfferS3UploadAfterValidation:
    """Test cases for _offer_s3_upload_after_validation function."""

    @pytest.mark.asyncio
    async def test_offer_s3_upload_success(self):
        """Test successful S3 upload offer."""
        mock_ctx = MockContext()
        config_path = "/test/config"
        validation_result = {"valid": True, "message": "Success"}

        result = await _offer_s3_upload_after_validation(
            mock_ctx, config_path, validation_result
        )

        assert result["upload_offered"] is True
        assert result["user_prompted"] is True
        assert result["config_path"] == config_path
        assert result["validation_result"] == validation_result
        assert "next_steps" in result
        assert len(result["next_steps"]) == 3

        # Verify context info calls were made
        mock_ctx.info.assert_called()

    @pytest.mark.asyncio
    async def test_offer_s3_upload_error(self):
        """Test S3 upload offer with error."""
        mock_ctx = MockContext()

        with patch.object(mock_ctx, "info", side_effect=Exception("Context error")):
            result = await _offer_s3_upload_after_validation(mock_ctx, "/test", {})

            assert result["upload_offered"] is False
            assert "error" in result
            assert "Context error" in result["error"]


class TestIntegrateS3UploadWorkflow:
    """Test cases for _integrate_s3_upload_workflow function."""

    @pytest.mark.asyncio
    async def test_integrate_s3_upload_workflow_success(self):
        """Test successful S3 upload workflow integration."""
        mock_ctx = MockContext()
        config_path = "/test/config"
        validation_result = {"valid": True, "message": "Success"}

        result = await _integrate_s3_upload_workflow(
            mock_ctx, config_path, validation_result
        )

        assert "validation" in result
        assert "s3_upload_integration" in result
        assert result["s3_upload_integration"]["available"] is True
        assert result["s3_upload_integration"]["offered"] is True

    @pytest.mark.asyncio
    async def test_integrate_s3_upload_workflow_validation_failed(self):
        """Test S3 upload workflow integration when validation failed."""
        mock_ctx = MockContext()
        config_path = "/test/config"
        validation_result = {"valid": False, "errors": ["Test error"]}

        result = await _integrate_s3_upload_workflow(
            mock_ctx, config_path, validation_result
        )

        assert result["s3_upload_integration"]["available"] is False
        assert result["s3_upload_integration"]["reason"] == "validation_failed"

    @pytest.mark.asyncio
    async def test_integrate_s3_upload_workflow_error(self):
        """Test S3 upload workflow integration with error."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3._offer_s3_upload_after_validation",
            side_effect=Exception("Integration error"),
        ):
            result = await _integrate_s3_upload_workflow(
                mock_ctx, "/test", {"valid": True}
            )

            assert result["s3_upload_integration"]["available"] is False
            assert "error" in result["s3_upload_integration"]


class TestToolValidateConfigurationFromS3:
    """Test cases for tool_validate_configuration_from_s3 function."""

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_local_path_error(self):
        """Test validation with local file path (should fail)."""
        mock_ctx = MockContext()

        result = await tool_validate_configuration_from_s3(
            mock_ctx, "/local/path/config.zip"
        )

        assert result["valid"] is False
        assert "Local file paths cannot be used" in result["errors"][0]["message"]
        assert "workflow_correction" in result

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_windows_path_error(self):
        """Test validation with Windows file path (should fail)."""
        mock_ctx = MockContext()

        result = await tool_validate_configuration_from_s3(
            mock_ctx, "C:\\local\\path\\config.zip"
        )

        assert result["valid"] is False
        assert "Local file paths cannot be used" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_invalid_s3_path(self):
        """Test validation with invalid S3 path format."""
        mock_ctx = MockContext()

        result = await tool_validate_configuration_from_s3(mock_ctx, "invalid-path")

        assert result["valid"] is False
        assert "Invalid S3 path format" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_download_failure(self):
        """Test validation when S3 download fails."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
            return_value=False,
        ):
            result = await tool_validate_configuration_from_s3(
                mock_ctx, "s3://test-bucket/config.zip"
            )

            assert result["valid"] is False
            assert (
                "Failed to download ZIP file from S3" in result["errors"][0]["message"]
            )

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_invalid_zip(self):
        """Test validation with invalid ZIP file."""
        mock_ctx = MockContext()

        with (
            patch(
                "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                return_value=True,
            ),
            patch("zipfile.is_zipfile", return_value=False),
        ):
            result = await tool_validate_configuration_from_s3(
                mock_ctx, "s3://test-bucket/config.zip"
            )

            assert result["valid"] is False
            assert "not a valid ZIP archive" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_success(self):
        """Test successful S3 validation."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", "key: value\n")

            def mock_download(bucket, key, local_path):
                # Copy our test ZIP to the expected location
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                    side_effect=mock_download,
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/config.zip"
                )

                assert result["valid"] is True
                assert result["message"] == "Success"
                mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_success_with_s3_prefix(self):
        """Test successful S3 validation with s3:// prefix."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", "key: value\n")

            def mock_download(bucket, key, local_path):
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                    side_effect=mock_download,
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/path/config.zip"
                )

                assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_bad_zip_file(self):
        """Test validation with corrupted ZIP file."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a corrupted ZIP file
            zip_path = os.path.join(temp_dir, "config.zip")
            with open(zip_path, "w") as f:
                f.write("corrupted zip content")

            def mock_download(bucket, key, local_path):
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with patch(
                "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                side_effect=mock_download,
            ):
                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/config.zip"
                )

                assert result["valid"] is False
                assert (
                    "The downloaded file is not a valid ZIP archive"
                    in result["errors"][0]["message"]
                )

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_with_s3_integration(self):
        """Test successful validation with S3 upload integration."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", "key: value\n")

            def mock_download(bucket, key, local_path):
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                    side_effect=mock_download,
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_validate.return_value = {"valid": True, "message": "Success"}

                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/config.zip"
                )

                assert result["valid"] is True
                assert "s3_upload_integration" in result
                assert result["s3_upload_integration"]["available"] is True

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_validation_failed_no_integration(
        self,
    ):
        """Test that S3 integration is not added when validation fails."""
        mock_ctx = MockContext()

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test-config.yaml", "key: value\n")

            def mock_download(bucket, key, local_path):
                import shutil

                shutil.copy2(zip_path, local_path)
                return True

            with (
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
                    side_effect=mock_download,
                ),
                patch(
                    "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.validate_configuration_impl"
                ) as mock_validate,
            ):
                mock_validate.return_value = {"valid": False, "errors": ["Test error"]}

                result = await tool_validate_configuration_from_s3(
                    mock_ctx, "s3://test-bucket/config.zip"
                )

                assert result["valid"] is False
                assert "s3_upload_integration" not in result

    @pytest.mark.asyncio
    async def test_validate_configuration_from_s3_unexpected_error(self):
        """Test validation with unexpected error."""
        mock_ctx = MockContext()

        with patch(
            "awslabs.lza_mcp_server.tools.validation.validation_configuration_s3.download_from_s3",
            side_effect=Exception("Unexpected error"),
        ):
            result = await tool_validate_configuration_from_s3(
                mock_ctx, "s3://test-bucket/config.zip"
            )

            assert result["valid"] is False
            assert "Error during S3 validation" in result["errors"][0]["message"]
            assert "Unexpected error" in result["errors"][0]["message"]
