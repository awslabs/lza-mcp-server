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

"""Unit tests for update_uc_file error handling."""

import pytest
import yaml

from awslabs.lza_mcp_server.tools.uc_merge.update_uc_file import update_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager
from awslabs.lza_mcp_server.error_categories import ErrorCategory


@pytest.fixture
def temp_session(tmp_path):
    """Create a temporary UC session directory structure."""
    session_manager = SessionManager(base_session_dir=tmp_path)
    session_id = session_manager.generate_session_id()
    session_path = session_manager.create_session_directory(session_id)
    session_manager.save_session_metadata(
        session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
    )

    # Create sample configuration file
    (session_path / "test-config.yaml").write_text(
        "HomeRegion: us-east-1\nHomeRegionIngressCidr: 10.0.0.0/16\n"
    )

    return {
        "session_id": session_id,
        "session_path": session_path,
        "session_manager": session_manager,
    }


class TestFileErrors:
    """Test file-related error handling."""

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_session, monkeypatch):
        """Test error when file does not exist."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "nonexistent-file.yaml",
            {"HomeRegion": "us-west-2"},
        )

        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert result["category"] == ErrorCategory.FILE_NOT_FOUND
        assert "context" in result
        assert result["context"]["file_path"] == "nonexistent-file.yaml"

    @pytest.mark.asyncio
    async def test_path_traversal_attempt(self, temp_session, monkeypatch):
        """Test error when attempting path traversal."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "../../../etc/passwd",
            {"HomeRegion": "us-west-2"},
        )

        assert result["success"] is False
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_invalid_yaml_file(self, temp_session, monkeypatch):
        """Test error when file contains invalid YAML."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Create file with invalid YAML
        session_path = temp_session["session_path"]
        (session_path / "invalid.yaml").write_text(
            "key: value\n  invalid indentation\nanother: [unclosed bracket\n"
        )

        result = await update_uc_file(
            temp_session["session_id"],
            "invalid.yaml",
            {"HomeRegion": "us-west-2"},
        )

        assert result["success"] is False
        assert result["error_code"] == "YAML_PARSE_ERROR"
        assert result["category"] == ErrorCategory.CONFIGURATION

    @pytest.mark.asyncio
    async def test_empty_yaml_file(self, temp_session, monkeypatch):
        """Test handling of empty YAML file."""
        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Create empty file
        session_path = temp_session["session_path"]
        (session_path / "empty.yaml").write_text("")

        result = await update_uc_file(
            temp_session["session_id"],
            "empty.yaml",
            {"HomeRegion": "us-west-2"},
        )

        # Should succeed and create new content
        assert result["success"] is True
        assert result["updates_applied"]["HomeRegion"]["new"] == "us-west-2"

    @pytest.mark.asyncio
    async def test_file_read_permission_error(self, temp_session, monkeypatch):
        """Test error when file cannot be read due to permissions."""
        from unittest.mock import patch

        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Mock the file open to raise PermissionError on read
        original_open = open

        def mock_open_func(file, mode="r", *args, **kwargs):
            if "r" in mode and "test-config.yaml" in str(file):
                raise PermissionError("Permission denied")
            return original_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            result = await update_uc_file(
                temp_session["session_id"],
                "test-config.yaml",
                {"HomeRegion": "us-west-2"},
            )

            assert result["success"] is False
            assert result["error_code"] == "FILE_READ_ERROR"
            assert result["category"] == ErrorCategory.FILE_OPERATION


class TestYAMLGenerationErrors:
    """Test YAML generation error handling."""

    @pytest.mark.asyncio
    async def test_yaml_generation_error(self, temp_session, monkeypatch):
        """Test error when YAML generation fails."""
        from unittest.mock import patch

        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Mock yaml.dump to raise an error
        with patch("yaml.dump") as mock_dump:
            mock_dump.side_effect = yaml.YAMLError("Cannot serialize")

            result = await update_uc_file(
                temp_session["session_id"],
                "test-config.yaml",
                {"HomeRegion": "us-west-2"},
            )

            assert result["success"] is False
            assert result["error_code"] == "YAML_GENERATION_ERROR"
            assert result["category"] == ErrorCategory.CONFIGURATION


class TestFileWriteErrors:
    """Test file write error handling."""

    @pytest.mark.asyncio
    async def test_file_write_permission_error(self, temp_session, monkeypatch):
        """Test error when file cannot be written due to permissions."""
        from unittest.mock import patch

        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Mock the file open to raise PermissionError on write
        original_open = open

        def mock_open_func(file, mode="r", *args, **kwargs):
            if "w" in mode and "test-config.yaml" in str(file):
                raise PermissionError("Permission denied")
            return original_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            result = await update_uc_file(
                temp_session["session_id"],
                "test-config.yaml",
                {"HomeRegion": "us-west-2"},
            )

            assert result["success"] is False
            assert result["error_code"] == "FILE_WRITE_ERROR"
            assert result["category"] == ErrorCategory.FILE_OPERATION

    @pytest.mark.asyncio
    async def test_file_write_disk_full_error(self, temp_session, monkeypatch):
        """Test error when disk is full during write."""
        from unittest.mock import patch

        monkeypatch.setattr(
            "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file.SessionManager",
            lambda: temp_session["session_manager"],
        )

        # Mock the file open to raise OSError on write
        original_open = open

        def mock_open_func(file, mode="r", *args, **kwargs):
            if "w" in mode and "test-config.yaml" in str(file):
                raise OSError(28, "No space left on device")
            return original_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            result = await update_uc_file(
                temp_session["session_id"],
                "test-config.yaml",
                {"HomeRegion": "us-west-2"},
            )

            assert result["success"] is False
            assert result["error_code"] == "FILE_WRITE_ERROR"
            # Check that troubleshooting mentions disk space
            troubleshooting_text = " ".join(result["troubleshooting"]).lower()
            assert "disk space" in troubleshooting_text
