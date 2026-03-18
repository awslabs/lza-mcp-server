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

"""Tests for getLzaConfiguration tool — targeting ~100 % coverage."""

import os
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.get_lza_configuration import (
    LzaConfigRetrieval,
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
def retrieval():
    return LzaConfigRetrieval()


def _make_config_zip(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("accounts-config.yaml", "mandatoryAccounts: []")
        zf.writestr("global-config.yaml", "homeRegion: us-east-1")
        zf.writestr("sub/nested.yaml", "nested: true")


def _patch_identity():
    return patch(
        "awslabs.lza_mcp_server.tools.config.get_lza_configuration.get_caller_identity",
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
                assert f"aws-accelerator-config-{ACCOUNT}-{REGION}" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_bucket_not_found(self, ctx, retrieval):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                result = await retrieval.get_configuration(ctx, qualifier="env1")
                assert result["success"] is False
                assert "env1-config-" in result["error"]


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
    async def test_invalid_zip_file(self, ctx, retrieval, tmp_path):
        """Downloaded file is not a valid ZIP."""
        not_a_zip = tmp_path / "bad.zip"
        not_a_zip.write_text("this is not a zip")

        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: (
                    not_a_zip.rename(p) if not os.path.exists(p) else None
                )
            )

            # Write bad content to the temp file created by mkstemp
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
    async def test_standard_success(self, ctx, retrieval, tmp_path):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                base = str(tmp_path / "lza")
                with patch.dict(
                    os.environ,
                    {"LZA_CONFIG_BASE_PATH": base, "LZA_CONFIG_HOST_PATH": "/host"},
                ):
                    result = await retrieval.get_configuration(ctx)
                    assert result["success"] is True
                    assert result["qualifier"] is None
                    assert result["object_key"] == "zipped/aws-accelerator-config.zip"
                    assert result["file_count"] >= 2
                    assert result["directory_count"] >= 1
                    assert "sub" in result["root_folders"]
                    assert "llm_instructions" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_qualifier_success(self, ctx, retrieval, tmp_path):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                base = str(tmp_path / "lza")
                with patch.dict(
                    os.environ,
                    {"LZA_CONFIG_BASE_PATH": base, "LZA_CONFIG_HOST_PATH": "/host"},
                ):
                    result = await retrieval.get_configuration(ctx, qualifier="env1")
                    assert result["success"] is True
                    assert result["qualifier"] == "env1"
                    assert result["object_key"] == "lza/aws-accelerator-config.zip"
                    assert "env1" in result["llm_instructions"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_bucket_override_success(self, ctx, retrieval, tmp_path):
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                base = str(tmp_path / "lza")
                with patch.dict(
                    os.environ,
                    {"LZA_CONFIG_BASE_PATH": base, "LZA_CONFIG_HOST_PATH": "/host"},
                ):
                    result = await retrieval.get_configuration(
                        ctx, bucket_name="custom-bucket"
                    )
                    assert result["success"] is True
                    assert result["bucket_name"] == "custom-bucket"


# ---------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------


class TestCleanup:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_previous_directory(self, ctx, retrieval, tmp_path):
        """Previous temp directory should be removed on next call."""
        prev_dir = tmp_path / "old-config"
        prev_dir.mkdir()
        (prev_dir / "file.txt").write_text("old")
        retrieval._last_temp_directory = str(prev_dir)

        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                await retrieval.get_configuration(ctx)
                assert not prev_dir.exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_failure_is_non_fatal(self, ctx, retrieval):
        """Cleanup failure should not prevent the operation."""
        retrieval._last_temp_directory = "/nonexistent/path/that/does/not/exist"

        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=False)
            with _patch_identity():
                # Should not raise
                result = await retrieval.get_configuration(ctx)
                assert result["success"] is False  # fails at bucket check, not cleanup


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
# Metadata extraction
# ---------------------------------------------------------------


class TestMetadata:
    @pytest.mark.unit
    def test_metadata_with_subdirectories(self, retrieval, tmp_path):
        zip_path = tmp_path / "test.zip"
        extract = tmp_path / "extract"
        extract.mkdir()
        (extract / "file1.yaml").write_text("a")
        sub = extract / "policies"
        sub.mkdir()
        (sub / "policy.json").write_text("{}")
        deep = sub / "nested"
        deep.mkdir()

        _make_config_zip(str(zip_path))

        meta = retrieval._extract_metadata(str(zip_path), str(extract))
        assert meta["file_count"] == 2
        assert meta["directory_count"] == 2
        assert "policies" in meta["root_folders"]
        assert "file1.yaml" in meta["root_files"]
        dirs = meta["structure"]["root"]["directories"]
        assert "policies" in dirs
        assert "policy.json" in dirs["policies"]["files"]
        assert "nested" in dirs["policies"]["directories"]

    @pytest.mark.unit
    def test_metadata_exception_returns_defaults(self, retrieval):
        """If metadata extraction fails, defaults are returned."""
        meta = retrieval._extract_metadata("/nonexistent.zip", "/nonexistent")
        assert meta["file_count"] == 0
        assert meta["zip_size"] == 0


# ---------------------------------------------------------------
# Cleanup exception path
# ---------------------------------------------------------------


class TestCleanupException:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cleanup_rmtree_failure_logged(self, ctx, retrieval, tmp_path):
        """When shutil.rmtree fails during cleanup, a warning is logged."""
        prev_dir = tmp_path / "old-config"
        prev_dir.mkdir()
        retrieval._last_temp_directory = str(prev_dir)

        with patch("shutil.rmtree", side_effect=PermissionError("denied")):
            with patch.object(retrieval, "s3_manager") as m:
                m.verify_bucket_exists = AsyncMock(return_value=False)
                with _patch_identity():
                    result = await retrieval.get_configuration(ctx)
                    # Should not crash — just warn and continue
                    assert result["success"] is False  # fails at bucket check


# ---------------------------------------------------------------
# Existing extract path gets removed
# ---------------------------------------------------------------


class TestExistingExtractPath:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_existing_extract_dir_removed(self, ctx, retrieval, tmp_path):
        """If retrieved-config already exists, it should be removed before extraction."""
        base = tmp_path / "lza"
        existing = base / "retrieved-config"
        existing.mkdir(parents=True)
        (existing / "stale.yaml").write_text("old")

        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                with patch.dict(
                    os.environ,
                    {
                        "LZA_CONFIG_BASE_PATH": str(base),
                        "LZA_CONFIG_HOST_PATH": "/host",
                    },
                ):
                    result = await retrieval.get_configuration(ctx)
                    assert result["success"] is True
                    # stale.yaml should be gone
                    assert not (existing / "stale.yaml").exists()
                    # new files should be present
                    assert (existing / "accounts-config.yaml").exists()


# ---------------------------------------------------------------
# Finally block temp zip cleanup failure
# ---------------------------------------------------------------


class TestTempZipCleanupFailure:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_temp_zip_remove_failure_non_fatal(self, ctx, retrieval, tmp_path):
        """If os.remove fails on the temp zip in finally, it should not crash."""
        with patch.object(retrieval, "s3_manager") as m:
            m.verify_bucket_exists = AsyncMock(return_value=True)
            m._get_s3_client.return_value.download_file = MagicMock(
                side_effect=lambda b, k, p: _make_config_zip(p)
            )
            with _patch_identity():
                base = str(tmp_path / "lza")
                with patch.dict(
                    os.environ,
                    {"LZA_CONFIG_BASE_PATH": base, "LZA_CONFIG_HOST_PATH": "/host"},
                ):
                    # Patch os.remove to fail for .zip files
                    original_remove = os.remove

                    def failing_remove(path):
                        if path.endswith(".zip"):
                            raise PermissionError("cannot delete zip")
                        return original_remove(path)

                    with patch(
                        "awslabs.lza_mcp_server.tools.config.get_lza_configuration.os.remove",
                        side_effect=failing_remove,
                    ):
                        result = await retrieval.get_configuration(ctx)
                        # Should still succeed — cleanup failure is non-fatal
                        assert result["success"] is True
