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

"""Unit tests for SchemaSearchConfig chunk size calculation."""

from awslabs.lza_mcp_server.tools.schema.schema_config import SchemaSearchConfig


class TestGetChunkSize:
    """Test chunk size calculation based on file size."""

    def test_small_file_normal_chunk_size(self):
        """Test small file gets normal chunk size."""
        file_size = 1024 * 1024  # 1MB
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_NORMAL

    def test_medium_file_normal_chunk_size(self):
        """Test medium file (just under large threshold) gets normal chunk size."""
        file_size = SchemaSearchConfig.LARGE_FILE_THRESHOLD - 1
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_NORMAL

    def test_large_file_large_chunk_size(self):
        """Test large file gets large chunk size."""
        file_size = 5 * 1024 * 1024  # 5MB
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_LARGE

    def test_large_file_threshold_boundary(self):
        """Test file at large threshold boundary gets large chunk size."""
        file_size = SchemaSearchConfig.LARGE_FILE_THRESHOLD + 1
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_LARGE

    def test_huge_file_huge_chunk_size(self):
        """Test huge file gets huge chunk size."""
        file_size = 20 * 1024 * 1024  # 20MB
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_HUGE

    def test_huge_file_threshold_boundary(self):
        """Test file at huge threshold boundary gets huge chunk size."""
        file_size = SchemaSearchConfig.HUGE_FILE_THRESHOLD + 1
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_HUGE

    def test_zero_file_size(self):
        """Test zero file size gets normal chunk size."""
        file_size = 0
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_NORMAL

    def test_very_large_file(self):
        """Test very large file (100MB) gets huge chunk size."""
        file_size = 100 * 1024 * 1024  # 100MB
        chunk_size = SchemaSearchConfig.get_chunk_size(file_size)
        assert chunk_size == SchemaSearchConfig.CHUNK_SIZE_HUGE

    def test_chunk_size_decreases_with_file_size(self):
        """Test chunk size decreases as file size increases."""
        small_file = 1024 * 1024  # 1MB
        large_file = 5 * 1024 * 1024  # 5MB
        huge_file = 20 * 1024 * 1024  # 20MB

        small_chunk = SchemaSearchConfig.get_chunk_size(small_file)
        large_chunk = SchemaSearchConfig.get_chunk_size(large_file)
        huge_chunk = SchemaSearchConfig.get_chunk_size(huge_file)

        assert small_chunk > large_chunk > huge_chunk
