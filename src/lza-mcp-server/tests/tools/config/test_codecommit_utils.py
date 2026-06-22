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

"""Unit tests for codecommit_utils module."""

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.codecommit_utils import (
    _get_codecommit_client,
    _normalise_repo_path,
    list_all_files,
    get_blob_content,
    fetch_all_files,
    get_branch_tip_commit,
    commit_files,
)


def _client_error(code: str, message: str = "error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "operation")


@pytest.fixture
def mock_cc_client():
    with patch(
        "awslabs.lza_mcp_server.tools.config.codecommit_utils._get_codecommit_client"
    ) as mock_factory:
        client = MagicMock()
        mock_factory.return_value = client
        yield client


# ---------------------------------------------------------------------------
# _get_codecommit_client
# ---------------------------------------------------------------------------


class TestGetCodeCommitClient:
    def test_returns_client(self):
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client

        with patch(
            "awslabs.lza_mcp_server.tools.config.codecommit_utils.get_aws_session",
            return_value=mock_session,
        ):
            result = _get_codecommit_client()

        mock_session.client.assert_called_once()
        assert result is mock_client


# ---------------------------------------------------------------------------
# list_all_files
# ---------------------------------------------------------------------------


class TestListAllFiles:
    def test_flat_repo_no_subfolders(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {
            "files": [
                {"absolutePath": "accounts-config.yaml", "blobId": "blob1"},
                {"absolutePath": "network-config.yaml", "blobId": "blob2"},
            ],
            "subFolders": [],
        }

        result = list_all_files("my-repo", "main")

        assert result == [
            ("accounts-config.yaml", "blob1"),
            ("network-config.yaml", "blob2"),
        ]
        mock_cc_client.get_folder.assert_called_once_with(
            repositoryName="my-repo",
            commitSpecifier="main",
            folderPath="",
        )

    def test_nested_subfolders(self, mock_cc_client):
        # Root returns one file + one subfolder
        # Subfolder returns one file, no more subfolders
        mock_cc_client.get_folder.side_effect = [
            {
                "files": [{"absolutePath": "root.yaml", "blobId": "b0"}],
                "subFolders": [{"absolutePath": "customizations"}],
            },
            {
                "files": [
                    {"absolutePath": "customizations/config.yaml", "blobId": "b1"}
                ],
                "subFolders": [],
            },
        ]

        result = list_all_files("my-repo", "main")

        assert ("root.yaml", "b0") in result
        assert ("customizations/config.yaml", "b1") in result
        assert len(result) == 2

    def test_deeply_nested(self, mock_cc_client):
        mock_cc_client.get_folder.side_effect = [
            {
                "files": [],
                "subFolders": [{"absolutePath": "a"}],
            },
            {
                "files": [],
                "subFolders": [{"absolutePath": "a/b"}],
            },
            {
                "files": [{"absolutePath": "a/b/deep.yaml", "blobId": "bdeep"}],
                "subFolders": [],
            },
        ]

        result = list_all_files("my-repo", "main")

        assert result == [("a/b/deep.yaml", "bdeep")]

    def test_empty_repo(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {"files": [], "subFolders": []}

        result = list_all_files("my-repo", "main")

        assert result == []

    def test_custom_folder_path(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {
            "files": [{"absolutePath": "sub/file.yaml", "blobId": "bx"}],
            "subFolders": [],
        }

        result = list_all_files("my-repo", "main", folder_path="sub")

        mock_cc_client.get_folder.assert_called_once_with(
            repositoryName="my-repo",
            commitSpecifier="main",
            folderPath="sub",
        )
        assert result == [("sub/file.yaml", "bx")]

    def test_propagates_client_error(self, mock_cc_client):
        mock_cc_client.get_folder.side_effect = _client_error(
            "RepositoryDoesNotExistException"
        )

        with pytest.raises(ClientError):
            list_all_files("missing-repo", "main")

    def test_multiple_subfolders_at_same_level(self, mock_cc_client):
        mock_cc_client.get_folder.side_effect = [
            {
                "files": [{"absolutePath": "root.yaml", "blobId": "b0"}],
                "subFolders": [
                    {"absolutePath": "dir-a"},
                    {"absolutePath": "dir-b"},
                ],
            },
            {
                "files": [{"absolutePath": "dir-a/a.yaml", "blobId": "ba"}],
                "subFolders": [],
            },
            {
                "files": [{"absolutePath": "dir-b/b.yaml", "blobId": "bb"}],
                "subFolders": [],
            },
        ]

        result = list_all_files("my-repo", "main")

        paths = [r[0] for r in result]
        assert "root.yaml" in paths
        assert "dir-a/a.yaml" in paths
        assert "dir-b/b.yaml" in paths
        assert len(result) == 3


# ---------------------------------------------------------------------------
# get_blob_content
# ---------------------------------------------------------------------------


class TestGetBlobContent:
    def test_returns_bytes(self, mock_cc_client):
        mock_cc_client.get_blob.return_value = {"content": b"hello: world\n"}

        result = get_blob_content("my-repo", "abc123")

        assert result == b"hello: world\n"
        mock_cc_client.get_blob.assert_called_once_with(
            repositoryName="my-repo",
            blobId="abc123",
        )

    def test_propagates_client_error(self, mock_cc_client):
        mock_cc_client.get_blob.side_effect = _client_error(
            "BlobIdDoesNotExistException"
        )

        with pytest.raises(ClientError):
            get_blob_content("my-repo", "deadbeef")


# ---------------------------------------------------------------------------
# fetch_all_files
# ---------------------------------------------------------------------------


class TestFetchAllFiles:
    def test_combines_list_and_blob(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {
            "files": [
                {"absolutePath": "accounts-config.yaml", "blobId": "b1"},
                {"absolutePath": "network-config.yaml", "blobId": "b2"},
            ],
            "subFolders": [],
        }
        mock_cc_client.get_blob.side_effect = [
            {"content": b"accounts content"},
            {"content": b"network content"},
        ]

        result = fetch_all_files("my-repo", "main")

        assert result["accounts-config.yaml"] == b"accounts content"
        assert result["network-config.yaml"] == b"network content"
        assert len(result) == 2

    def test_empty_repo_returns_empty_dict(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {"files": [], "subFolders": []}

        result = fetch_all_files("my-repo", "main")

        assert result == {}
        mock_cc_client.get_blob.assert_not_called()

    def test_propagates_get_folder_error(self, mock_cc_client):
        mock_cc_client.get_folder.side_effect = _client_error(
            "RepositoryDoesNotExistException"
        )

        with pytest.raises(ClientError):
            fetch_all_files("missing-repo", "main")

    def test_propagates_get_blob_error(self, mock_cc_client):
        mock_cc_client.get_folder.return_value = {
            "files": [{"absolutePath": "file.yaml", "blobId": "b1"}],
            "subFolders": [],
        }
        mock_cc_client.get_blob.side_effect = _client_error(
            "BlobIdDoesNotExistException"
        )

        with pytest.raises(ClientError):
            fetch_all_files("my-repo", "main")


# ---------------------------------------------------------------------------
# get_branch_tip_commit
# ---------------------------------------------------------------------------


class TestGetBranchTipCommit:
    def test_returns_commit_id(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {
            "branch": {"commitId": "abc123def456"}
        }

        result = get_branch_tip_commit("my-repo", "main")

        assert result == "abc123def456"
        mock_cc_client.get_branch.assert_called_once_with(
            repositoryName="my-repo",
            branchName="main",
        )

    def test_returns_none_for_nonexistent_branch(self, mock_cc_client):
        mock_cc_client.get_branch.side_effect = _client_error(
            "BranchDoesNotExistException"
        )

        result = get_branch_tip_commit("my-repo", "nonexistent")

        assert result is None

    def test_propagates_other_client_errors(self, mock_cc_client):
        mock_cc_client.get_branch.side_effect = _client_error(
            "RepositoryDoesNotExistException"
        )

        with pytest.raises(ClientError):
            get_branch_tip_commit("missing-repo", "main")


# ---------------------------------------------------------------------------
# commit_files
# ---------------------------------------------------------------------------


class TestCommitFiles:
    def test_commit_with_parent(self, mock_cc_client):
        # get_branch returns a parent commit
        mock_cc_client.get_branch.return_value = {
            "branch": {"commitId": "parent-commit-id"}
        }
        mock_cc_client.create_commit.return_value = {
            "commitId": "new-commit-id",
            "treeId": "new-tree-id",
        }

        result = commit_files(
            repository_name="my-repo",
            branch="main",
            files={"accounts-config.yaml": b"content"},
            commit_message="Update LZA config",
        )

        assert result == {"commitId": "new-commit-id", "treeId": "new-tree-id"}

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert call_kwargs["repositoryName"] == "my-repo"
        assert call_kwargs["branchName"] == "main"
        assert call_kwargs["commitMessage"] == "Update LZA config"
        assert call_kwargs["parentCommitId"] == "parent-commit-id"
        assert len(call_kwargs["putFiles"]) == 1
        assert call_kwargs["putFiles"][0]["filePath"] == "accounts-config.yaml"
        assert call_kwargs["putFiles"][0]["fileContent"] == b"content"
        assert call_kwargs["putFiles"][0]["fileMode"] == "NORMAL"

    def test_commit_without_parent(self, mock_cc_client):
        # Branch doesn't exist yet — no parent commit
        mock_cc_client.get_branch.side_effect = _client_error(
            "BranchDoesNotExistException"
        )
        mock_cc_client.create_commit.return_value = {
            "commitId": "first-commit",
            "treeId": "first-tree",
        }

        result = commit_files(
            repository_name="my-repo",
            branch="main",
            files={"file.yaml": b"data"},
            commit_message="Initial commit",
        )

        assert result["commitId"] == "first-commit"
        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert "parentCommitId" not in call_kwargs

    def test_normalises_windows_paths(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {
            "commitId": "c1",
            "treeId": "t1",
        }

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"sub\\file.yaml": b"data"},
            commit_message="test",
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert call_kwargs["putFiles"][0]["filePath"] == "sub/file.yaml"

    def test_strips_leading_slash(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"/leading/slash.yaml": b"data"},
            commit_message="test",
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert call_kwargs["putFiles"][0]["filePath"] == "leading/slash.yaml"

    def test_multiple_files(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        files = {
            "accounts-config.yaml": b"accounts",
            "network-config.yaml": b"network",
            "organization-config.yaml": b"org",
        }

        commit_files(
            repository_name="my-repo",
            branch="main",
            files=files,
            commit_message="Update all",
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert len(call_kwargs["putFiles"]) == 3

    def test_custom_author(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"f.yaml": b"data"},
            commit_message="test",
            author_name="Custom Author",
            author_email="custom@example.com",
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert call_kwargs["authorName"] == "Custom Author"
        assert call_kwargs["email"] == "custom@example.com"

    def test_propagates_create_commit_error(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.side_effect = _client_error(
            "ParentCommitIdOutdatedException"
        )

        with pytest.raises(ClientError):
            commit_files(
                repository_name="my-repo",
                branch="main",
                files={"f.yaml": b"data"},
                commit_message="test",
            )


# ---------------------------------------------------------------------------
# _normalise_repo_path — path traversal validation
# ---------------------------------------------------------------------------


class TestNormaliseRepoPath:
    def test_strips_leading_slash(self):
        assert _normalise_repo_path("/a/b.yaml") == "a/b.yaml"

    def test_converts_windows_separators(self):
        assert _normalise_repo_path("sub\\file.yaml") == "sub/file.yaml"

    def test_allows_dotted_names(self):
        # Legitimate names that merely contain dots must not be rejected.
        assert _normalise_repo_path("abc..def/file.yaml") == "abc..def/file.yaml"
        assert _normalise_repo_path("config.v2.yaml") == "config.v2.yaml"

    def test_rejects_parent_traversal_component(self):
        with pytest.raises(ValueError):
            _normalise_repo_path("a/../b.yaml")

    def test_rejects_leading_parent_traversal(self):
        with pytest.raises(ValueError):
            _normalise_repo_path("../escape.yaml")

    def test_rejects_current_dir_component(self):
        with pytest.raises(ValueError):
            _normalise_repo_path("a/./b.yaml")

    def test_rejects_empty_component_from_double_slash(self):
        with pytest.raises(ValueError):
            _normalise_repo_path("a//b.yaml")


# ---------------------------------------------------------------------------
# commit_files — deleteFiles support
# ---------------------------------------------------------------------------


class TestCommitFilesDeletions:
    def test_delete_files_included_in_create_commit(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"keep.yaml": b"data"},
            commit_message="test",
            delete_files=["stale.yaml", "old/nested.yaml"],
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        deleted_paths = [entry["filePath"] for entry in call_kwargs["deleteFiles"]]
        assert deleted_paths == ["stale.yaml", "old/nested.yaml"]

    def test_no_delete_files_key_when_none(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"keep.yaml": b"data"},
            commit_message="test",
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert "deleteFiles" not in call_kwargs

    def test_no_delete_files_key_when_empty_list(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}
        mock_cc_client.create_commit.return_value = {"commitId": "c1", "treeId": "t1"}

        commit_files(
            repository_name="my-repo",
            branch="main",
            files={"keep.yaml": b"data"},
            commit_message="test",
            delete_files=[],
        )

        call_kwargs = mock_cc_client.create_commit.call_args[1]
        assert "deleteFiles" not in call_kwargs

    def test_rejects_traversal_in_delete_path(self, mock_cc_client):
        mock_cc_client.get_branch.return_value = {"branch": {"commitId": "p1"}}

        with pytest.raises(ValueError):
            commit_files(
                repository_name="my-repo",
                branch="main",
                files={"keep.yaml": b"data"},
                commit_message="test",
                delete_files=["../escape.yaml"],
            )
