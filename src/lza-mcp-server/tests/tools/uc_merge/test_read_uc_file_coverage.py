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

"""Additional coverage tests for read_uc_file tool."""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from awslabs.lza_mcp_server.tools.uc_merge.read_uc_file import read_uc_file
from awslabs.lza_mcp_server.tools.uc_merge.session_manager import SessionManager


@pytest.fixture
def mock_ctx():
    """Create a mock MCP context."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


@pytest.mark.unit
@pytest.mark.uc_merge
class TestReadUcFileCoverage:
    """Additional coverage tests for read_uc_file tool."""

    @pytest.mark.asyncio
    async def test_unicode_decode_error(self, mock_ctx, tmp_path):
        """Test handling of Unicode decode errors.

        Covers lines 232-250: UnicodeDecodeError exception handling
        """
        # Patch SessionManager to use our temp directory
        from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module

        original_session_manager = module.SessionManager

        # Create session using SessionManager
        session_manager = SessionManager(base_session_dir=tmp_path)
        session_id = session_manager.generate_session_id()
        session_path = session_manager.create_session_directory(session_id)
        session_manager.save_session_metadata(
            session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
        )

        # Create a file with invalid UTF-8 bytes
        test_file = session_path / "test.yaml"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        def patched_session_manager():
            return session_manager

        module.SessionManager = patched_session_manager

        try:
            # Run the tool
            result = await read_uc_file(mock_ctx, session_id, "test.yaml")

            # Assertions
            assert result["success"] is False
            assert result["error_code"] == "ENCODING_ERROR"
            assert "Failed to decode file as UTF-8" in result["error"]
            assert "troubleshooting" in result
        finally:
            module.SessionManager = original_session_manager

    @pytest.mark.asyncio
    async def test_permission_error(self, mock_ctx, tmp_path):
        """Test handling of permission errors.

        Covers lines 251-269: PermissionError exception handling
        """
        # Patch SessionManager to use our temp directory
        from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module

        original_session_manager = module.SessionManager

        # Create session using SessionManager
        session_manager = SessionManager(base_session_dir=tmp_path)
        session_id = session_manager.generate_session_id()
        session_path = session_manager.create_session_directory(session_id)
        session_manager.save_session_metadata(
            session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
        )

        # Create a test file
        test_file = session_path / "test.yaml"
        test_file.write_text("test: content")

        def patched_session_manager():
            return session_manager

        module.SessionManager = patched_session_manager

        try:
            # Mock read_text to raise PermissionError
            with patch.object(Path, "read_text") as mock_read:
                mock_read.side_effect = PermissionError("Access denied")

                # Run the tool
                result = await read_uc_file(mock_ctx, session_id, "test.yaml")

            # Assertions
            assert result["success"] is False
            assert result["error_code"] == "ACCESS_DENIED"
            assert "Permission denied" in result["error"]
            assert "troubleshooting" in result
        finally:
            module.SessionManager = original_session_manager

    @pytest.mark.asyncio
    async def test_unexpected_error_reading_file(self, mock_ctx, tmp_path):
        """Test handling of unexpected errors during file read.

        Covers lines 270-283: General exception handling
        """
        # Patch SessionManager to use our temp directory
        from awslabs.lza_mcp_server.tools.uc_merge import read_uc_file as module

        original_session_manager = module.SessionManager

        # Create session using SessionManager
        session_manager = SessionManager(base_session_dir=tmp_path)
        session_id = session_manager.generate_session_id()
        session_path = session_manager.create_session_directory(session_id)
        session_manager.save_session_metadata(
            session_id=session_id, network_model="hub-and-spoke", uc_release="v1.0.0"
        )

        # Create a test file
        test_file = session_path / "test.yaml"
        test_file.write_text("test: content")

        def patched_session_manager():
            return session_manager

        module.SessionManager = patched_session_manager

        try:
            # Mock read_text to raise unexpected error
            with patch.object(Path, "read_text") as mock_read:
                mock_read.side_effect = RuntimeError("Unexpected filesystem error")

                # Run the tool
                result = await read_uc_file(mock_ctx, session_id, "test.yaml")

            # Assertions
            assert result["success"] is False
            assert "Failed to read file" in result["error"]
            assert "troubleshooting" in result
        finally:
            module.SessionManager = original_session_manager
