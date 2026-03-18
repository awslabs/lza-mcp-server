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

import os
import shutil
import tempfile

import pytest
import yaml
from unittest.mock import patch, Mock

from awslabs.lza_mcp_server.tools.config.put_lza_configuration import (
    tool_put_lza_configuration,
)
from awslabs.lza_mcp_server.tools.config.get_minimum_configuration import (
    tool_get_minimum_configuration,
)

ACCOUNT = "123456789012"
REGION = "us-east-1"
IDENTITY = {"account_id": ACCOUNT, "user_arn": "arn:aws:iam::test", "region": REGION}


class TestPutLzaConfigurationIntegration:
    @pytest.mark.asyncio
    async def test_put_direct_upload_workflow(self, mock_mcp_context):
        """Direct upload via S3UploadUtils when no retrieved config exists."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_caller_identity",
            return_value=IDENTITY,
        ):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=None,
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3UploadUtils"
                ) as mock_utils_cls:
                    mock_instance = Mock()

                    async def mock_upload(*a, **kw):
                        return {"success": True, "operation": "direct_upload"}

                    mock_instance.upload_configuration = Mock(side_effect=mock_upload)
                    mock_utils_cls.return_value = mock_instance

                    result = await tool_put_lza_configuration(
                        mock_mcp_context,
                        config_path="./config",
                        bucket_name="test-bucket",
                    )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_put_error_handling(self, mock_mcp_context):
        """Exceptions from S3UploadUtils are returned as structured errors."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_caller_identity",
            return_value=IDENTITY,
        ):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=None,
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3UploadUtils"
                ) as mock_utils_cls:
                    mock_instance = Mock()

                    async def mock_upload(*a, **kw):
                        raise Exception("Upload failed")

                    mock_instance.upload_configuration = Mock(side_effect=mock_upload)
                    mock_utils_cls.return_value = mock_instance

                    result = await tool_put_lza_configuration(mock_mcp_context)

        assert result["success"] is False
        assert "error" in result


class TestConfigToolsEndToEnd:
    @pytest.mark.asyncio
    async def test_get_minimum_config_workflow(self, mock_mcp_context):
        temp_config_dir = tempfile.mkdtemp()
        temp_save_dir = tempfile.mkdtemp()
        try:
            sample = {
                "mandatoryAccounts": [
                    {
                        "name": "Management",
                        "email": "mgmt@example.com",
                        "organizationalUnit": "Root",
                        "warm": False,
                    }
                ]
            }
            with open(os.path.join(temp_config_dir, "accounts-config.yaml"), "w") as f:
                yaml.dump(sample, f)

            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
                result = await tool_get_minimum_configuration(
                    mock_mcp_context, config_type=None, save_to_directory=temp_save_dir
                )

            assert "config_files" in result
            assert "saved_to_directory" in result
        finally:
            shutil.rmtree(temp_config_dir)
            shutil.rmtree(temp_save_dir)

    @pytest.mark.asyncio
    async def test_config_validation_error_recovery(self, mock_mcp_context):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "accounts-config.yaml"), "w") as f:
                f.write("invalid: yaml: [unclosed")

            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_dir}):
                await tool_get_minimum_configuration(mock_mcp_context)

            assert len(mock_mcp_context.error_messages) > 0
        finally:
            shutil.rmtree(temp_dir)
