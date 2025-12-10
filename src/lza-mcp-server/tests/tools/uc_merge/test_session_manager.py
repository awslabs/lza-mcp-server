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

"""Unit tests for session management utilities."""

import json
import pytest
import shutil
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager


@pytest.mark.unit
@pytest.mark.uc_merge
class TestSessionManager:
    """Test suite for SessionManager class."""
    
    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create a temporary session directory for testing."""
        session_dir = tmp_path / "test-sessions"
        session_dir.mkdir()
        return session_dir
    
    @pytest.fixture
    def session_manager(self, temp_session_dir):
        """Create a SessionManager instance with temporary directory."""
        return SessionManager(base_session_dir=temp_session_dir)
    
    def test_session_id_generation_uniqueness(self, session_manager):
        """Test that session_id generation produces unique identifiers.
        
        Requirements: 2.5, 2.7
        """
        # Generate two session IDs with a delay
        session_id1 = session_manager.generate_session_id()
        time.sleep(1.1)  # Ensure timestamp changes (resolution is 1 second)
        session_id2 = session_manager.generate_session_id()
        
        # Verify IDs are different
        assert session_id1 != session_id2
        
        # Verify both have correct format
        for session_id in [session_id1, session_id2]:
            assert session_id.startswith("uc-session-")
            # Format: uc-session-YYYYMMDD-HHMMSS
            parts = session_id.split("-")
            assert len(parts) == 4
            assert parts[0] == "uc"
            assert parts[1] == "session"
            assert len(parts[2]) == 8  # YYYYMMDD
            assert len(parts[3]) == 6  # HHMMSS
    
    def test_session_id_format(self, session_manager):
        """Test that session_id follows the expected format.
        
        Requirements: 2.7
        """
        session_id = session_manager.generate_session_id()
        
        # Verify format: uc-session-{timestamp}
        assert session_id.startswith("uc-session-")
        
        # Extract timestamp part
        timestamp_part = session_id.replace("uc-session-", "")
        
        # Verify timestamp format: YYYYMMDD-HHMMSS
        assert len(timestamp_part) == 15  # 8 + 1 + 6
        assert timestamp_part[8] == "-"
        
        # Verify it's a valid timestamp
        date_part = timestamp_part[:8]
        time_part = timestamp_part[9:]
        
        # Should be able to parse as datetime
        datetime.strptime(date_part, "%Y%m%d")
        datetime.strptime(time_part, "%H%M%S")
    
    def test_session_directory_creation(self, session_manager):
        """Test session directory creation.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        
        # Create session directory
        session_path = session_manager.create_session_directory(session_id)
        
        # Verify directory was created
        assert session_path.exists()
        assert session_path.is_dir()
        assert session_path.name == session_id
        
        # Verify path is correct
        expected_path = session_manager.base_session_dir / session_id
        assert session_path == expected_path
    
    def test_session_directory_creation_idempotent(self, session_manager):
        """Test that creating the same session directory twice doesn't fail."""
        session_id = "uc-session-20250127-143022"
        
        # Create directory twice
        path1 = session_manager.create_session_directory(session_id)
        path2 = session_manager.create_session_directory(session_id)
        
        # Both should succeed and return same path
        assert path1 == path2
        assert path1.exists()
    
    def test_session_exists_check(self, session_manager):
        """Test session existence checking.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        
        # Initially should not exist
        assert not session_manager.session_exists(session_id)
        
        # Create session
        session_manager.create_session_directory(session_id)
        
        # Now should exist
        assert session_manager.session_exists(session_id)
    
    def test_session_exists_returns_false_for_file(self, session_manager):
        """Test that session_exists returns False if path is a file, not directory."""
        session_id = "uc-session-20250127-143022"
        
        # Create a file instead of directory
        file_path = session_manager.base_session_dir / session_id
        file_path.write_text("not a directory")
        
        # Should return False
        assert not session_manager.session_exists(session_id)
    
    def test_get_session_path(self, session_manager):
        """Test getting session path."""
        session_id = "uc-session-20250127-143022"
        
        path = session_manager.get_session_path(session_id)
        
        # Verify path structure
        assert path == session_manager.base_session_dir / session_id
        assert path.name == session_id
    
    def test_save_session_metadata(self, session_manager):
        """Test saving session metadata.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Save metadata
        session_manager.save_session_metadata(
            session_id=session_id,
            network_model="hub-and-spoke",
            uc_release="v1.0.0",
            custom_field="custom_value"
        )
        
        # Verify metadata file was created
        metadata_file = session_manager.get_session_path(session_id) / ".session_metadata.json"
        assert metadata_file.exists()
        
        # Verify metadata content
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        assert metadata["session_id"] == session_id
        assert metadata["network_model"] == "hub-and-spoke"
        assert metadata["uc_release"] == "v1.0.0"
        assert metadata["custom_field"] == "custom_value"
        assert "created_at" in metadata
    
    def test_load_session_metadata(self, session_manager):
        """Test loading session metadata.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Save metadata
        session_manager.save_session_metadata(
            session_id=session_id,
            network_model="shared-vpc",
            uc_release="v2.0.0"
        )
        
        # Load metadata
        metadata = session_manager.load_session_metadata(session_id)
        
        # Verify loaded metadata
        assert metadata is not None
        assert metadata["session_id"] == session_id
        assert metadata["network_model"] == "shared-vpc"
        assert metadata["uc_release"] == "v2.0.0"
        assert "created_at" in metadata
    
    def test_load_session_metadata_not_found(self, session_manager):
        """Test loading metadata for non-existent session."""
        session_id = "uc-session-nonexistent"
        
        # Should return None
        metadata = session_manager.load_session_metadata(session_id)
        assert metadata is None
    
    def test_load_session_metadata_invalid_json(self, session_manager):
        """Test loading metadata with invalid JSON."""
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Write invalid JSON
        metadata_file = session_manager.get_session_path(session_id) / ".session_metadata.json"
        metadata_file.write_text("invalid json {")
        
        # Should return None
        metadata = session_manager.load_session_metadata(session_id)
        assert metadata is None
    
    def test_validate_session_success(self, session_manager):
        """Test successful session validation.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        session_manager.save_session_metadata(
            session_id=session_id,
            network_model="hub-and-spoke",
            uc_release="v1.0.0"
        )
        
        # Validate session
        is_valid, error_msg = session_manager.validate_session(session_id)
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_session_empty_id(self, session_manager):
        """Test validation fails for empty session ID."""
        is_valid, error_msg = session_manager.validate_session("")
        
        assert is_valid is False
        assert "cannot be empty" in error_msg
    
    def test_validate_session_non_string_id(self, session_manager):
        """Test validation fails for non-string session ID."""
        is_valid, error_msg = session_manager.validate_session(123)
        
        assert is_valid is False
        assert "must be a string" in error_msg
    
    def test_validate_session_not_exists(self, session_manager):
        """Test validation fails for non-existent session."""
        session_id = "uc-session-nonexistent"
        
        is_valid, error_msg = session_manager.validate_session(session_id)
        
        assert is_valid is False
        assert "does not exist" in error_msg
        assert "start_uc_merge_session" in error_msg
    
    def test_validate_session_missing_metadata(self, session_manager):
        """Test validation fails when metadata is missing."""
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        # Don't save metadata
        
        is_valid, error_msg = session_manager.validate_session(session_id)
        
        assert is_valid is False
        assert "invalid" in error_msg
        assert "missing metadata" in error_msg
    
    def test_cleanup_previous_sessions(self, session_manager):
        """Test cleanup of previous sessions.
        
        Requirements: 2.11
        """
        # Create multiple sessions
        session1 = "uc-session-20250127-143022"
        session2 = "uc-session-20250127-143023"
        session3 = "uc-session-20250127-143024"
        
        session_manager.create_session_directory(session1)
        session_manager.create_session_directory(session2)
        session_manager.create_session_directory(session3)
        
        # Verify all exist
        assert session_manager.session_exists(session1)
        assert session_manager.session_exists(session2)
        assert session_manager.session_exists(session3)
        
        # Cleanup all sessions
        cleaned_count = session_manager.cleanup_previous_sessions()
        
        # Verify all were cleaned
        assert cleaned_count == 3
        assert not session_manager.session_exists(session1)
        assert not session_manager.session_exists(session2)
        assert not session_manager.session_exists(session3)
    
    def test_cleanup_previous_sessions_keep_one(self, session_manager):
        """Test cleanup keeps specified session.
        
        Requirements: 2.11
        """
        # Create multiple sessions
        session1 = "uc-session-20250127-143022"
        session2 = "uc-session-20250127-143023"
        session3 = "uc-session-20250127-143024"
        
        session_manager.create_session_directory(session1)
        session_manager.create_session_directory(session2)
        session_manager.create_session_directory(session3)
        
        # Cleanup but keep session2
        cleaned_count = session_manager.cleanup_previous_sessions(keep_session_id=session2)
        
        # Verify session2 was kept, others cleaned
        assert cleaned_count == 2
        assert not session_manager.session_exists(session1)
        assert session_manager.session_exists(session2)
        assert not session_manager.session_exists(session3)
    
    def test_cleanup_empty_directory(self, session_manager):
        """Test cleanup on empty directory."""
        # No sessions exist
        cleaned_count = session_manager.cleanup_previous_sessions()
        
        # Should return 0
        assert cleaned_count == 0
    
    def test_cleanup_ignores_non_session_directories(self, session_manager):
        """Test cleanup only removes session directories."""
        # Create session directory
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Create non-session directory
        other_dir = session_manager.base_session_dir / "other-directory"
        other_dir.mkdir()
        
        # Create file
        other_file = session_manager.base_session_dir / "file.txt"
        other_file.write_text("content")
        
        # Cleanup
        cleaned_count = session_manager.cleanup_previous_sessions()
        
        # Only session should be cleaned
        assert cleaned_count == 1
        assert not session_manager.session_exists(session_id)
        assert other_dir.exists()
        assert other_file.exists()
    
    def test_cleanup_handles_permission_errors(self, session_manager, tmp_path):
        """Test cleanup continues even if some deletions fail."""
        # Create sessions
        session1 = "uc-session-20250127-143022"
        session2 = "uc-session-20250127-143023"
        
        session_manager.create_session_directory(session1)
        session_manager.create_session_directory(session2)
        
        # Mock shutil.rmtree to fail on first call
        original_rmtree = shutil.rmtree
        call_count = [0]
        
        def mock_rmtree(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("Permission denied")
            original_rmtree(path, *args, **kwargs)
        
        # Patch and cleanup
        with patch("shutil.rmtree", side_effect=mock_rmtree):
            cleaned_count = session_manager.cleanup_previous_sessions()
        
        # Should have attempted both, but only one succeeded
        assert cleaned_count == 1
    
    def test_copy_files_to_session(self, session_manager, tmp_path):
        """Test copying files to session directory.
        
        Requirements: 2.5
        """
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Create source directory with files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("content1")
        (source_dir / "file2.yaml").write_text("content2")
        
        # Create subdirectory with file
        subdir = source_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")
        
        # Copy files
        files_copied = session_manager.copy_files_to_session(
            session_id=session_id,
            source_dir=source_dir,
            preserve_structure=True
        )
        
        # Verify files were copied
        assert files_copied == 3
        
        session_path = session_manager.get_session_path(session_id)
        assert (session_path / "file1.txt").exists()
        assert (session_path / "file2.yaml").exists()
        assert (session_path / "subdir" / "file3.txt").exists()
        
        # Verify content
        assert (session_path / "file1.txt").read_text() == "content1"
        assert (session_path / "file2.yaml").read_text() == "content2"
        assert (session_path / "subdir" / "file3.txt").read_text() == "content3"
    
    def test_copy_files_preserve_structure(self, session_manager, tmp_path):
        """Test that directory structure is preserved when copying."""
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Create nested directory structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "level1").mkdir()
        (source_dir / "level1" / "level2").mkdir()
        (source_dir / "level1" / "level2" / "file.txt").write_text("nested")
        
        # Copy with structure preservation
        files_copied = session_manager.copy_files_to_session(
            session_id=session_id,
            source_dir=source_dir,
            preserve_structure=True
        )
        
        assert files_copied == 1
        
        # Verify structure is preserved
        session_path = session_manager.get_session_path(session_id)
        nested_file = session_path / "level1" / "level2" / "file.txt"
        assert nested_file.exists()
        assert nested_file.read_text() == "nested"
    
    def test_copy_files_flatten_structure(self, session_manager, tmp_path):
        """Test copying files without preserving structure."""
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Create nested directory structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "subdir").mkdir()
        (source_dir / "file1.txt").write_text("content1")
        (source_dir / "subdir" / "file2.txt").write_text("content2")
        
        # Copy without structure preservation
        files_copied = session_manager.copy_files_to_session(
            session_id=session_id,
            source_dir=source_dir,
            preserve_structure=False
        )
        
        assert files_copied == 2
        
        # Verify files are flattened
        session_path = session_manager.get_session_path(session_id)
        assert (session_path / "file1.txt").exists()
        assert (session_path / "file2.txt").exists()
        assert not (session_path / "subdir").exists()
    
    def test_copy_files_source_not_exists(self, session_manager, tmp_path):
        """Test error when source directory doesn't exist."""
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Use non-existent source
        source_dir = tmp_path / "nonexistent"
        
        # Should raise OSError
        with pytest.raises(OSError) as exc_info:
            session_manager.copy_files_to_session(
                session_id=session_id,
                source_dir=source_dir
            )
        
        assert "does not exist" in str(exc_info.value)
    
    def test_list_sessions(self, session_manager):
        """Test listing all sessions."""
        # Create multiple sessions with metadata
        session1 = "uc-session-20250127-143022"
        session2 = "uc-session-20250127-143023"
        
        session_manager.create_session_directory(session1)
        session_manager.save_session_metadata(
            session_id=session1,
            network_model="hub-and-spoke",
            uc_release="v1.0.0"
        )
        
        session_manager.create_session_directory(session2)
        session_manager.save_session_metadata(
            session_id=session2,
            network_model="shared-vpc",
            uc_release="v2.0.0"
        )
        
        # List sessions
        sessions = session_manager.list_sessions()
        
        # Verify both sessions are listed
        assert len(sessions) == 2
        
        session_ids = [s["session_id"] for s in sessions]
        assert session1 in session_ids
        assert session2 in session_ids
        
        # Verify metadata is included
        for session in sessions:
            assert "session_id" in session
            assert "path" in session
            assert "metadata" in session
            assert session["metadata"] is not None
    
    def test_list_sessions_empty(self, session_manager):
        """Test listing sessions when none exist."""
        sessions = session_manager.list_sessions()
        assert sessions == []
    
    def test_list_sessions_ignores_non_session_dirs(self, session_manager):
        """Test that list_sessions only returns session directories."""
        # Create session
        session_id = "uc-session-20250127-143022"
        session_manager.create_session_directory(session_id)
        
        # Create non-session directory
        other_dir = session_manager.base_session_dir / "other-directory"
        other_dir.mkdir()
        
        # List sessions
        sessions = session_manager.list_sessions()
        
        # Only session should be listed
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id
    
    def test_list_sessions_handles_missing_metadata(self, session_manager):
        """Test listing sessions when some have missing metadata."""
        # Create session with metadata
        session1 = "uc-session-20250127-143022"
        session_manager.create_session_directory(session1)
        session_manager.save_session_metadata(
            session_id=session1,
            network_model="hub-and-spoke",
            uc_release="v1.0.0"
        )
        
        # Create session without metadata
        session2 = "uc-session-20250127-143023"
        session_manager.create_session_directory(session2)
        
        # List sessions
        sessions = session_manager.list_sessions()
        
        # Both should be listed
        assert len(sessions) == 2
        
        # One should have metadata, one should have None
        metadata_values = [s["metadata"] for s in sessions]
        assert None in metadata_values
        assert any(m is not None for m in metadata_values)
