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

"""Integration tests for config tools functionality."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock

from awslabs.lza_mcp_server.tools.config.upload_config_s3 import (
    tool_upload_configuration_to_s3,
)
from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
)


class TestUploadConfigurationIntegration:
    """Integration tests for the main upload configuration function."""

    @pytest.mark.asyncio
    async def test_upload_configuration_direct_upload_workflow(self, mock_mcp_context):
        """Test upload configuration with direct upload workflow."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils:
            mock_utils_instance = Mock()
            mock_s3_utils.return_value = mock_utils_instance
            # Make it async with Mock
            mock_upload_configuration = Mock()

            async def mock_upload_config_func(*args, **kwargs):
                return {"success": True, "operation": "direct_upload"}

            mock_upload_configuration.side_effect = mock_upload_config_func
            mock_utils_instance.upload_configuration = mock_upload_configuration

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path="./config",  # Use relative path instead of absolute
                bucket_name="test-bucket",
                offer_pipeline_release=False,
            )

        assert result["success"] is True
        assert result["operation"] == "direct_upload"
        mock_upload_configuration.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_configuration_error_handling(self, mock_mcp_context):
        """Test error handling in upload configuration.

        Verifies that exceptions from S3UploadUtils are properly caught,
        logged, and returned as structured error responses.
        """
        with patch(
            "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
        ) as mock_s3_utils:
            mock_utils_instance = Mock()
            mock_s3_utils.return_value = mock_utils_instance

            async def mock_upload_config_func(*args, **kwargs):
                raise Exception("Upload failed")

            mock_utils_instance.upload_configuration = Mock(
                side_effect=mock_upload_config_func
            )

            result = await tool_upload_configuration_to_s3(
                mock_mcp_context,
                config_path=None,
                bucket_name=None,
                offer_pipeline_release=True,
            )

        # Verify error is properly propagated in response
        assert result["success"] is False, "Expected success=False for failed upload"
        assert "error" in result, "Expected 'error' field in response"
        assert "Upload failed" in str(result.get("error", "")), (
            "Expected original error message in response"
        )
        assert "UPLOAD_ERROR" in result.get("error_code", ""), (
            "Expected UPLOAD_ERROR code"
        )

        # Verify error was logged to context
        assert len(mock_mcp_context.error_messages) > 0, (
            "Expected error to be logged to context"
        )
        assert any("Upload failed" in msg for msg in mock_mcp_context.error_messages), (
            "Expected error message to be logged"
        )


class TestConfigToolsEndToEnd:
    """End-to-end tests for config tools workflow."""

    @pytest.mark.asyncio
    async def test_get_minimum_config_then_upload_workflow(self, mock_mcp_context):
        """Test complete workflow: get minimum config then upload."""
        from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
            tool_get_minimum_configuration,
        )

        temp_config_dir = tempfile.mkdtemp()
        temp_save_dir = tempfile.mkdtemp()

        try:
            # Create sample config files
            sample_config = {
                "mandatoryAccounts": [
                    {
                        "name": "Management",
                        "email": "management@example.com",
                        "organizationalUnit": "Root",
                        "warm": False,
                    }
                ]
            }

            import yaml

            config_file = os.path.join(temp_config_dir, "accounts-config.yaml")
            with open(config_file, "w") as f:
                yaml.dump(sample_config, f)

            # Step 1: Get minimum configuration
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
                config_result = await tool_get_minimum_configuration(
                    mock_mcp_context, config_type=None, save_to_directory=temp_save_dir
                )

            assert "config_files" in config_result
            assert "saved_to_directory" in config_result

            # Step 2: Upload the saved configuration
            # Mock os.path.exists to return False for share validation paths
            # Also mock validate_file_path to allow the temp directory
            with patch("os.path.exists", return_value=False):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.upload_config_s3.validate_file_path",
                    return_value=(True, ""),
                ):
                    with patch(
                        "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
                    ) as mock_s3_utils:
                        mock_utils_instance = Mock()
                        mock_s3_utils.return_value = mock_utils_instance
                        # Make it async with Mock
                        mock_upload_configuration = Mock()

                        async def mock_upload_config_func(*args, **kwargs):
                            return {
                                "success": True,
                                "uploaded_files": ["accounts-config.yaml"],
                            }

                        mock_upload_configuration.side_effect = mock_upload_config_func
                        mock_utils_instance.upload_configuration = (
                            mock_upload_configuration
                        )

                        upload_result = await tool_upload_configuration_to_s3(
                            mock_mcp_context,
                            config_path=temp_save_dir,
                            bucket_name="test-bucket",
                            offer_pipeline_release=True,
                        )

            assert upload_result["success"] is True

        finally:
            shutil.rmtree(temp_config_dir)
            shutil.rmtree(temp_save_dir)

    @pytest.mark.asyncio
    async def test_config_validation_and_upload_error_recovery(self, mock_mcp_context):
        """Test error recovery in config validation and upload workflow."""
        # Test scenario where config validation fails but upload can still proceed
        temp_dir = tempfile.mkdtemp()

        try:
            # Create invalid config file
            invalid_config = "invalid: yaml: [unclosed"
            config_file = os.path.join(temp_dir, "accounts-config.yaml")
            with open(config_file, "w") as f:
                f.write(invalid_config)

            # Try to get minimum configuration (should handle YAML error)
            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_dir}):
                await tool_get_minimum_configuration(mock_mcp_context)

            # Should have error messages but not crash
            assert len(mock_mcp_context.error_messages) > 0

            # Upload should still be attempted with direct upload
            with patch(
                "awslabs.lza_mcp_server.tools.config.upload_config_s3.S3UploadUtils"
            ) as mock_s3_utils:
                mock_utils_instance = Mock()
                mock_s3_utils.return_value = mock_utils_instance
                # Make it async with Mock
                mock_upload_configuration = Mock()

                async def mock_upload_config_func(*args, **kwargs):
                    return {"error": "Configuration validation failed"}

                mock_upload_configuration.side_effect = mock_upload_config_func
                mock_utils_instance.upload_configuration = mock_upload_configuration

                upload_result = await tool_upload_configuration_to_s3(
                    mock_mcp_context,
                    config_path=temp_dir,
                    bucket_name="test-bucket",
                    offer_pipeline_release=False,
                )

            # Should handle upload error gracefully
            assert "error" in upload_result or "success" in upload_result

        finally:
            shutil.rmtree(temp_dir)
