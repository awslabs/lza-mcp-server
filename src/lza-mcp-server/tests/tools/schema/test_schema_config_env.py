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

"""Unit tests for SchemaSearchConfig environment configuration."""

import os
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.schema.schema_config import get_config_from_env


class TestGetConfigFromEnv:
    """Test environment-based configuration overrides."""

    def test_get_config_from_env_no_overrides(self):
        """Test get_config_from_env with no environment variables set."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_config_from_env()
            assert config == {}

    def test_get_config_from_env_large_file_threshold(self):
        """Test SCHEMA_LARGE_FILE_THRESHOLD environment variable."""
        with patch.dict(
            os.environ, {"SCHEMA_LARGE_FILE_THRESHOLD": "5242880"}, clear=True
        ):
            config = get_config_from_env()
            assert "large_file_threshold" in config
            assert config["large_file_threshold"] == 5242880

    def test_get_config_from_env_max_results(self):
        """Test SCHEMA_MAX_RESULTS environment variable."""
        with patch.dict(os.environ, {"SCHEMA_MAX_RESULTS": "20"}, clear=True):
            config = get_config_from_env()
            assert "max_results_default" in config
            assert config["max_results_default"] == 20

    def test_get_config_from_env_chunk_size(self):
        """Test SCHEMA_CHUNK_SIZE environment variable."""
        with patch.dict(os.environ, {"SCHEMA_CHUNK_SIZE": "100"}, clear=True):
            config = get_config_from_env()
            assert "chunk_size_normal" in config
            assert config["chunk_size_normal"] == 100

    def test_get_config_from_env_max_properties(self):
        """Test SCHEMA_MAX_PROPERTIES environment variable."""
        with patch.dict(os.environ, {"SCHEMA_MAX_PROPERTIES": "50"}, clear=True):
            config = get_config_from_env()
            assert "max_properties_to_check" in config
            assert config["max_properties_to_check"] == 50

    def test_get_config_from_env_multiple_overrides(self):
        """Test multiple environment variable overrides."""
        env_vars = {
            "SCHEMA_LARGE_FILE_THRESHOLD": "3145728",
            "SCHEMA_MAX_RESULTS": "15",
            "SCHEMA_CHUNK_SIZE": "75",
            "SCHEMA_MAX_PROPERTIES": "30",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_config_from_env()
            assert len(config) == 4
            assert config["large_file_threshold"] == 3145728
            assert config["max_results_default"] == 15
            assert config["chunk_size_normal"] == 75
            assert config["max_properties_to_check"] == 30

    def test_get_config_from_env_partial_overrides(self):
        """Test partial environment variable overrides."""
        env_vars = {
            "SCHEMA_MAX_RESULTS": "25",
            "SCHEMA_CHUNK_SIZE": "60",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_config_from_env()
            assert len(config) == 2
            assert config["max_results_default"] == 25
            assert config["chunk_size_normal"] == 60
            assert "large_file_threshold" not in config
            assert "max_properties_to_check" not in config

    def test_get_config_from_env_ignores_unrelated_vars(self):
        """Test that unrelated environment variables are ignored."""
        env_vars = {
            "SCHEMA_MAX_RESULTS": "10",
            "UNRELATED_VAR": "value",
            "ANOTHER_VAR": "123",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_config_from_env()
            assert len(config) == 1
            assert config["max_results_default"] == 10
            assert "unrelated_var" not in config
            assert "another_var" not in config

    def test_get_config_from_env_converts_to_int(self):
        """Test that environment variable values are converted to integers."""
        with patch.dict(os.environ, {"SCHEMA_MAX_RESULTS": "42"}, clear=True):
            config = get_config_from_env()
            assert isinstance(config["max_results_default"], int)
            assert config["max_results_default"] == 42

    def test_get_config_from_env_zero_values(self):
        """Test environment variables with zero values."""
        env_vars = {
            "SCHEMA_MAX_RESULTS": "0",
            "SCHEMA_CHUNK_SIZE": "0",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_config_from_env()
            assert config["max_results_default"] == 0
            assert config["chunk_size_normal"] == 0

    def test_get_config_from_env_large_values(self):
        """Test environment variables with large values."""
        env_vars = {
            "SCHEMA_LARGE_FILE_THRESHOLD": "104857600",  # 100MB
            "SCHEMA_MAX_PROPERTIES": "10000",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_config_from_env()
            assert config["large_file_threshold"] == 104857600
            assert config["max_properties_to_check"] == 10000
