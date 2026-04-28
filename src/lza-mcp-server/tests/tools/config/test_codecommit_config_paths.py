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

"""Tests for the CodeCommit paths in getLzaConfiguration and putLzaConfiguration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.get_lza_configuration import LzaConfigRetrieval
from awslabs.lza_mcp_server.tools.config.put_lza_configuration import (
    tool_put_lza_configuration,
)
from awslabs.lza_mcp_server.tools.config.config_codecommit_resolver import (
    ConfigCodeCommitLocation,
)
from awslabs.lza_mcp_server.utils.workspace_manager import WorkspaceNotFoundError


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "error"}}, "op")


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
    mgr.list_files = MagicMock(
        return_value=["accounts-config.yaml", "network-config.yaml"]
    )
    mgr.write_file = MagicMock()
    mgr.read_file = MagicMock(return_value=b"content")
    mgr.create_folder = MagicMock()
    return mgr


@pytest.fixture
def retrieval(mock_ws_manager):
    return LzaConfigRetrieval(mock_ws_manager)


_CC_LOCATION = ConfigCodeCommitLocation(
    repository_name="lza-config-repo",
    branch="main",
    qualifier=None,
)

_CC_LOCATION_WITH_QUALIFIER = ConfigCodeCommitLocation(
    repository_name="lza-config-repo",
    branch="main",
    qualifier="my-qualifier",
)

IDENTITY = {
    "account_id": "123456789012",
    "user_arn": "arn:aws:iam::test",
    "region": "us-east-1",
}


def _patch_resolve_cc(location):
    return patch(
        "awslabs.lza_mcp_server.tools.config.get_lza_configuration.resolve_codecommit_location",
        return_value=location,
    )


def _patch_resolve_cc_put(location):
    return patch(
        "awslabs.lza_mcp_server.tools.config.put_lza_configuration.resolve_codecommit_location",
        return_value=location,
    )


def _patch_fetch(files):
    return patch(
        "awslabs.lza_mcp_server.tools.config.get_config_from_codecommit.fetch_all_files",
        return_value=files,
    )


def _patch_commit(result):
    return patch(
        "awslabs.lza_mcp_server.tools.config.put_config_to_codecommit.commit_files",
        return_value=result,
    )


def _patch_identity():
    return patch(
        "awslabs.lza_mcp_server.tools.config.put_config_to_s3.get_caller_identity",
        return_value=IDENTITY,
    )


# ===========================================================================
# getLzaConfiguration — CodeCommit path
# ===========================================================================


class TestGetLzaConfigurationCodeCommit:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_flat_files(self, ctx, retrieval, mock_ws_manager):
        files = {
            "accounts-config.yaml": b"accounts: []",
            "network-config.yaml": b"network: {}",
        }
        with _patch_resolve_cc(_CC_LOCATION), _patch_fetch(files):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo"
            )

        assert result["success"] is True
        assert result["config_source"] == "codecommit"
        assert result["repository_name"] == "lza-config-repo"
        assert result["branch"] == "main"
        assert result["file_count"] == 2
        assert "accounts-config.yaml" in result["root_files"]
        assert mock_ws_manager.write_file.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_with_nested_files(self, ctx, retrieval, mock_ws_manager):
        files = {
            "accounts-config.yaml": b"accounts: []",
            "customizations/config.yaml": b"custom: {}",
        }
        with _patch_resolve_cc(_CC_LOCATION), _patch_fetch(files):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo"
            )

        assert result["success"] is True
        assert "customizations" in result["root_folders"]
        assert "accounts-config.yaml" in result["root_files"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_with_path_prefix(self, ctx, retrieval, mock_ws_manager):
        files = {"accounts-config.yaml": b"accounts: []"}
        with _patch_resolve_cc(_CC_LOCATION), _patch_fetch(files):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo", path="lza"
            )

        assert result["success"] is True
        assert result["path"] == "lza"
        # File should be written under the path prefix
        call_args = mock_ws_manager.write_file.call_args[0]
        assert call_args[1].startswith("lza/")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_with_qualifier(self, ctx, retrieval):
        files = {"accounts-config.yaml": b"accounts: []"}
        with _patch_resolve_cc(_CC_LOCATION_WITH_QUALIFIER), _patch_fetch(files):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo", qualifier="my-qualifier"
            )

        assert result["success"] is True
        assert result["qualifier"] == "my-qualifier"
        assert "my-qualifier" in result["llm_instructions"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_llm_instructions_contain_repo_and_branch(self, ctx, retrieval):
        files = {"accounts-config.yaml": b"accounts: []"}
        with _patch_resolve_cc(_CC_LOCATION), _patch_fetch(files):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo"
            )

        assert "lza-config-repo" in result["llm_instructions"]
        assert "main" in result["llm_instructions"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_repository_returns_error(self, ctx, retrieval):
        with _patch_resolve_cc(_CC_LOCATION), _patch_fetch({}):
            result = await retrieval.get_configuration(
                ctx, repository_name="lza-config-repo"
            )

        assert result["success"] is False
        assert result["error_code"] == "EMPTY_REPOSITORY"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_repository_not_found(self, ctx, retrieval):
        with _patch_resolve_cc(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.get_config_from_codecommit.fetch_all_files",
                side_effect=_client_error("RepositoryDoesNotExistException"),
            ):
                result = await retrieval.get_configuration(
                    ctx, repository_name="missing-repo"
                )

        assert result["success"] is False
        assert result["error_code"] == "REPOSITORY_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_branch_not_found(self, ctx, retrieval):
        with _patch_resolve_cc(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.get_config_from_codecommit.fetch_all_files",
                side_effect=_client_error("BranchDoesNotExistException"),
            ):
                result = await retrieval.get_configuration(
                    ctx, repository_name="lza-config-repo", branch="nonexistent"
                )

        assert result["success"] is False
        assert result["error_code"] == "BRANCH_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_commit_does_not_exist(self, ctx, retrieval):
        with _patch_resolve_cc(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.get_config_from_codecommit.fetch_all_files",
                side_effect=_client_error("CommitDoesNotExistException"),
            ):
                result = await retrieval.get_configuration(
                    ctx, repository_name="lza-config-repo"
                )

        assert result["success"] is False
        assert result["error_code"] == "BRANCH_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_other_codecommit_error(self, ctx, retrieval):
        with _patch_resolve_cc(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.get_config_from_codecommit.fetch_all_files",
                side_effect=_client_error("AccessDeniedException"),
            ):
                result = await retrieval.get_configuration(
                    ctx, repository_name="lza-config-repo"
                )

        assert result["success"] is False
        assert "CodeCommit fetch failed" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_repository_name(self, ctx, retrieval):
        result = await retrieval.get_configuration(ctx, repository_name="a" * 101)
        assert result["success"] is False
        assert result["error_code"] == "INVALID_REPOSITORY_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_branch_name(self, ctx, retrieval):
        result = await retrieval.get_configuration(
            ctx, repository_name="my-repo", branch="a" * 257
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BRANCH_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_falls_back_to_s3_when_no_codecommit_source(self, ctx, retrieval):
        """When resolve_codecommit_location returns None, S3 path is used."""
        with patch(
            "awslabs.lza_mcp_server.tools.config.get_lza_configuration.resolve_codecommit_location",
            return_value=None,
        ):
            with patch.object(retrieval, "s3_manager") as m:
                m.verify_bucket_exists = AsyncMock(return_value=False)
                with patch(
                    "awslabs.lza_mcp_server.tools.config.get_config_from_s3.get_caller_identity",
                    return_value=IDENTITY,
                ):
                    result = await retrieval.get_configuration(ctx)

        # Should have gone to S3 path and failed on bucket not found
        assert result["success"] is False
        assert result["error_code"] == "BUCKET_NOT_FOUND"


# ===========================================================================
# putLzaConfiguration — CodeCommit path
# ===========================================================================


class TestPutLzaConfigurationCodeCommit:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"accounts: []"

        with (
            _patch_resolve_cc_put(_CC_LOCATION),
            _patch_commit({"commitId": "abc123", "treeId": "tree456"}),
        ):
            result = await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="",
                repository_name="lza-config-repo",
            )

        assert result["success"] is True
        assert result["config_source"] == "codecommit"
        assert result["commit_id"] == "abc123"
        assert result["tree_id"] == "tree456"
        assert result["repository_name"] == "lza-config-repo"
        assert result["branch"] == "main"
        assert result["file_count"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_with_qualifier(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"accounts: []"

        with (
            _patch_resolve_cc_put(_CC_LOCATION_WITH_QUALIFIER),
            _patch_commit({"commitId": "abc123", "treeId": "tree456"}),
        ):
            result = await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="",
                qualifier="my-qualifier",
                repository_name="lza-config-repo",
            )

        assert result["success"] is True
        assert result["qualifier"] == "my-qualifier"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_success_with_custom_commit_message(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"accounts: []"

        with (
            _patch_resolve_cc_put(_CC_LOCATION) as _,
            _patch_commit({"commitId": "abc123", "treeId": "tree456"}) as mock_commit,
        ):
            await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="",
                repository_name="lza-config-repo",
                commit_message="My custom message",
            )

        mock_commit.assert_called_once()
        call_kwargs = mock_commit.call_args[1]
        assert call_kwargs["commit_message"] == "My custom message"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_string_content_encoded_to_bytes(self, ctx, mock_ws_manager):
        """read_file returning str should be encoded to bytes before commit."""
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = "string content"  # str, not bytes

        with (
            _patch_resolve_cc_put(_CC_LOCATION) as _,
            _patch_commit({"commitId": "c1", "treeId": "t1"}) as mock_commit,
        ):
            result = await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="",
                repository_name="lza-config-repo",
            )

        assert result["success"] is True
        call_kwargs = mock_commit.call_args[1]
        file_content = call_kwargs["files"]["accounts-config.yaml"]
        assert isinstance(file_content, bytes)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_path_prefix_stripped_from_arcname(self, ctx, mock_ws_manager):
        """Files under a path prefix should be committed with relative paths."""
        mock_ws_manager.list_files.return_value = ["lza/accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"accounts: []"

        with (
            _patch_resolve_cc_put(_CC_LOCATION) as _,
            _patch_commit({"commitId": "c1", "treeId": "t1"}) as mock_commit,
        ):
            await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="lza",
                repository_name="lza-config-repo",
            )

        call_kwargs = mock_commit.call_args[1]
        assert "accounts-config.yaml" in call_kwargs["files"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_repository_not_found(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"content"

        with _patch_resolve_cc_put(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_config_to_codecommit.commit_files",
                side_effect=_client_error("RepositoryDoesNotExistException"),
            ):
                result = await tool_put_lza_configuration(
                    ctx,
                    mock_ws_manager,
                    workspace_id="ws-123",
                    path="",
                    repository_name="missing-repo",
                )

        assert result["success"] is False
        assert result["error_code"] == "REPOSITORY_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_branch_not_found(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"content"

        with _patch_resolve_cc_put(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_config_to_codecommit.commit_files",
                side_effect=_client_error("BranchDoesNotExistException"),
            ):
                result = await tool_put_lza_configuration(
                    ctx,
                    mock_ws_manager,
                    workspace_id="ws-123",
                    path="",
                    repository_name="lza-config-repo",
                    branch="nonexistent",
                )

        assert result["success"] is False
        assert result["error_code"] == "BranchDoesNotExistException"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_commit_conflict(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"content"

        with _patch_resolve_cc_put(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_config_to_codecommit.commit_files",
                side_effect=_client_error("ParentCommitIdOutdatedException"),
            ):
                result = await tool_put_lza_configuration(
                    ctx,
                    mock_ws_manager,
                    workspace_id="ws-123",
                    path="",
                    repository_name="lza-config-repo",
                )

        assert result["success"] is False
        assert result["error_code"] == "COMMIT_CONFLICT"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_other_codecommit_error(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"content"

        with _patch_resolve_cc_put(_CC_LOCATION):
            with patch(
                "awslabs.lza_mcp_server.tools.config.put_config_to_codecommit.commit_files",
                side_effect=_client_error("AccessDeniedException"),
            ):
                result = await tool_put_lza_configuration(
                    ctx,
                    mock_ws_manager,
                    workspace_id="ws-123",
                    path="",
                    repository_name="lza-config-repo",
                )

        assert result["success"] is False
        assert "CodeCommit commit failed" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_repository_name(self, ctx, mock_ws_manager):
        result = await tool_put_lza_configuration(
            ctx,
            mock_ws_manager,
            workspace_id="ws-123",
            path="",
            repository_name="a" * 101,
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_REPOSITORY_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_branch_name(self, ctx, mock_ws_manager):
        result = await tool_put_lza_configuration(
            ctx,
            mock_ws_manager,
            workspace_id="ws-123",
            path="",
            repository_name="my-repo",
            branch="a" * 257,
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_BRANCH_NAME"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_workspace_not_found(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.side_effect = WorkspaceNotFoundError("not found")

        result = await tool_put_lza_configuration(
            ctx,
            mock_ws_manager,
            workspace_id="ws-bad",
            path="",
            repository_name="my-repo",
        )
        assert result["success"] is False
        assert result["error_code"] == "WORKSPACE_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_workspace(self, ctx, mock_ws_manager):
        mock_ws_manager.list_files.return_value = []

        result = await tool_put_lza_configuration(
            ctx,
            mock_ws_manager,
            workspace_id="ws-123",
            path="",
            repository_name="my-repo",
        )
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONFIGURATION"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_falls_back_to_s3_when_no_codecommit_source(
        self, ctx, mock_ws_manager
    ):
        """When resolve_codecommit_location returns None, S3 path is used."""
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]

        with patch(
            "awslabs.lza_mcp_server.tools.config.put_lza_configuration.resolve_codecommit_location",
            return_value=None,
        ):
            with _patch_identity():
                with patch(
                    "awslabs.lza_mcp_server.tools.config.put_lza_configuration.put_config_to_s3",
                    new_callable=AsyncMock,
                    return_value={"success": True, "config_source": "s3"},
                ) as mock_s3:
                    result = await tool_put_lza_configuration(
                        ctx,
                        mock_ws_manager,
                        workspace_id="ws-123",
                        path="",
                    )

        assert result["config_source"] == "s3"
        mock_s3.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_root_path_normalised(self, ctx, mock_ws_manager):
        """Paths '/' and '.' should be normalised to empty string."""
        mock_ws_manager.list_files.return_value = ["accounts-config.yaml"]
        mock_ws_manager.read_file.return_value = b"content"

        with (
            _patch_resolve_cc_put(_CC_LOCATION),
            _patch_commit({"commitId": "c1", "treeId": "t1"}),
        ):
            result = await tool_put_lza_configuration(
                ctx,
                mock_ws_manager,
                workspace_id="ws-123",
                path="/",
                repository_name="lza-config-repo",
            )

        assert result["success"] is True
