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

"""Session lifecycle management for UC merge operations."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class SessionManager:
    """Manages UC merge session lifecycle including creation, validation, and cleanup."""

    def __init__(self, base_session_dir: Optional[Path] = None):
        """Initialize the session manager.

        Args:
            base_session_dir: Base directory for session storage. If None, uses
                            get_lza_config_base_path() from common module.
        """
        if base_session_dir is None:
            from awslabs.lza_mcp_server.tools.uc_merge.common import (
                get_lza_config_base_path,
            )

            base_session_dir = get_lza_config_base_path()
        self.base_session_dir = base_session_dir
        self.base_session_dir.mkdir(parents=True, exist_ok=True)

    def generate_session_id(self) -> str:
        """Generate a unique session identifier.

        Returns:
            Session ID in format: uc-session-{timestamp}
            Example: uc-session-20250127-143022
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"uc-session-{timestamp}"

    def get_session_path(self, session_id: str) -> Path:
        """Get the full path for a session directory.

        Args:
            session_id: Session identifier

        Returns:
            Path to session directory
        """
        return self.base_session_dir / session_id

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session directory exists, False otherwise
        """
        session_path = self.get_session_path(session_id)
        return session_path.exists() and session_path.is_dir()

    def create_session_directory(self, session_id: str) -> Path:
        """Create a new session directory.

        Args:
            session_id: Session identifier

        Returns:
            Path to created session directory

        Raises:
            OSError: If directory creation fails
        """
        session_path = self.get_session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def save_session_metadata(
        self,
        session_id: str,
        network_model: str,
        uc_release: str,
        **additional_metadata,
    ) -> None:
        """Save session metadata to a JSON file.

        Args:
            session_id: Session identifier
            network_model: Selected network model
            uc_release: UC release version
            **additional_metadata: Additional metadata to store
        """
        session_path = self.get_session_path(session_id)
        metadata_file = session_path / ".session_metadata.json"

        metadata = {
            "session_id": session_id,
            "network_model": network_model,
            "uc_release": uc_release,
            "created_at": datetime.now().isoformat(),
            **additional_metadata,
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def load_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session metadata from JSON file.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary containing session metadata, or None if not found
        """
        session_path = self.get_session_path(session_id)
        metadata_file = session_path / ".session_metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def validate_session(self, session_id: str) -> Tuple[bool, str]:
        """Validate that a session exists and is valid.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not session_id:
            return False, "Session ID cannot be empty"

        if not isinstance(session_id, str):
            return False, "Session ID must be a string"

        if not self.session_exists(session_id):
            return (
                False,
                f"Session '{session_id}' does not exist. Start a session first with start_uc_merge_session()",
            )

        # Check if metadata exists
        metadata = self.load_session_metadata(session_id)
        if metadata is None:
            return False, f"Session '{session_id}' is invalid (missing metadata)"

        return True, ""

    def cleanup_previous_sessions(self, keep_session_id: Optional[str] = None) -> int:
        """Clean up previous session directories.

        Args:
            keep_session_id: Optional session ID to keep (won't be deleted)

        Returns:
            Number of sessions cleaned up
        """
        cleaned_count = 0

        if not self.base_session_dir.exists():
            return cleaned_count

        for session_dir in self.base_session_dir.iterdir():
            if not session_dir.is_dir():
                continue

            # Skip if this is the session to keep
            if keep_session_id and session_dir.name == keep_session_id:
                continue

            # Only clean up directories that match session pattern
            if session_dir.name.startswith("uc-session-"):
                try:
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
                except OSError:
                    # Log but don't fail if cleanup fails
                    pass

        return cleaned_count

    def copy_files_to_session(
        self, session_id: str, source_dir: Path, preserve_structure: bool = True
    ) -> int:
        """Copy files from source directory to session directory.

        Args:
            session_id: Session identifier
            source_dir: Source directory to copy from
            preserve_structure: Whether to preserve directory structure

        Returns:
            Number of files copied

        Raises:
            OSError: If copy operation fails
        """
        session_path = self.get_session_path(session_id)
        files_copied = 0

        if not source_dir.exists():
            raise OSError(f"Source directory does not exist: {source_dir}")

        for item in source_dir.rglob("*"):
            if item.is_file():
                if preserve_structure:
                    # Preserve directory structure
                    relative_path = item.relative_to(source_dir)
                    dest_path = session_path / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    # Flatten structure
                    dest_path = session_path / item.name

                shutil.copy2(item, dest_path)
                files_copied += 1

        return files_copied

    def list_sessions(self) -> list[Dict[str, Any]]:
        """List all existing sessions.

        Returns:
            List of session information dictionaries
        """
        sessions: list[Dict[str, Any]] = []

        if not self.base_session_dir.exists():
            return sessions

        for session_dir in self.base_session_dir.iterdir():
            if not session_dir.is_dir():
                continue

            if session_dir.name.startswith("uc-session-"):
                metadata = self.load_session_metadata(session_dir.name)
                sessions.append(
                    {
                        "session_id": session_dir.name,
                        "path": str(session_dir),
                        "metadata": metadata,
                    }
                )

        return sessions
