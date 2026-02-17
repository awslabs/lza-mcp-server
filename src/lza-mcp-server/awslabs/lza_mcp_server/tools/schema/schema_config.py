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

"""Configuration settings for schema search functionality."""

import os
from typing import Dict, Any


class SchemaSearchConfig:
    """Configuration for schema search operations."""

    # File size thresholds (in bytes)
    LARGE_FILE_THRESHOLD = 2 * 1024 * 1024  # 2MB
    HUGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB

    # Search limits
    MAX_RESULTS_DEFAULT = 10
    MAX_RESULTS_LARGE_FILE = 5
    MAX_PROPERTIES_TO_CHECK = 20
    MAX_MATCH_LOCATIONS = 5
    MAX_DESCRIPTION_LENGTH = 200

    # Chunking settings
    CHUNK_SIZE_NORMAL = 50
    CHUNK_SIZE_LARGE = 20
    CHUNK_SIZE_HUGE = 10

    # Memory management
    MAX_SCHEMA_KEYS_TO_EXTRACT = 1000
    INITIAL_READ_SIZE = 1024 * 1024  # 1MB for key extraction

    @classmethod
    def get_chunk_size(cls, file_size: int) -> int:
        """Get appropriate chunk size based on file size."""
        if file_size > cls.HUGE_FILE_THRESHOLD:
            return cls.CHUNK_SIZE_HUGE
        elif file_size > cls.LARGE_FILE_THRESHOLD:
            return cls.CHUNK_SIZE_LARGE
        else:
            return cls.CHUNK_SIZE_NORMAL

    @classmethod
    def get_max_results(cls, file_size: int, requested_max: int) -> int:
        """Get appropriate max results based on file size."""
        if file_size > cls.LARGE_FILE_THRESHOLD:
            return min(requested_max, cls.MAX_RESULTS_LARGE_FILE)
        else:
            return requested_max

    @classmethod
    def get_schema_version_path(
        cls,
        version: str,
        base_dir: str = None,
    ) -> str:
        """Get path to schema file for a specific LZA version.

        Args:
            version: LZA version (e.g., "v1.12.0") - must be explicit
            base_dir: Base directory containing versioned schemas (defaults to LZA_SCHEMA_DIR env var or /app/json-schemas)

        Returns:
            Path to combined.json for the specified version

        Raises:
            FileNotFoundError: If schema file doesn't exist for version
            ValueError: If version is "latest" (not supported)
        """
        if base_dir is None:
            base_dir = os.environ.get("LZA_SCHEMA_DIR", "/app/json-schemas")

        if version == "latest":
            raise ValueError(
                'Version "latest" is not supported. '
                'Please specify an explicit version (e.g., "v1.12.0"). '
                "Use listLzaSupportedVersions() to see available versions."
            )

        schema_path = os.path.join(base_dir, version, "combined.json")

        if not os.path.exists(schema_path):
            raise FileNotFoundError(
                f"Schema file not found for version {version}: {schema_path}"
            )

        return schema_path


# Environment-based configuration overrides
def get_config_from_env() -> Dict[str, Any]:
    """Get configuration overrides from environment variables."""
    config = {}

    # File size thresholds
    if "SCHEMA_LARGE_FILE_THRESHOLD" in os.environ:
        config["large_file_threshold"] = int(os.environ["SCHEMA_LARGE_FILE_THRESHOLD"])

    # Search limits
    if "SCHEMA_MAX_RESULTS" in os.environ:
        config["max_results_default"] = int(os.environ["SCHEMA_MAX_RESULTS"])

    if "SCHEMA_CHUNK_SIZE" in os.environ:
        config["chunk_size_normal"] = int(os.environ["SCHEMA_CHUNK_SIZE"])

    # Memory management
    if "SCHEMA_MAX_PROPERTIES" in os.environ:
        config["max_properties_to_check"] = int(os.environ["SCHEMA_MAX_PROPERTIES"])

    return config


# Apply environment overrides
_env_config = get_config_from_env()
for key, value in _env_config.items():
    if hasattr(SchemaSearchConfig, key.upper()):
        setattr(SchemaSearchConfig, key.upper(), value)
