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

"""Unit tests for server startup logic."""

import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.server_startup import (
    configure_logging,
    get_schema_directory,
    validate_schema_integrity,
)


class TestGetSchemaDirectory:
    """Test schema directory path retrieval."""

    def test_returns_path_object(self, monkeypatch):
        """Test returns Path object."""
        monkeypatch.setenv("LZA_SCHEMA_DIR", "/custom/path")
        result = get_schema_directory()
        assert isinstance(result, Path)

    def test_uses_env_variable(self, monkeypatch):
        """Test uses LZA_SCHEMA_DIR environment variable."""
        monkeypatch.setenv("LZA_SCHEMA_DIR", "/custom/schema/path")
        result = get_schema_directory()
        assert str(result) == "/custom/schema/path"

    def test_uses_default_when_env_not_set(self, monkeypatch):
        """Test uses default path when environment variable not set."""
        monkeypatch.delenv("LZA_SCHEMA_DIR", raising=False)
        result = get_schema_directory()
        assert str(result) == "/app/json-schemas"

    def test_handles_relative_path(self, monkeypatch):
        """Test handles relative path from environment."""
        monkeypatch.setenv("LZA_SCHEMA_DIR", "relative/path")
        result = get_schema_directory()
        assert str(result) == "relative/path"

    def test_handles_path_with_trailing_slash(self, monkeypatch):
        """Test handles path with trailing slash."""
        monkeypatch.setenv("LZA_SCHEMA_DIR", "/path/to/schemas/")
        result = get_schema_directory()
        # Path normalizes trailing slashes
        assert "/path/to/schemas" in str(result)


class TestValidateSchemaIntegrity:
    """Test schema integrity validation."""

    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_validates_with_default_fail_on_error(self, mock_validate):
        """Test validates with default fail_on_error=True."""
        schema_dir = Path("/test/schemas")

        validate_schema_integrity(schema_dir)

        mock_validate.assert_called_once_with(schema_dir=schema_dir, fail_on_error=True)

    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_validates_with_explicit_fail_on_error_true(self, mock_validate):
        """Test validates with explicit fail_on_error=True."""
        schema_dir = Path("/test/schemas")

        validate_schema_integrity(schema_dir, fail_on_error=True)

        mock_validate.assert_called_once_with(schema_dir=schema_dir, fail_on_error=True)

    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_validates_with_fail_on_error_false(self, mock_validate):
        """Test validates with fail_on_error=False."""
        schema_dir = Path("/test/schemas")

        validate_schema_integrity(schema_dir, fail_on_error=False)

        mock_validate.assert_called_once_with(
            schema_dir=schema_dir, fail_on_error=False
        )

    @patch("awslabs.lza_mcp_server.server_startup.logger")
    def test_raises_import_error_when_module_unavailable(self, mock_logger):
        """Test raises ImportError when integrity module unavailable."""
        schema_dir = Path("/test/schemas")

        with patch(
            "awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup"
        ) as mock_validate:
            mock_validate.side_effect = ImportError("Module not found")

            with pytest.raises(ImportError):
                validate_schema_integrity(schema_dir)

    @patch("awslabs.lza_mcp_server.server_startup.logger")
    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_raises_exception_on_validation_failure(self, mock_validate, mock_logger):
        """Test raises exception when validation fails."""
        schema_dir = Path("/test/schemas")
        mock_validate.side_effect = ValueError("Validation failed")

        with pytest.raises(ValueError, match="Validation failed"):
            validate_schema_integrity(schema_dir)

    @patch("awslabs.lza_mcp_server.server_startup.logger")
    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_logs_error_on_validation_failure(self, mock_validate, mock_logger):
        """Test logs error message when validation fails."""
        schema_dir = Path("/test/schemas")
        mock_validate.side_effect = ValueError("Checksum mismatch")

        with pytest.raises(ValueError):
            validate_schema_integrity(schema_dir)

        mock_logger.error.assert_called_once()
        assert "Schema integrity validation failed" in str(mock_logger.error.call_args)

    @patch("awslabs.lza_mcp_server.utils.integrity.validate_schemas_on_startup")
    def test_successful_validation_no_exception(self, mock_validate):
        """Test successful validation does not raise exception."""
        schema_dir = Path("/test/schemas")
        mock_validate.return_value = None

        # Should not raise
        validate_schema_integrity(schema_dir)


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configures_with_default_level(self, monkeypatch):
        """Test configures logging with default INFO level."""
        monkeypatch.delenv("FASTMCP_LOG_LEVEL", raising=False)

        with patch("logging.basicConfig") as mock_basic_config:
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                configure_logging()

                mock_basic_config.assert_called_once_with(level=logging.INFO)
                mock_logger.setLevel.assert_called_once_with("INFO")

    def test_configures_with_env_variable(self, monkeypatch):
        """Test configures logging from FASTMCP_LOG_LEVEL environment variable."""
        monkeypatch.setenv("FASTMCP_LOG_LEVEL", "DEBUG")

        with patch("logging.basicConfig") as mock_basic_config:
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                configure_logging()

                mock_basic_config.assert_called_once_with(level=logging.INFO)
                mock_logger.setLevel.assert_called_once_with("DEBUG")

    def test_configures_with_explicit_level(self):
        """Test configures logging with explicit log level."""
        with patch("logging.basicConfig") as mock_basic_config:
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                configure_logging(log_level="WARNING")

                mock_basic_config.assert_called_once_with(level=logging.INFO)
                mock_logger.setLevel.assert_called_once_with("WARNING")

    def test_explicit_level_overrides_env(self, monkeypatch):
        """Test explicit log level overrides environment variable."""
        monkeypatch.setenv("FASTMCP_LOG_LEVEL", "DEBUG")

        with patch("logging.basicConfig") as mock_basic_config:
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                configure_logging(log_level="ERROR")

                mock_basic_config.assert_called_once_with(level=logging.INFO)
                mock_logger.setLevel.assert_called_once_with("ERROR")

    def test_handles_various_log_levels(self):
        """Test handles various log level strings."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in log_levels:
            with patch("logging.basicConfig"):
                with patch("logging.getLogger") as mock_get_logger:
                    mock_logger = Mock()
                    mock_get_logger.return_value = mock_logger

                    configure_logging(log_level=level)

                    mock_logger.setLevel.assert_called_once_with(level)
