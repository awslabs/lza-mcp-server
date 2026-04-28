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
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceManager

ACCOUNT = "123456789012"
REGION = "us-east-1"
IDENTITY = {"account_id": ACCOUNT, "user_arn": "arn:aws:iam::test", "region": REGION}


class TestPutLzaConfigurationIntegration:
    @pytest.mark.asyncio
    async def test_put_workspace_upload_workflow(self, mock_mcp_context):
        """Upload from workspace when files exist."""
        mock_ws_manager = Mock()
        mock_ws_manager.list_files = Mock(
            return_value=["accounts-config.yaml", "global-config.yaml"]
        )
        mock_ws_manager.read_file = Mock(return_value=b"content")

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_config_to_s3.get_caller_identity",
            return_value=IDENTITY,
        ):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_config_to_s3.S3Manager"
            ) as mock_cls:
                from unittest.mock import AsyncMock

                mock_mgr = Mock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    mock_mcp_context,
                    mock_ws_manager,
                    "ws-123",
                    "",
                    bucket_name="test-bucket",
                )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_put_error_handling(self, mock_mcp_context):
        """Exceptions are returned as structured errors."""
        mock_ws_manager = Mock()
        mock_ws_manager.list_files = Mock(return_value=["accounts-config.yaml"])
        mock_ws_manager.read_file = Mock(return_value=b"content")

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_config_to_s3.get_caller_identity",
            side_effect=RuntimeError("boom"),
        ):
            result = await tool_put_lza_configuration(
                mock_mcp_context, mock_ws_manager, "ws-123", ""
            )

        assert result["success"] is False
        assert "error" in result


class TestConfigToolsEndToEnd:
    @pytest.mark.asyncio
    async def test_get_minimum_config_workflow(self, mock_mcp_context):
        temp_config_dir = tempfile.mkdtemp()
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

            mock_wm = Mock(spec=WorkspaceManager)
            mock_wm.create_workspace.return_value = "abc123def456"
            mock_wm.list_files.return_value = []
            mock_wm.write_file.return_value = None

            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_config_dir}):
                result = await tool_get_minimum_configuration(mock_mcp_context, mock_wm)

            assert "config_files" in result
            assert result["workspace_id"] == "abc123def456"
            assert result["workspace_created"] is True
            assert "files_written" in result
        finally:
            shutil.rmtree(temp_config_dir)

    @pytest.mark.asyncio
    async def test_config_validation_error_recovery(self, mock_mcp_context):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "accounts-config.yaml"), "w") as f:
                f.write("invalid: yaml: [unclosed")

            mock_wm = Mock(spec=WorkspaceManager)
            mock_wm.create_workspace.return_value = "abc123def456"
            mock_wm.list_files.return_value = []
            mock_wm.write_file.return_value = None

            with patch.dict(os.environ, {"LZA_MIN_CONFIG_DIR": temp_dir}):
                await tool_get_minimum_configuration(mock_mcp_context, mock_wm)

            assert len(mock_mcp_context.error_messages) > 0
        finally:
            shutil.rmtree(temp_dir)
