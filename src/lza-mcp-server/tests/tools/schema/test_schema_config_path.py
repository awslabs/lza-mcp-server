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

"""Unit tests for SchemaSearchConfig schema path resolution."""

import os
import pytest
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.schema.schema_config import SchemaSearchConfig


class TestGetSchemaVersionPath:
    """Test schema version path resolution."""

    @patch("os.path.exists")
    def test_get_schema_version_path_success(self, mock_exists):
        """Test successful schema path resolution."""
        mock_exists.return_value = True
        version = "v1.12.0"
        base_dir = "/app/json-schemas"

        path = SchemaSearchConfig.get_schema_version_path(version, base_dir)

        expected_path = os.path.join(base_dir, version, "combined.json")
        assert path == expected_path
        mock_exists.assert_called_once_with(expected_path)

    @patch("os.path.exists")
    def test_get_schema_version_path_custom_base_dir(self, mock_exists):
        """Test schema path resolution with custom base directory."""
        mock_exists.return_value = True
        version = "v1.11.0"
        base_dir = "/custom/schemas"

        path = SchemaSearchConfig.get_schema_version_path(version, base_dir)

        expected_path = os.path.join(base_dir, version, "combined.json")
        assert path == expected_path
        assert "/custom/schemas" in path

    @patch("os.path.exists")
    def test_get_schema_version_path_file_not_found(self, mock_exists):
        """Test schema path resolution when file doesn't exist."""
        mock_exists.return_value = False
        version = "v1.99.0"
        base_dir = "/app/json-schemas"

        with pytest.raises(FileNotFoundError) as exc_info:
            SchemaSearchConfig.get_schema_version_path(version, base_dir)

        assert "Schema file not found" in str(exc_info.value)
        assert version in str(exc_info.value)
        assert "combined.json" in str(exc_info.value)

    def test_get_schema_version_path_latest_not_supported(self):
        """Test that 'latest' version is not supported."""
        version = "latest"
        base_dir = "/app/json-schemas"

        with pytest.raises(ValueError) as exc_info:
            SchemaSearchConfig.get_schema_version_path(version, base_dir)

        error_message = str(exc_info.value)
        assert '"latest" is not supported' in error_message
        assert "explicit version" in error_message
        assert "listLzaSupportedVersions" in error_message

    @patch("os.path.exists")
    def test_get_schema_version_path_default_base_dir(self, mock_exists):
        """Test schema path resolution with default base directory."""
        mock_exists.return_value = True
        version = "v1.12.0"

        path = SchemaSearchConfig.get_schema_version_path(version)

        assert "/app/json-schemas" in path
        assert version in path
        assert "combined.json" in path

    @patch("os.path.exists")
    def test_get_schema_version_path_with_patch_version(self, mock_exists):
        """Test schema path resolution with patch version."""
        mock_exists.return_value = True
        version = "v1.12.3"
        base_dir = "/app/json-schemas"

        path = SchemaSearchConfig.get_schema_version_path(version, base_dir)

        expected_path = os.path.join(base_dir, version, "combined.json")
        assert path == expected_path

    @patch("os.path.exists")
    def test_get_schema_version_path_constructs_correct_path(self, mock_exists):
        """Test that path is correctly constructed with os.path.join."""
        mock_exists.return_value = True
        version = "v1.12.0"
        base_dir = "/test/path"

        path = SchemaSearchConfig.get_schema_version_path(version, base_dir)

        # Verify path components
        assert path.startswith(base_dir)
        assert version in path
        assert path.endswith("combined.json")
        # Verify proper path separator usage
        assert os.path.sep in path
