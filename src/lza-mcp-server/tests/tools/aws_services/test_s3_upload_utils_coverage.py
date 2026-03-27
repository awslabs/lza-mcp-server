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

"""Coverage gap tests for S3UploadUtils."""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils import S3UploadUtils
from awslabs.lza_mcp_server.orchestration.core.s3_upload_error import S3UploadError


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _aws_context():
    return {"connected": True, "account_id": "123456789012", "region": "us-east-1"}


# ---------------------------------------------------------------------------
# ensure_aws_connectivity — cache hit and failure paths
# ---------------------------------------------------------------------------


class TestEnsureAwsConnectivity:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_cached_result_on_second_call(self, mock_ctx):
        """Second call returns cached context without re-checking AWS."""
        utils = S3UploadUtils()
        utils._aws_connectivity_verified = True
        utils._aws_context = _aws_context()

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
        ) as mock_check:
            result = await utils.ensure_aws_connectivity(mock_ctx)
            mock_check.assert_not_called()
            assert result == _aws_context()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_raises_when_connectivity_fails(self, mock_ctx):
        """Raises Exception when AWS connectivity check returns connected=False."""
        utils = S3UploadUtils()

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity",
            return_value={"connected": False, "message": "No credentials"},
        ):
            with pytest.raises(Exception, match="AWS connectivity failed"):
                await utils.ensure_aws_connectivity(mock_ctx)


# ---------------------------------------------------------------------------
# _discover_and_select_configuration — error paths
# ---------------------------------------------------------------------------


class TestDiscoverAndSelectConfiguration:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_s3_upload_error_from_validate_path(self, mock_ctx):
        """S3UploadError from validate_configuration_path is returned as dict."""
        utils = S3UploadUtils()
        err = S3UploadError(
            message="bad path",
            category="CONFIGURATION",
            error_code="INVALID_PATH",
        )
        utils.config_manager.validate_configuration_path = AsyncMock(side_effect=err)

        result = await utils._discover_and_select_configuration(mock_ctx, "/bad/path")
        assert result["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_configs_discovered_returns_error(self, mock_ctx):
        """Empty discovery result returns structured error."""
        utils = S3UploadUtils()
        utils.config_manager.validate_configuration_path = AsyncMock(return_value=None)
        utils.config_manager.discover_configurations = AsyncMock(return_value=[])

        result = await utils._discover_and_select_configuration(mock_ctx)
        assert result["success"] is False
        assert "No valid LZA configurations" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_s3_upload_error_from_discover(self, mock_ctx):
        """S3UploadError from discover_configurations is returned as dict."""
        utils = S3UploadUtils()
        err = S3UploadError(
            message="discover failed",
            category="INTEGRATION",
            error_code="DISCOVERY_ERROR",
        )
        utils.config_manager.discover_configurations = AsyncMock(side_effect=err)

        result = await utils._discover_and_select_configuration(mock_ctx)
        assert result["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_exception_from_discover(self, mock_ctx):
        """Unexpected exception from discover_configurations returns structured error."""
        utils = S3UploadUtils()
        utils.config_manager.discover_configurations = AsyncMock(
            side_effect=RuntimeError("disk full")
        )

        result = await utils._discover_and_select_configuration(mock_ctx)
        assert result["success"] is False
        assert "disk full" in result["error"]


# ---------------------------------------------------------------------------
# upload_configuration — failure paths
# ---------------------------------------------------------------------------


class TestUploadConfigurationFailures:
    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_config_discovery_failure_propagated(self, mock_check, mock_ctx):
        """Config discovery failure is returned with aws_context attached."""
        mock_check.return_value = _aws_context()
        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": False, "error": "no configs found"}
        )

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False
        assert "aws_context" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_invalid_custom_bucket_name_rejected(self, mock_check, mock_ctx):
        """Invalid custom bucket name returns validation error."""
        mock_check.return_value = _aws_context()
        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        utils.s3_manager.validate_custom_bucket_name = AsyncMock(
            return_value={
                "valid": False,
                "error": "bucket name too short",
                "error_type": "INVALID_BUCKET",
            }
        )

        result = await utils.upload_configuration(mock_ctx, bucket_name="ab")
        assert result["success"] is False
        assert "bucket name too short" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_bucket_not_found_returns_prompt(self, mock_check, mock_ctx):
        """Non-existent bucket returns user prompt for alternative."""
        mock_check.return_value = _aws_context()
        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        utils.s3_manager.determine_bucket_name = AsyncMock(
            return_value="missing-bucket"
        )
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=False)
        utils.s3_manager.prompt_for_custom_bucket_name = AsyncMock(
            return_value={"prompt": "Enter bucket name"}
        )

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False
        assert "does not exist" in result["error"]
        assert "user_prompt" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile"
    )
    async def test_zip_creation_failure_returned(
        self, mock_tempfile, mock_check, mock_create_zip, mock_cleanup, mock_ctx
    ):
        """ZIP creation failure is returned as error."""
        mock_check.return_value = _aws_context()
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        mock_create_zip.return_value = {"success": False, "error": "zip failed"}
        mock_cleanup.return_value = {"success": True}

        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value="test-bucket")
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False
        assert "zip failed" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile"
    )
    async def test_s3_upload_failure_returned(
        self, mock_tempfile, mock_check, mock_create_zip, mock_cleanup, mock_ctx
    ):
        """S3 upload failure is returned as error."""
        mock_check.return_value = _aws_context()
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        mock_create_zip.return_value = {"success": True, "file_size": 512}
        mock_cleanup.return_value = {"success": True}

        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value="test-bucket")
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        utils.s3_manager.upload_zip_file = AsyncMock(
            return_value={
                "success": False,
                "error": "access denied",
                "error_code": "ACCESS_DENIED",
            }
        )

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False
        assert "access denied" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile"
    )
    async def test_cleanup_failure_logged_but_not_fatal(
        self, mock_tempfile, mock_check, mock_create_zip, mock_cleanup, mock_ctx
    ):
        """Cleanup failure is logged but doesn't affect the upload result."""
        mock_check.return_value = _aws_context()
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        mock_create_zip.return_value = {"success": True, "file_size": 512}
        mock_cleanup.return_value = {"success": False, "error": "cleanup failed"}

        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        utils.s3_manager.determine_bucket_name = AsyncMock(return_value="test-bucket")
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        utils.s3_manager.upload_zip_file = AsyncMock(
            return_value={"success": True, "file_size": 512}
        )

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is True
        mock_ctx.error.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_s3_upload_error_exception_handled(self, mock_check, mock_ctx):
        """S3UploadError exception is caught and returned as dict."""
        mock_check.return_value = _aws_context()
        utils = S3UploadUtils()
        err = S3UploadError(
            message="structured error",
            category="INTEGRATION",
            error_code="S3_ERROR",
        )
        utils._discover_and_select_configuration = AsyncMock(side_effect=err)

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    async def test_unexpected_exception_handled(self, mock_check, mock_ctx):
        """Unexpected exception is caught and returned as structured error."""
        mock_check.return_value = _aws_context()
        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            side_effect=RuntimeError("unexpected boom")
        )

        result = await utils.upload_configuration(mock_ctx)
        assert result["success"] is False
        assert "unexpected boom" in result["error"]


# ---------------------------------------------------------------------------
# _discover_and_select_configuration — remaining branch coverage
# ---------------------------------------------------------------------------


class TestDiscoverAndSelectConfigurationBranches:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_config_path_returns_success(self, mock_ctx):
        """validate_configuration_path returns True → success dict returned."""
        utils = S3UploadUtils()
        utils.config_manager.validate_configuration_path = AsyncMock(return_value=True)

        result = await utils._discover_and_select_configuration(
            mock_ctx, "/valid/config"
        )
        assert result["success"] is True
        assert result["selected_config"] == "/valid/config"
        assert result["discovery_method"] == "provided_path"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_validate_path_returns_falsy_falls_through_to_discover(
        self, mock_ctx
    ):
        """validate_configuration_path returns falsy → falls through to workspace discovery."""
        utils = S3UploadUtils()
        utils.config_manager.validate_configuration_path = AsyncMock(return_value=False)

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.select_configuration",
            new_callable=AsyncMock,
            return_value="/discovered/config",
        ):
            utils.config_manager.discover_configurations = AsyncMock(
                return_value=["/discovered/config"]
            )
            result = await utils._discover_and_select_configuration(
                mock_ctx, "/some/path"
            )

        assert result["success"] is True
        assert result["selected_config"] == "/discovered/config"
        assert result["discovery_method"] == "workspace_search"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_workspace_discovery_with_select(self, mock_ctx):
        """Successful workspace discovery calls select_configuration and returns result."""
        utils = S3UploadUtils()
        utils.config_manager.discover_configurations = AsyncMock(
            return_value=["/config/a", "/config/b"]
        )

        with patch(
            "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.select_configuration",
            new_callable=AsyncMock,
            return_value="/config/a",
        ):
            result = await utils._discover_and_select_configuration(mock_ctx)

        assert result["success"] is True
        assert result["selected_config"] == "/config/a"
        assert result["discovery_method"] == "workspace_search"
        assert len(result["discovered_configs"]) == 2


class TestCustomBucketValidationPassBranch:
    @pytest.mark.asyncio
    @pytest.mark.unit
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.cleanup_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.create_configuration_zip"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tool_check_aws_connectivity"
    )
    @patch(
        "awslabs.lza_mcp_server.tools.aws_services.s3_upload_utils.tempfile.NamedTemporaryFile"
    )
    async def test_custom_bucket_valid_continues_to_verify(
        self, mock_tempfile, mock_check, mock_create_zip, mock_cleanup, mock_ctx
    ):
        """Custom bucket passes validation → continues to verify_bucket_exists (branch 246->258)."""
        mock_check.return_value = _aws_context()
        mock_temp = Mock()
        mock_temp.name = "/tmp/config.zip"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        mock_create_zip.return_value = {"success": True, "file_size": 512}
        mock_cleanup.return_value = {"success": True}

        utils = S3UploadUtils()
        utils._discover_and_select_configuration = AsyncMock(
            return_value={"success": True, "selected_config": "/config"}
        )
        # Validation passes (valid=True)
        utils.s3_manager.validate_custom_bucket_name = AsyncMock(
            return_value={"valid": True}
        )
        utils.s3_manager.verify_bucket_exists = AsyncMock(return_value=True)
        utils.s3_manager.upload_zip_file = AsyncMock(
            return_value={"success": True, "file_size": 512}
        )

        result = await utils.upload_configuration(mock_ctx, bucket_name="valid-bucket")
        assert result["success"] is True
        assert result["bucket_name"] == "valid-bucket"
