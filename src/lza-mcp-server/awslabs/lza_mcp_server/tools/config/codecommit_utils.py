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

"""Low-level CodeCommit read/write helpers used by getLzaConfiguration and
putLzaConfiguration.

Read path  — recursive GetFolder walk + GetBlob per file:
  GetFolder returns the immediate children of a folder (files + subFolders).
  We walk the tree recursively, collecting (absolutePath, blobId) pairs, then
  fetch each blob's base64-encoded content with GetBlob and decode it.

  Note: GetFolder returns at most 1000 entries per call.  LZA configuration
  repositories are well within this limit in practice.

Write path — single CreateCommit with all workspace files:
  All files are sent in one CreateCommit call as putFiles entries.  Files that
  exist in the remote branch but are absent from the workspace are included as
  deleteFiles entries, ensuring deletions are tracked.  Git will only record a
  diff for files whose content actually changed, so the commit history remains
  clean regardless of how many files are included.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.aws_access import get_aws_session
from awslabs.lza_mcp_server.constants import DEFAULT_REGION
import os

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", DEFAULT_REGION)


def _get_codecommit_client():
    """Return a boto3 CodeCommit client for the configured region."""
    session = get_aws_session()
    return session.client("codecommit", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def list_all_files(
    repository_name: str,
    commit_specifier: str,
    folder_path: str = "",
) -> List[Tuple[str, str]]:
    """Recursively list all files in a CodeCommit repository folder.

    Uses GetFolder to walk the directory tree.  Each call returns the
    immediate children (files + subFolders) of the requested path.
    Recursion stops when there are no more subFolders.

    Args:
        repository_name: CodeCommit repository name.
        commit_specifier: Branch name, tag, or commit ID (e.g. "main").
        folder_path: Starting folder path.  Empty string means the root.

    Returns:
        List of (absolute_path, blob_id) tuples for every file found.

    Raises:
        ClientError: If the CodeCommit API call fails.
    """
    client = _get_codecommit_client()
    results: List[Tuple[str, str]] = []
    folders_to_visit = [folder_path]

    while folders_to_visit:
        current_folder = folders_to_visit.pop()
        logger.debug(
            "GetFolder: repo=%s ref=%s path='%s'",
            repository_name,
            commit_specifier,
            current_folder,
        )

        response = client.get_folder(
            repositoryName=repository_name,
            commitSpecifier=commit_specifier,
            folderPath=current_folder,
        )

        # Collect files at this level
        for file_entry in response.get("files", []):
            abs_path = file_entry["absolutePath"]
            blob_id = file_entry["blobId"]
            results.append((abs_path, blob_id))

        # Queue sub-folders for the next iteration
        for sub in response.get("subFolders", []):
            folders_to_visit.append(sub["absolutePath"])

    logger.info(
        "Found %d files in repo '%s' at ref '%s'",
        len(results),
        repository_name,
        commit_specifier,
    )
    return results


def get_blob_content(repository_name: str, blob_id: str) -> bytes:
    """Fetch the raw content of a Git blob.

    Args:
        repository_name: CodeCommit repository name.
        blob_id: The blob SHA returned by GetFolder.

    Returns:
        Raw file bytes (decoded from the base64 response).

    Raises:
        ClientError: If the CodeCommit API call fails.
    """
    client = _get_codecommit_client()
    response = client.get_blob(
        repositoryName=repository_name,
        blobId=blob_id,
    )
    # boto3 returns the content as bytes already decoded from base64
    return response["content"]


def fetch_all_files(
    repository_name: str,
    branch: str,
) -> Dict[str, bytes]:
    """Download every file from a CodeCommit branch into a dict.

    Combines list_all_files() and get_blob_content() into a single
    convenience function.

    Args:
        repository_name: CodeCommit repository name.
        branch: Branch name (e.g. "main").

    Returns:
        Dict mapping file path → raw bytes for every file in the branch.

    Raises:
        ClientError: If any CodeCommit API call fails.
    """
    file_list = list_all_files(repository_name, branch)
    result: Dict[str, bytes] = {}

    for abs_path, blob_id in file_list:
        logger.debug("GetBlob: %s (blob %s)", abs_path, blob_id)
        result[abs_path] = get_blob_content(repository_name, blob_id)

    return result


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def get_branch_tip_commit(repository_name: str, branch: str) -> Optional[str]:
    """Return the HEAD commit ID for a branch, or None if the branch is empty.

    Args:
        repository_name: CodeCommit repository name.
        branch: Branch name.

    Returns:
        Commit ID string, or None if the branch has no commits yet.

    Raises:
        ClientError: If the branch does not exist or the API call fails.
    """
    client = _get_codecommit_client()
    try:
        response = client.get_branch(
            repositoryName=repository_name,
            branchName=branch,
        )
        return response["branch"]["commitId"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "BranchDoesNotExistException":
            logger.info(
                "Branch '%s' does not exist in repo '%s'", branch, repository_name
            )
            return None
        raise


def _normalise_repo_path(file_path: str) -> str:
    """Normalise a path for CodeCommit and reject directory traversal.

    Strips a leading slash, converts Windows separators to POSIX, and rejects
    any path containing a "." or ".." component or an empty component (e.g.
    from a leading/double slash).  Components are checked individually so that
    legitimate names which merely contain dots (e.g. "abc..def") are allowed.

    Args:
        file_path: Raw file path from the workspace.

    Returns:
        The normalised POSIX-style path.

    Raises:
        ValueError: If the path contains a traversal or empty component.
    """
    normalised_path = file_path.lstrip("/").replace("\\", "/")
    components = normalised_path.split("/")
    if any(part in ("", ".", "..") for part in components):
        raise ValueError(f"Invalid file path rejected: {file_path!r}")
    return normalised_path


def commit_files(
    repository_name: str,
    branch: str,
    files: Dict[str, bytes],
    commit_message: str,
    delete_files: Optional[List[str]] = None,
    author_name: str = "LZA MCP Server",
    author_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Commit all workspace files to a CodeCommit branch in a single call.

    Uses CreateCommit with a putFiles list containing every file and an
    optional deleteFiles list for files that should be removed.  Git records
    a diff only for files whose content actually changed, so the commit history
    stays clean even when all files are included.

    Args:
        repository_name: CodeCommit repository name.
        branch: Target branch name (e.g. "main").
        files: Dict mapping file path → raw bytes.
        commit_message: Commit message.
        delete_files: Optional list of file paths to delete from the repo.
        author_name: Author display name for the commit.
        author_email: Optional author email for the commit.

    Returns:
        Dict with commitId and treeId from the CreateCommit response.

    Raises:
        ClientError: If the CodeCommit API call fails.
    """
    client = _get_codecommit_client()

    # Build the putFiles list — content must be base64-encoded bytes
    put_files = []
    for file_path, content in files.items():
        # Normalise and reject any path traversal sequences — CodeCommit
        # operates on a flat repository tree but we validate defensively to
        # prevent injection of absolute paths or traversal sequences.
        normalised_path = _normalise_repo_path(file_path)

        put_files.append(
            {
                "filePath": normalised_path,
                "fileMode": "NORMAL",
                "fileContent": content,
            }
        )

    # Build the deleteFiles list
    delete_file_entries = []
    if delete_files:
        for file_path in delete_files:
            normalised_path = _normalise_repo_path(file_path)
            delete_file_entries.append({"filePath": normalised_path})

    # Retrieve the current HEAD commit so CreateCommit can detect conflicts
    parent_commit_id = get_branch_tip_commit(repository_name, branch)

    create_kwargs: Dict[str, Any] = {
        "repositoryName": repository_name,
        "branchName": branch,
        "commitMessage": commit_message,
        "authorName": author_name,
        "putFiles": put_files,
    }

    if author_email:
        create_kwargs["email"] = author_email

    if delete_file_entries:
        create_kwargs["deleteFiles"] = delete_file_entries

    if parent_commit_id:
        create_kwargs["parentCommitId"] = parent_commit_id

    logger.info(
        "CreateCommit: repo=%s branch=%s put=%d delete=%d parent=%s",
        repository_name,
        branch,
        len(put_files),
        len(delete_file_entries),
        parent_commit_id or "none",
    )

    response = client.create_commit(**create_kwargs)

    return {
        "commitId": response["commitId"],
        "treeId": response["treeId"],
    }
