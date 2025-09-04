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

"""Unit tests for validation common module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.validation.common import validate_configuration_impl


class TestValidateConfigurationImpl:
    """Test cases for validate_configuration_impl function."""

    def test_validate_configuration_nonexistent_directory(self):
        """Test validation with non-existent directory."""
        result = validate_configuration_impl("/nonexistent/path")

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "Config directory not found" in result["errors"][0]["message"]

    def test_validate_configuration_empty_directory(self):
        """Test validation with empty directory in test mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is True
            assert result["message"] == "Configuration validation successful"

    def test_validate_configuration_missing_required_files(self):
        """Test validation with missing required files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = validate_configuration_impl(temp_dir, _test_mode=False)

            assert result["valid"] is False
            assert len(result["errors"]) == 3  # Three required files missing
            error_messages = [error["message"] for error in result["errors"]]
            assert any("accounts-config.yaml" in msg for msg in error_messages)
            assert any("global-config.yaml" in msg for msg in error_messages)
            assert any("organization-config.yaml" in msg for msg in error_messages)

    def test_validate_configuration_valid_yaml_files(self):
        """Test validation with valid YAML files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid YAML files
            (temp_path / "accounts-config.yaml").write_text("key: value\n")
            (temp_path / "global-config.yaml").write_text("global: config\n")
            (temp_path / "organization-config.yaml").write_text("org: config\n")

            result = validate_configuration_impl(temp_dir, _test_mode=False)

            assert result["valid"] is True
            assert result["message"] == "Configuration validation successful"

    def test_validate_configuration_invalid_yaml_syntax(self):
        """Test validation with invalid YAML syntax."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid YAML file
            (temp_path / "invalid.yaml").write_text("key: value\n  invalid: yaml")

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert "YAML syntax error" in result["errors"][0]["message"]
            assert result["errors"][0]["severity"] == "error"

    def test_validate_configuration_valid_json_files(self):
        """Test validation with valid JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid JSON file
            (temp_path / "config.json").write_text('{"key": "value"}')

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is True

    def test_validate_configuration_invalid_json_syntax(self):
        """Test validation with invalid JSON syntax."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid JSON file
            (temp_path / "invalid.json").write_text(
                '{"key": "value"'
            )  # Missing closing brace

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert "JSON syntax error" in result["errors"][0]["message"]

    def test_validate_configuration_mixed_valid_invalid_files(self):
        """Test validation with mix of valid and invalid files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid and invalid files
            (temp_path / "valid.yaml").write_text("key: value\n")
            (temp_path / "invalid.yaml").write_text("key: value\n  invalid: yaml")
            (temp_path / "valid.json").write_text('{"key": "value"}')

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert "YAML syntax error" in result["errors"][0]["message"]

    def test_validate_configuration_ignores_non_config_files(self):
        """Test validation ignores non-configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create non-config files that should be ignored
            (temp_path / "readme.txt").write_text("This is a readme")
            (temp_path / "script.py").write_text("print('hello')")

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is True

    def test_validate_configuration_subdirectories(self):
        """Test validation with files in subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create subdirectory with config files
            subdir = temp_path / "policies"
            subdir.mkdir()
            (subdir / "policy.json").write_text('{"policy": "content"}')

            result = validate_configuration_impl(temp_dir, _test_mode=True)

            assert result["valid"] is True

    def test_validate_configuration_file_read_error(self):
        """Test validation with file read error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a file and then mock an error reading it
            config_file = temp_path / "config.yaml"
            config_file.write_text("key: value\n")

            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                result = validate_configuration_impl(temp_dir, _test_mode=True)

                assert result["valid"] is False
                assert len(result["errors"]) == 1
                assert "Error reading config.yaml" in result["errors"][0]["message"]

    def test_validate_configuration_unexpected_error(self):
        """Test validation with unexpected error."""
        with patch("pathlib.Path.resolve", side_effect=Exception("Unexpected error")):
            result = validate_configuration_impl("/some/path", _test_mode=True)

            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert (
                "Validation error: Unexpected error" in result["errors"][0]["message"]
            )
