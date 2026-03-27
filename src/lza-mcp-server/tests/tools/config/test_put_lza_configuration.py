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

"""Tests for putLzaConfiguration tool — targeting ~100 % coverage."""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from awslabs.lza_mcp_server.tools.config.put_lza_configuration import (
    tool_put_lza_configuration,
    _detect_retrieved_config,
    _zip_and_upload,
)
from awslabs.lza_mcp_server.tools.config.config_s3_resolver import ConfigS3Location

ACCOUNT = "123456789012"
REGION = "us-east-1"
IDENTITY = {"account_id": ACCOUNT, "user_arn": "arn:aws:iam::test", "region": REGION}


@pytest.fixture
def ctx():
    c = MagicMock()
    c.info = AsyncMock()
    c.error = AsyncMock()
    return c


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
    async def test_invalid_qualifier(self, ctx):
        result = await tool_put_lza_configuration(ctx, qualifier="bad@qual!")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_QUALIFIER"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_bucket_name(self, ctx):
        result = await tool_put_lza_configuration(ctx, bucket_name="AB")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BUCKET_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_config_path(self, ctx):
        result = await tool_put_lza_configuration(ctx, config_path="../escape")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_CONFIG_PATH"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_host_path_users_rejected(self, ctx):
        result = await tool_put_lza_configuration(ctx, config_path="/Users/someone/cfg")
        assert result["success"] is False
        assert result.get("error_code") in ("INVALID_CONFIG_PATH", "HOST_PATH_PROVIDED")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_host_path_tilde_rejected(self, ctx):
        result = await tool_put_lza_configuration(ctx, config_path="~/my-config")
        assert result["success"] is False
        assert result.get("error_code") in ("INVALID_CONFIG_PATH", "HOST_PATH_PROVIDED")


# ---------------------------------------------------------------
# _detect_retrieved_config
# ---------------------------------------------------------------


class TestDetectRetrievedConfig:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_detected_when_valid(self, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        (d / "global-config.yaml").write_text("b")
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
            return_value=Path(str(d)),
        ):
            result = await _detect_retrieved_config()
            assert result["detected"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_not_detected_when_none(self):
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
            return_value=None,
        ):
            result = await _detect_retrieved_config()
            assert result["detected"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_not_detected_when_missing_files(self, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        # missing global-config.yaml
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
            return_value=Path(str(d)),
        ):
            result = await _detect_retrieved_config()
            assert result["detected"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_not_detected_when_path_does_not_exist(self):
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
            return_value=Path("/nonexistent/path"),
        ):
            result = await _detect_retrieved_config()
            assert result["detected"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_exception_returns_not_detected(self):
        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
            side_effect=RuntimeError("boom"),
        ):
            result = await _detect_retrieved_config()
            assert result["detected"] is False


# ---------------------------------------------------------------
# _zip_and_upload
# ---------------------------------------------------------------


class TestZipAndUpload:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        sub = d / "policies"
        sub.mkdir()
        (sub / "p.json").write_text("{}")

        location = ConfigS3Location(
            bucket_name="test-bucket",
            object_key="zipped/aws-accelerator-config.zip",
            account_id=ACCOUNT,
            region=REGION,
            qualifier=None,
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
        ) as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.upload_zip_file = AsyncMock(return_value={"success": True})
            mock_cls.return_value = mock_mgr

            result = await _zip_and_upload(ctx, str(d), location)
            assert result["success"] is True
            assert result["bucket_name"] == "test-bucket"
            assert result["zip_size"] > 0
            mock_mgr.upload_zip_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_upload_failure_propagated(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")

        location = ConfigS3Location(
            bucket_name="b",
            object_key="k",
            account_id=ACCOUNT,
            region=REGION,
            qualifier=None,
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
        ) as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.upload_zip_file = AsyncMock(
                return_value={"success": False, "error": "denied"}
            )
            mock_cls.return_value = mock_mgr

            result = await _zip_and_upload(ctx, str(d), location)
            assert result["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_exception_returns_error(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")

        location = ConfigS3Location(
            bucket_name="b",
            object_key="k",
            account_id=ACCOUNT,
            region=REGION,
            qualifier=None,
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3Manager"
        ) as mock_cls:
            mock_mgr = MagicMock()
            mock_mgr.upload_zip_file = AsyncMock(side_effect=RuntimeError("boom"))
            mock_cls.return_value = mock_mgr

            result = await _zip_and_upload(ctx, str(d), location)
            assert result["success"] is False
            assert "boom" in result["error"]


# ---------------------------------------------------------------
# tool_put_lza_configuration — S3 location resolution
# ---------------------------------------------------------------


class TestResolve:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_standard_uses_correct_bucket(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        (d / "global-config.yaml").write_text("b")

        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=Path(str(d)),
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration._zip_and_upload",
                    new_callable=AsyncMock,
                ) as mock_upload:
                    mock_upload.return_value = {"success": True}
                    await tool_put_lza_configuration(ctx)
                    loc = mock_upload.call_args[0][2]
                    assert (
                        loc.bucket_name == f"aws-accelerator-config-{ACCOUNT}-{REGION}"
                    )
                    assert loc.object_key == "zipped/aws-accelerator-config.zip"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_uses_correct_bucket(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        (d / "global-config.yaml").write_text("b")

        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=Path(str(d)),
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration._zip_and_upload",
                    new_callable=AsyncMock,
                ) as mock_upload:
                    mock_upload.return_value = {"success": True}
                    await tool_put_lza_configuration(ctx, qualifier="env1")
                    loc = mock_upload.call_args[0][2]
                    assert loc.bucket_name == f"env1-config-{ACCOUNT}-{REGION}"
                    assert loc.object_key == "lza/aws-accelerator-config.zip"


# ---------------------------------------------------------------
# Auto-detect
# ---------------------------------------------------------------


class TestAutoDetect:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auto_detect_uploads_successfully(self, ctx, tmp_path):
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")
        (d / "global-config.yaml").write_text("b")

        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=Path(str(d)),
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration._zip_and_upload",
                    new_callable=AsyncMock,
                ) as mock_upload:
                    mock_upload.return_value = {"success": True}
                    result = await tool_put_lza_configuration(ctx)
                    assert result["success"] is True


# ---------------------------------------------------------------
# Direct upload via S3UploadUtils
# ---------------------------------------------------------------


class TestDirectUpload:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_with_config_path(self, ctx):
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=None,
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3UploadUtils"
                ) as mock_cls:
                    mock_inst = MagicMock()

                    async def mock_upload(*a, **kw):
                        return {"success": True}

                    mock_inst.upload_configuration = Mock(side_effect=mock_upload)
                    mock_cls.return_value = mock_inst

                    result = await tool_put_lza_configuration(
                        ctx, config_path="./my-config"
                    )
                    assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_config_path_no_detected(self, ctx):
        """No config_path and no detected config → falls through to S3UploadUtils."""
        with _patch_identity():
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_lza_configuration.get_extracted_lza_config_path",
                return_value=None,
            ):
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.S3UploadUtils"
                ) as mock_cls:
                    mock_inst = MagicMock()

                    async def mock_upload(*a, **kw):
                        return {"success": True}

                    mock_inst.upload_configuration = Mock(side_effect=mock_upload)
                    mock_cls.return_value = mock_inst

                    result = await tool_put_lza_configuration(ctx)
                    assert result["success"] is True
                    info_msgs = [str(c) for c in ctx.info.call_args_list]
                    assert any("Discovering" in m for m in info_msgs)


# ---------------------------------------------------------------
# Unexpected exception
# ---------------------------------------------------------------


class TestUnexpectedError:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_exception_caught(self, ctx):
        with _patch_identity() as mock_id:
            mock_id.side_effect = RuntimeError("boom")
            result = await tool_put_lza_configuration(ctx)
            assert result["success"] is False
            assert "boom" in result["error"]


# ---------------------------------------------------------------
# _zip_and_upload finally block cleanup failure
# ---------------------------------------------------------------


class TestZipCleanupFailure:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_temp_zip_remove_failure_non_fatal(self, ctx, tmp_path):
        """If os.remove fails on the temp zip in finally, it should not crash."""
        d = tmp_path / "cfg"
        d.mkdir()
        (d / "accounts-config.yaml").write_text("a")

        location = ConfigS3Location(
            bucket_name="b",
            object_key="k",
            account_id=ACCOUNT,
            region=REGION,
            qualifier=None,
        )

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
                result = await _zip_and_upload(ctx, str(d), location)
                assert result["success"] is True
