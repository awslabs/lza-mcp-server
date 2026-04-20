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

"""Zip utility for creating zip archives from workspace files."""

import io
import logging
import zipfile

from awslabs.lza_mcp_server.utils.workspace_manager import (
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspaceStorageError,
    WorkspaceValidationError,
)

logger = logging.getLogger(__name__)


class ZipUtility:
    """Creates zip archives from workspace files and folders.

    Delegates all I/O to a ``WorkspaceManager``, inheriting its path
    safety validation.
    """

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        self._wm = workspace_manager

    def create_zip(
        self,
        workspace_id: str,
        source_paths: list[str],
        destination_path: str,
    ) -> None:
        """Create a zip archive from *source_paths* and write it to *destination_path*.

        - Folder sources are recursively included.
        - Path safety validation is applied to every source and the destination.
        - Missing source paths produce a descriptive error listing them all.
        """
        if not source_paths:
            raise WorkspaceValidationError("source_paths cannot be empty")

        # Validate destination path early (delegates to WorkspaceManager)
        self._wm.validate_path(workspace_id, destination_path)

        # Resolve each source — collect files to include and any missing paths.
        missing: list[str] = []
        # List of (archive_name, source_path) tuples
        entries: list[tuple[str, str]] = []

        all_files = self._wm.list_files(workspace_id)

        for src in source_paths:
            # Validate the source path (raises on traversal)
            self._wm.validate_path(workspace_id, src)

            # Check if src is an exact file match
            if src in all_files:
                entries.append((src, src))
                continue

            # Check if src is a folder prefix
            prefix = src.rstrip("/") + "/"
            children = [f for f in all_files if f.startswith(prefix)]
            if children:
                for child in children:
                    entries.append((child, child))
                continue

            # Neither file nor folder — record as missing
            missing.append(src)

        if missing:
            raise WorkspaceNotFoundError(
                "Source paths not found in workspace: " + ", ".join(missing)
            )

        # Build the zip in memory
        buf = io.BytesIO()
        try:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for archive_name, file_path in entries:
                    content = self._wm.read_file(workspace_id, file_path)
                    zf.writestr(archive_name, content)
        except (WorkspaceValidationError, WorkspaceNotFoundError):
            raise
        except Exception as exc:
            logger.error("Failed to build zip in workspace %s: %s", workspace_id, exc)
            raise WorkspaceStorageError(f"Failed to build zip archive: {exc}") from exc

        # Write the zip to the destination
        try:
            self._wm.write_file(workspace_id, destination_path, buf.getvalue())
        except (WorkspaceValidationError, WorkspaceNotFoundError):
            raise
        except Exception as exc:
            logger.error(
                "Failed to write zip to '%s' in workspace %s: %s",
                destination_path,
                workspace_id,
                exc,
            )
            raise WorkspaceStorageError(
                f"Failed to write zip to '{destination_path}': {exc}"
            ) from exc
