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

"""Local filesystem storage adapter for workspaces."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalAdapter:
    """StorageAdapter implementation using the local filesystem.

    Base directory is read from the ``WORKSPACE_DIR`` environment variable.
    The variable must be set; no default is provided by the adapter itself.
    The directory is created automatically on first use.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        resolved = base_dir or os.environ.get("WORKSPACE_DIR")
        if not resolved:
            raise RuntimeError(
                "WORKSPACE_DIR environment variable is required "
                "when no explicit base_dir is provided"
            )
        self._base_dir = Path(resolved)
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Create the base directory if it does not exist."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve a relative path under the base directory."""
        return self._base_dir / path

    def write(self, path: str, content: bytes) -> None:
        """Write *content* to *path*, creating parent directories."""
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def read(self, path: str) -> bytes:
        """Read and return bytes from *path*.

        Raises ``FileNotFoundError`` when the path does not exist.
        """
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        return target.read_bytes()

    def delete(self, path: str) -> None:
        """Delete the file at *path*."""
        target = self._resolve(path)
        if target.exists():
            target.unlink()

    def list(self, prefix: Optional[str] = None) -> list[str]:
        """Return relative paths of all files under *prefix* (or root).

        Empty directories are included with a trailing ``/`` so that
        callers can discover them even when they contain no files.
        """
        root = self._resolve(prefix) if prefix else self._base_dir
        if not root.exists():
            return []
        results: list[str] = []
        for p in root.rglob("*"):
            rel = str(p.relative_to(self._base_dir))
            if p.is_file():
                results.append(rel)
            elif p.is_dir() and not any(p.iterdir()):
                # Include empty directories with trailing slash
                results.append(rel + "/")
        return results

    def exists(self, path: str) -> bool:
        """Return True if *path* exists (file or directory)."""
        return self._resolve(path).exists()

    def create_directory(self, path: str) -> None:
        """Create *path* and any intermediate directories."""
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    def delete_directory(self, path: str) -> None:
        """Remove *path* and all its contents."""
        target = self._resolve(path)
        if target.exists():
            shutil.rmtree(target)
