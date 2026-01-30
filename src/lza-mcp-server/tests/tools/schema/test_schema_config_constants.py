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

"""Unit tests for SchemaSearchConfig constants."""

from awslabs.lza_mcp_server.tools.schema.schema_config import SchemaSearchConfig


class TestSchemaSearchConfigConstants:
    """Test configuration constants."""

    def test_file_size_thresholds(self):
        """Test file size threshold constants."""
        assert SchemaSearchConfig.LARGE_FILE_THRESHOLD == 2 * 1024 * 1024  # 2MB
        assert SchemaSearchConfig.HUGE_FILE_THRESHOLD == 10 * 1024 * 1024  # 10MB
        assert (
            SchemaSearchConfig.HUGE_FILE_THRESHOLD
            > SchemaSearchConfig.LARGE_FILE_THRESHOLD
        )

    def test_search_limits(self):
        """Test search limit constants."""
        assert SchemaSearchConfig.MAX_RESULTS_DEFAULT == 10
        assert SchemaSearchConfig.MAX_RESULTS_LARGE_FILE == 5
        assert SchemaSearchConfig.MAX_PROPERTIES_TO_CHECK == 20
        assert SchemaSearchConfig.MAX_MATCH_LOCATIONS == 5
        assert SchemaSearchConfig.MAX_DESCRIPTION_LENGTH == 200

    def test_chunking_settings(self):
        """Test chunking configuration constants."""
        assert SchemaSearchConfig.CHUNK_SIZE_NORMAL == 50
        assert SchemaSearchConfig.CHUNK_SIZE_LARGE == 20
        assert SchemaSearchConfig.CHUNK_SIZE_HUGE == 10
        # Verify decreasing chunk sizes for larger files
        assert (
            SchemaSearchConfig.CHUNK_SIZE_NORMAL > SchemaSearchConfig.CHUNK_SIZE_LARGE
        )
        assert SchemaSearchConfig.CHUNK_SIZE_LARGE > SchemaSearchConfig.CHUNK_SIZE_HUGE

    def test_memory_management(self):
        """Test memory management constants."""
        assert SchemaSearchConfig.MAX_SCHEMA_KEYS_TO_EXTRACT == 1000
        assert SchemaSearchConfig.INITIAL_READ_SIZE == 1024 * 1024  # 1MB

    def test_constants_are_positive(self):
        """Test all numeric constants are positive."""
        assert SchemaSearchConfig.LARGE_FILE_THRESHOLD > 0
        assert SchemaSearchConfig.HUGE_FILE_THRESHOLD > 0
        assert SchemaSearchConfig.MAX_RESULTS_DEFAULT > 0
        assert SchemaSearchConfig.MAX_RESULTS_LARGE_FILE > 0
        assert SchemaSearchConfig.MAX_PROPERTIES_TO_CHECK > 0
        assert SchemaSearchConfig.MAX_MATCH_LOCATIONS > 0
        assert SchemaSearchConfig.MAX_DESCRIPTION_LENGTH > 0
        assert SchemaSearchConfig.CHUNK_SIZE_NORMAL > 0
        assert SchemaSearchConfig.CHUNK_SIZE_LARGE > 0
        assert SchemaSearchConfig.CHUNK_SIZE_HUGE > 0
        assert SchemaSearchConfig.MAX_SCHEMA_KEYS_TO_EXTRACT > 0
        assert SchemaSearchConfig.INITIAL_READ_SIZE > 0
