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

"""Tests for putLzaConfiguration tool — workspace-based implementation."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from awslabs.lza_mcp_server.tools.config.put_lza_configuration import (
    tool_put_lza_configuration,
    _zip_workspace_files,
)
from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceNotFoundError,
)

ACCOUNT = "123456789012"
REGION = "us-east-1"
IDENTITY = {"account_id": ACCOUNT, "user_arn": "arn:aws:iam::test", "region": REGION}


@pytest.fixture
def ctx():
    c = MagicMock()
    c.info = AsyncMock()
    c.error = AsyncMock()
    return c


@pytest.fixture
def mock_ws_manager():
    mgr = MagicMock()
    mgr.list_files = MagicMock(
        return_value=[
            "accounts-config.yaml",
            "global-config.yaml",
            "network-config.yaml",
        ]
    )
    mgr.read_file = MagicMock(return_value=b"content")
    return mgr


def _patch_identity():
    return patch(
        "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_caller_identity",
        return_value=IDENTITY,
    )


# ---------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_qualifier(self, ctx, mock_ws_manager):
        result = await tool_put_lza_configuration(
            ctx, mock_ws_manager, "ws-123", "", qualifier="bad@qual!"
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_QUALIFIER"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_bucket_name(self, ctx, mock_ws_manager):
        result = await tool_put_lza_configuration(
            ctx, mock_ws_manager, "ws-123", "", bucket_name="AB"
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BUCKET_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_workspace_not_found(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.side_effect = WorkspaceNotFoundError("not found")
        result = await tool_put_lza_configuration(ctx, mock_ws_manager, "ws-bad", "")
        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_workspace(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = []
        with _patch_identity():
            result = await tool_put_lza_configuration(
                ctx, mock_ws_manager, "ws-123", ""
            )
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONFIGURATION"

    @pytest.mark.asyncio
    @pytest.mark.unit
    @pytest.mark.parametrize("root_path", ["/", "."])
    async def test_root_path_normalized_to_empty(self, ctx, mock_ws_manager, root_path):
        """Paths '/' and '.' should be treated as workspace root (empty string)."""
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    ctx, mock_ws_manager, "ws-123", root_path
                )
                assert result["success"] is True
                assert result["path"] == ""
                assert result["file_count"] == 3


# ---------------------------------------------------------------
# _zip_workspace_files
# ---------------------------------------------------------------


class TestZipWorkspaceFiles:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_zips_all_files_no_prefix(self, mock_ws_manager):
        zip_bytes = await _zip_workspace_files(mock_ws_manager, "ws-123", "")
        assert len(zip_bytes) > 0
        assert mock_ws_manager.read_file.call_count == 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_zips_files_with_prefix(self, mock_ws_manager):
        mock_ws_manager.list_files.return_value = [
            "config/accounts-config.yaml",
            "config/global-config.yaml",
            "other/readme.md",
        ]
        zip_bytes = await _zip_workspace_files(mock_ws_manager, "ws-123", "config")  # noqa: F841
        # Should only zip the 2 files under config/
        assert mock_ws_manager.read_file.call_count == 2


# ---------------------------------------------------------------
# S3 location resolution
# ---------------------------------------------------------------


class TestResolve:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_standard_uses_correct_bucket(self, ctx, mock_ws_manager):
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    ctx, mock_ws_manager, "ws-123", ""
                )
                assert result["success"] is True
                assert (
                    result["bucket_name"]
                    == f"aws-accelerator-config-{ACCOUNT}-{REGION}"
                )
                assert result["object_key"] == "zipped/aws-accelerator-config.zip"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_uses_correct_bucket(self, ctx, mock_ws_manager):
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    ctx, mock_ws_manager, "ws-123", "", qualifier="env1"
                )
                assert result["success"] is True
                assert result["bucket_name"] == f"env1-config-{ACCOUNT}-{REGION}"
                assert result["object_key"] == "lza/aws-accelerator-config.zip"


# ---------------------------------------------------------------
# Successful upload
# ---------------------------------------------------------------


class TestSuccessfulUpload:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_upload_returns_workspace_info(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = [
            "config/accounts-config.yaml",
            "config/global-config.yaml",
            "config/network-config.yaml",
        ]
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    ctx, mock_ws_manager, "ws-123", "config"
                )
                assert result["success"] is True
                assert result["workspace_id"] == "ws-123"
                assert result["path"] == "config"
                assert result["file_count"] == 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_upload_failure_propagated(self, ctx, mock_ws_manager):
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(
                    return_value={"success": False, "error": "denied"}
                )
                mock_cls.return_value = mock_mgr

                result = await tool_put_lza_configuration(
                    ctx, mock_ws_manager, "ws-123", ""
                )
                assert result["success"] is False


# ---------------------------------------------------------------
# Unexpected exception
# ---------------------------------------------------------------


class TestUnexpectedError:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_exception_caught(self, ctx, mock_ws_manager):
        with _patch_identity() as mock_id:
            mock_id.side_effect = RuntimeError("boom")
            result = await tool_put_lza_configuration(
                ctx, mock_ws_manager, "ws-123", ""
            )
            assert result["success"] is False
            assert "boom" in result["error"]


# ---------------------------------------------------------------
# Temp ZIP cleanup
# ---------------------------------------------------------------


class TestZipCleanupFailure:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_temp_zip_remove_failure_non_fatal(self, ctx, mock_ws_manager):
        """If os.remove fails on the temp zip in finally, it should not crash."""
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
            ) as mock_cls:
                mock_mgr = MagicMock()
                mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
                mock_cls.return_value = mock_mgr

                original_remove = os.remove

                def failing_remove(path):
                    if path.endswith(".zip"):
                        raise PermissionError("cannot delete zip")
                    return original_remove(path)

                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.os.remove",
                    side_effect=failing_remove,
                ):
                    result = await tool_put_lza_configuration(
                        ctx, mock_ws_manager, "ws-123", ""
                    )
                    assert result["success"] is True
