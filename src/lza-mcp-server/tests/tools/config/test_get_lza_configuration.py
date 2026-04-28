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

"""Tests for getLzaConfiguration tool — workspace-based implementation."""

import os
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.get_lza_configuration import (
    LzaConfigRetrieval,
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
    mgr.create_workspace = MagicMock(return_value="ws-new-123")
    mgr.list_files = MagicMock(return_value=[])
    mgr.write_file = MagicMock()
    mgr.create_folder = MagicMock()
    return mgr


@pytest.fixture
def retrieval(mock_ws_manager):
    return LzaConfigRetrieval(mock_ws_manager)


def _make_config_zip(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("accounts-config.yaml", "mandatoryAccounts: []")
        zf.writestr("global-config.yaml", "homeRegion: us-east-1")
        zf.writestr("sub/nested.yaml", "nested: true")


def _patch_identity():
    return patch(
        "awslabs.lza_mcp_server.tools.config.get_config_from_s3.get_caller_identity",
        return_value=IDENTITY,
    )


# ---------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------


class TestValidation:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_qualifier(self, ctx, retrieval):
        result = await retrieval.get_configuration(ctx, qualifier="bad@qual!")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_QUALIFIER"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_bucket_name(self, ctx, retrieval):
        result = await retrieval.get_configuration(ctx, bucket_name="AB")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BUCKET_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_none_qualifier_skips_validation(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                result = await retrieval.get_configuration(ctx, qualifier=None)
                assert result["error_code"] == "BUCKET_NOT_FOUND"


# ---------------------------------------------------------------
# Workspace resolution
# ---------------------------------------------------------------


class TestWorkspaceResolution:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_creates_new_workspace_when_none_provided(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is True
                assert result["workspace_id"] == "ws-new-123"
                assert result["workspace_created"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uses_existing_workspace(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(
                    ctx, workspace_id="ws-existing"
                )
                assert result["success"] is True
                assert result["workspace_id"] == "ws-existing"
                assert result["workspace_created"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_workspace_not_found(self, ctx, retrieval, mock_ws_manager):
        mock_ws_manager.list_files.side_effect = WorkspaceNotFoundError("not found")
        result = await retrieval.get_configuration(ctx, workspace_id="ws-bad")
        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"


# ---------------------------------------------------------------
# Bucket verification
# ---------------------------------------------------------------


class TestBucketVerification:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_standard_bucket_not_found(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is False
                assert result["error_code"] == "BUCKET_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_bucket_not_found(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                result = await retrieval.get_configuration(ctx, qualifier="env1")
                assert result["success"] is False
                assert result["error_code"] == "BUCKET_NOT_FOUND"


# ---------------------------------------------------------------
# S3 download errors
# ---------------------------------------------------------------


class TestDownloadErrors:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_such_key(self, ctx, retrieval):
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=ClientError(error_response, "GetObject")
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is False
                assert result["error_code"] == "OBJECT_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_other_client_error(self, ctx, retrieval):
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=ClientError(error_response, "GetObject")
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is False
                assert "S3 download failed" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_zip_file(self, ctx, retrieval):
        """Downloaded file is not a valid ZIP."""
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)

            def write_bad_zip(bucket, key, path):
                with open(path, "w") as f:
                    f.write("not a zip")

            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=write_bad_zip
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is False
                assert result["error_code"] == "INVALID_ZIP_FILE"


# ---------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------


class TestSuccess:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_standard_success(self, ctx, retrieval, mock_ws_manager):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is True
                assert result["workspace_id"] == "ws-new-123"
                assert result["qualifier"] is None
                assert result["object_key"] == "zipped/aws-accelerator-config.zip"
                assert result["file_count"] >= 2
                assert "sub" in result["root_folders"]
                assert "llm_instructions" in result
                # Verify workspace write_file was called
                assert mock_ws_manager.write_file.call_count >= 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_success(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx, qualifier="env1")
                assert result["success"] is True
                assert result["qualifier"] == "env1"
                assert result["object_key"] == "lza/aws-accelerator-config.zip"
                assert "env1" in result["llm_instructions"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_with_path(self, ctx, retrieval, mock_ws_manager):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(ctx, path="lza-config")
                assert result["success"] is True
                assert result["path"] == "lza-config"
                # Files should be written under the path prefix
                calls = mock_ws_manager.write_file.call_args_list
                for call in calls:
                    file_path = call[0][1]
                    assert file_path.startswith("lza-config/")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bucket_override_success(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                result = await retrieval.get_configuration(
                    ctx, bucket_name="custom-bucket"
                )
                assert result["success"] is True
                assert result["bucket_name"] == "custom-bucket"


# ---------------------------------------------------------------
# Unexpected exception
# ---------------------------------------------------------------


class TestUnexpectedError:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_exception_caught(self, ctx, retrieval):
        with _patch_identity() as mock_id:
            mock_id.side_effect = RuntimeError("boom")
            result = await retrieval.get_configuration(ctx)
            assert result["success"] is False
            assert result["error_code"] == "RETRIEVAL_ERROR"
            assert "boom" in result["error"]


# ---------------------------------------------------------------
# Temp ZIP cleanup
# ---------------------------------------------------------------


class TestTempZipCleanupFailure:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_temp_zip_remove_failure_non_fatal(self, ctx, retrieval):
        """If os.remove fails on the temp zip in finally, it should not crash."""
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                original_remove = os.remove

                def failing_remove(path):
                    if path.endswith(".zip"):
                        raise PermissionError("cannot delete zip")
                    return original_remove(path)

                with patch(
                    "awslabs.lza_mcp_server.tools.config.get_config_from_s3.os.remove",
                    side_effect=failing_remove,
                ):
                    result = await retrieval.get_configuration(ctx)
                    assert result["success"] is True
