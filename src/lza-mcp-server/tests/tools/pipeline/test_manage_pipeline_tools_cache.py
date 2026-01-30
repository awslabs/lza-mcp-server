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

"""Unit tests for manage_pipeline_tools cache functionality."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools import (
    is_cache_valid,
    get_cached_pipeline_metadata,
    cache_pipeline_metadata,
    clear_pipeline_cache,
    _pipeline_cache,
    _cache_timestamps,
)


class TestCacheValidation:
    """Test cache validation functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_pipeline_cache()

    def test_is_cache_valid_no_entry(self):
        """Test cache validation when entry doesn't exist."""
        result = is_cache_valid("nonexistent_key")
        assert result is False

    def test_is_cache_valid_fresh_entry(self):
        """Test cache validation with fresh entry."""
        cache_key = "test_key"
        _cache_timestamps[cache_key] = datetime.now()

        result = is_cache_valid(cache_key)
        assert result is True

    def test_is_cache_valid_expired_entry(self):
        """Test cache validation with expired entry."""
        cache_key = "test_key"
        # Set timestamp to 10 minutes ago (beyond 5 minute TTL)
        _cache_timestamps[cache_key] = datetime.now() - timedelta(minutes=10)

        result = is_cache_valid(cache_key)
        assert result is False

    def test_is_cache_valid_boundary_case(self):
        """Test cache validation at TTL boundary."""
        cache_key = "test_key"
        # Set timestamp to exactly 5 minutes ago (at TTL boundary)
        _cache_timestamps[cache_key] = datetime.now() - timedelta(seconds=300)

        result = is_cache_valid(cache_key)
        # Should be invalid as it's at or past the TTL
        assert result is False

    def test_is_cache_valid_just_before_expiry(self):
        """Test cache validation just before expiry."""
        cache_key = "test_key"
        # Set timestamp to 4 minutes 59 seconds ago (just before TTL)
        _cache_timestamps[cache_key] = datetime.now() - timedelta(seconds=299)

        result = is_cache_valid(cache_key)
        assert result is True


class TestCacheRetrieval:
    """Test cache retrieval functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_pipeline_cache()

    def test_get_cached_pipeline_metadata_not_cached(self):
        """Test retrieving metadata when not cached."""
        result = get_cached_pipeline_metadata("test-pipeline")
        assert result is None

    def test_get_cached_pipeline_metadata_expired(self):
        """Test retrieving metadata when cache is expired."""
        pipeline_name = "test-pipeline"
        cache_key = f"pipeline_metadata_{pipeline_name}"

        # Cache some data
        metadata = {"status": "InProgress"}
        _pipeline_cache[cache_key] = metadata

        # Set expired timestamp
        _cache_timestamps[cache_key] = datetime.now() - timedelta(minutes=10)

        result = get_cached_pipeline_metadata(pipeline_name)
        assert result is None

    def test_get_cached_pipeline_metadata_valid(self):
        """Test retrieving valid cached metadata."""
        pipeline_name = "test-pipeline"
        cache_key = f"pipeline_metadata_{pipeline_name}"

        # Cache some data
        metadata = {"status": "InProgress", "stages": ["Source", "Build"]}
        _pipeline_cache[cache_key] = metadata
        _cache_timestamps[cache_key] = datetime.now()

        result = get_cached_pipeline_metadata(pipeline_name)
        assert result is not None
        assert result == metadata
        assert result["status"] == "InProgress"
        assert len(result["stages"]) == 2

    def test_get_cached_pipeline_metadata_multiple_pipelines(self):
        """Test retrieving metadata for multiple pipelines."""
        # Cache data for multiple pipelines
        pipeline1 = "pipeline-1"
        pipeline2 = "pipeline-2"

        metadata1 = {"status": "Succeeded"}
        metadata2 = {"status": "Failed"}

        cache_pipeline_metadata(pipeline1, metadata1)
        cache_pipeline_metadata(pipeline2, metadata2)

        # Retrieve and verify
        result1 = get_cached_pipeline_metadata(pipeline1)
        result2 = get_cached_pipeline_metadata(pipeline2)

        assert result1 == metadata1
        assert result2 == metadata2
        assert result1 != result2


class TestCacheStorage:
    """Test cache storage functionality."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_pipeline_cache()

    def test_cache_pipeline_metadata_basic(self):
        """Test basic metadata caching."""
        pipeline_name = "test-pipeline"
        metadata = {"status": "InProgress"}

        cache_pipeline_metadata(pipeline_name, metadata)

        # Verify cache was stored
        cache_key = f"pipeline_metadata_{pipeline_name}"
        assert cache_key in _pipeline_cache
        assert _pipeline_cache[cache_key] == metadata
        assert cache_key in _cache_timestamps

    def test_cache_pipeline_metadata_overwrites_existing(self):
        """Test that caching overwrites existing data."""
        pipeline_name = "test-pipeline"
        old_metadata = {"status": "InProgress"}
        new_metadata = {"status": "Succeeded"}

        # Cache initial data
        cache_pipeline_metadata(pipeline_name, old_metadata)

        # Cache new data
        cache_pipeline_metadata(pipeline_name, new_metadata)

        # Verify new data replaced old data
        result = get_cached_pipeline_metadata(pipeline_name)
        assert result == new_metadata
        assert result != old_metadata

    def test_cache_pipeline_metadata_updates_timestamp(self):
        """Test that caching updates timestamp."""
        pipeline_name = "test-pipeline"
        metadata = {"status": "InProgress"}

        # Cache data
        cache_pipeline_metadata(pipeline_name, metadata)
        cache_key = f"pipeline_metadata_{pipeline_name}"
        first_timestamp = _cache_timestamps[cache_key]

        # Wait a moment and cache again
        time.sleep(0.1)
        cache_pipeline_metadata(pipeline_name, metadata)
        second_timestamp = _cache_timestamps[cache_key]

        # Verify timestamp was updated
        assert second_timestamp > first_timestamp

    def test_cache_pipeline_metadata_complex_data(self):
        """Test caching complex metadata structures."""
        pipeline_name = "test-pipeline"
        metadata = {
            "status": "InProgress",
            "stages": [
                {"name": "Source", "status": "Succeeded"},
                {"name": "Build", "status": "InProgress"},
            ],
            "execution_id": "12345678-1234-1234-1234-123456789012",
            "nested": {"key": "value", "list": [1, 2, 3]},
        }

        cache_pipeline_metadata(pipeline_name, metadata)

        result = get_cached_pipeline_metadata(pipeline_name)
        assert result == metadata
        assert len(result["stages"]) == 2
        assert result["nested"]["list"] == [1, 2, 3]


class TestCacheClearing:
    """Test cache clearing functionality."""

    def test_clear_pipeline_cache_empty(self):
        """Test clearing empty cache."""
        clear_pipeline_cache()

        assert len(_pipeline_cache) == 0
        assert len(_cache_timestamps) == 0

    def test_clear_pipeline_cache_with_data(self):
        """Test clearing cache with data."""
        # Add some data
        cache_pipeline_metadata("pipeline-1", {"status": "InProgress"})
        cache_pipeline_metadata("pipeline-2", {"status": "Succeeded"})

        # Verify data exists
        assert len(_pipeline_cache) == 2
        assert len(_cache_timestamps) == 2

        # Clear cache
        clear_pipeline_cache()

        # Verify cache is empty
        assert len(_pipeline_cache) == 0
        assert len(_cache_timestamps) == 0

    def test_clear_pipeline_cache_multiple_times(self):
        """Test clearing cache multiple times."""
        # Add data and clear
        cache_pipeline_metadata("pipeline-1", {"status": "InProgress"})
        clear_pipeline_cache()

        # Add more data and clear again
        cache_pipeline_metadata("pipeline-2", {"status": "Succeeded"})
        clear_pipeline_cache()

        # Verify cache is empty
        assert len(_pipeline_cache) == 0
        assert len(_cache_timestamps) == 0


class TestCacheIntegration:
    """Test cache integration scenarios."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_pipeline_cache()

    def test_cache_workflow_complete(self):
        """Test complete cache workflow: store, retrieve, expire, clear."""
        pipeline_name = "test-pipeline"
        metadata = {"status": "InProgress"}

        # Store
        cache_pipeline_metadata(pipeline_name, metadata)

        # Retrieve (should succeed)
        result = get_cached_pipeline_metadata(pipeline_name)
        assert result == metadata

        # Expire by manipulating timestamp
        cache_key = f"pipeline_metadata_{pipeline_name}"
        _cache_timestamps[cache_key] = datetime.now() - timedelta(minutes=10)

        # Retrieve (should fail due to expiry)
        result = get_cached_pipeline_metadata(pipeline_name)
        assert result is None

        # Clear
        clear_pipeline_cache()
        assert len(_pipeline_cache) == 0

    def test_cache_isolation_between_pipelines(self):
        """Test that cache entries for different pipelines are isolated."""
        pipeline1 = "pipeline-1"
        pipeline2 = "pipeline-2"

        metadata1 = {"status": "InProgress"}
        metadata2 = {"status": "Succeeded"}

        # Cache both
        cache_pipeline_metadata(pipeline1, metadata1)
        cache_pipeline_metadata(pipeline2, metadata2)

        # Expire only pipeline1
        cache_key1 = f"pipeline_metadata_{pipeline1}"
        _cache_timestamps[cache_key1] = datetime.now() - timedelta(minutes=10)

        # Verify pipeline1 is expired but pipeline2 is still valid
        result1 = get_cached_pipeline_metadata(pipeline1)
        result2 = get_cached_pipeline_metadata(pipeline2)

        assert result1 is None
        assert result2 == metadata2

    @patch("awslabs.lza_mcp_server.tools.pipeline.manage_pipeline_tools.logger")
    def test_cache_logging(self, mock_logger):
        """Test that cache operations log appropriately."""
        pipeline_name = "test-pipeline"
        metadata = {"status": "InProgress"}

        # Cache data
        cache_pipeline_metadata(pipeline_name, metadata)

        # Verify logging occurred
        mock_logger.debug.assert_called()
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert any("Cached pipeline metadata" in call for call in debug_calls)

        # Retrieve cached data
        get_cached_pipeline_metadata(pipeline_name)

        # Verify retrieval logging
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert any("Using cached pipeline metadata" in call for call in debug_calls)
