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

"""Unit tests for SchemaSearchConfig max results calculation."""

from awslabs.lza_mcp_server.tools.schema.schema_config import SchemaSearchConfig


class TestGetMaxResults:
    """Test max results calculation based on file size."""

    def test_small_file_returns_requested_max(self):
        """Test small file returns requested max results."""
        file_size = 1024 * 1024  # 1MB
        requested_max = 20
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == requested_max

    def test_medium_file_returns_requested_max(self):
        """Test medium file (just under large threshold) returns requested max."""
        file_size = SchemaSearchConfig.LARGE_FILE_THRESHOLD - 1
        requested_max = 15
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == requested_max

    def test_large_file_limits_results(self):
        """Test large file limits results to MAX_RESULTS_LARGE_FILE."""
        file_size = 5 * 1024 * 1024  # 5MB
        requested_max = 20
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == SchemaSearchConfig.MAX_RESULTS_LARGE_FILE

    def test_large_file_threshold_boundary(self):
        """Test file at large threshold boundary limits results."""
        file_size = SchemaSearchConfig.LARGE_FILE_THRESHOLD + 1
        requested_max = 20
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == SchemaSearchConfig.MAX_RESULTS_LARGE_FILE

    def test_large_file_requested_less_than_limit(self):
        """Test large file with requested max less than limit returns requested."""
        file_size = 5 * 1024 * 1024  # 5MB
        requested_max = 3
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == requested_max

    def test_large_file_requested_equal_to_limit(self):
        """Test large file with requested max equal to limit returns limit."""
        file_size = 5 * 1024 * 1024  # 5MB
        requested_max = SchemaSearchConfig.MAX_RESULTS_LARGE_FILE
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == SchemaSearchConfig.MAX_RESULTS_LARGE_FILE

    def test_huge_file_limits_results(self):
        """Test huge file limits results to MAX_RESULTS_LARGE_FILE."""
        file_size = 20 * 1024 * 1024  # 20MB
        requested_max = 50
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == SchemaSearchConfig.MAX_RESULTS_LARGE_FILE

    def test_zero_file_size_returns_requested(self):
        """Test zero file size returns requested max."""
        file_size = 0
        requested_max = 10
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == requested_max

    def test_requested_zero_returns_zero(self):
        """Test requested max of zero returns zero."""
        file_size = 1024 * 1024  # 1MB
        requested_max = 0
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == 0

    def test_large_file_requested_zero_returns_zero(self):
        """Test large file with requested max of zero returns zero."""
        file_size = 5 * 1024 * 1024  # 5MB
        requested_max = 0
        max_results = SchemaSearchConfig.get_max_results(file_size, requested_max)
        assert max_results == 0
