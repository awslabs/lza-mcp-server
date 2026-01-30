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

"""Unit tests for get_full_schema helper functions."""

import pytest
import json
import tempfile
import os

from awslabs.lza_mcp_server.tools.schema.get_full_schema import (
    _load_combined_schemas,
    _navigate_to_property,
    _build_property_result,
    _build_full_schema_result,
)


class TestLoadCombinedSchemas:
    """Test _load_combined_schemas helper function."""

    def test_load_valid_json_file(self):
        """Test loading a valid JSON file."""
        test_data = {"schema1": {"type": "object"}, "schema2": {"type": "string"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = tmp.name

        try:
            result = _load_combined_schemas(tmp_path)
            assert result == test_data
            assert "schema1" in result
            assert "schema2" in result
        finally:
            os.unlink(tmp_path)

    def test_load_empty_json_file(self):
        """Test loading an empty JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({}, tmp)
            tmp_path = tmp.name

        try:
            result = _load_combined_schemas(tmp_path)
            assert result == {}
        finally:
            os.unlink(tmp_path)

    def test_load_nonexistent_file(self):
        """Test loading a nonexistent file raises exception."""
        with pytest.raises(FileNotFoundError):
            _load_combined_schemas("/nonexistent/path/file.json")

    def test_load_invalid_json_file(self):
        """Test loading an invalid JSON file raises exception."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("invalid json content {")
            tmp_path = tmp.name

        try:
            with pytest.raises(json.JSONDecodeError):
                _load_combined_schemas(tmp_path)
        finally:
            os.unlink(tmp_path)


class TestNavigateToProperty:
    """Test _navigate_to_property helper function."""

    def test_navigate_simple_property(self):
        """Test navigating to a simple top-level property."""
        schema = {"name": {"type": "string"}, "age": {"type": "number"}}

        result = _navigate_to_property(schema, "name")
        assert result == {"type": "string"}

    def test_navigate_nested_property(self):
        """Test navigating to a nested property."""
        schema = {
            "user": {
                "properties": {"name": {"type": "string"}, "age": {"type": "number"}}
            }
        }

        result = _navigate_to_property(schema, "user.name")
        assert result == {"type": "string"}

    def test_navigate_through_properties_key(self):
        """Test navigating through properties key."""
        schema = {"properties": {"user": {"properties": {"name": {"type": "string"}}}}}

        result = _navigate_to_property(schema, "user.name")
        assert result == {"type": "string"}

    def test_navigate_through_items(self):
        """Test navigating through items in array schema."""
        schema = {"items": {"name": {"type": "string"}}}

        result = _navigate_to_property(schema, "name")
        assert result == {"type": "string"}

    def test_navigate_array_notation(self):
        """Test navigating with array notation."""
        schema = {"items": [{"type": "string"}, {"type": "number"}]}

        result = _navigate_to_property(schema, "items[0]")
        assert isinstance(result, list)

    def test_navigate_deep_nested_path(self):
        """Test navigating a deeply nested path."""
        schema = {
            "properties": {
                "level1": {
                    "properties": {
                        "level2": {"properties": {"level3": {"type": "string"}}}
                    }
                }
            }
        }

        result = _navigate_to_property(schema, "level1.level2.level3")
        assert result == {"type": "string"}

    def test_navigate_property_not_found(self):
        """Test navigation fails when property doesn't exist."""
        schema = {"name": {"type": "string"}}

        with pytest.raises(ValueError) as exc_info:
            _navigate_to_property(schema, "nonexistent")

        assert "not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_navigate_partial_path_not_found(self):
        """Test navigation fails when intermediate path doesn't exist."""
        schema = {"user": {"properties": {"name": {"type": "string"}}}}

        with pytest.raises(ValueError) as exc_info:
            _navigate_to_property(schema, "user.nonexistent")

        assert "not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_navigate_shows_available_properties(self):
        """Test error message shows available properties."""
        schema = {"name": {"type": "string"}, "age": {"type": "number"}}

        with pytest.raises(ValueError) as exc_info:
            _navigate_to_property(schema, "invalid")

        error_msg = str(exc_info.value)
        assert "Available:" in error_msg


class TestBuildPropertyResult:
    """Test _build_property_result helper function."""

    def test_build_result_without_metadata(self):
        """Test building result without metadata."""
        result = _build_property_result(
            schema_path="test-schema.json",
            property_path="user.name",
            property_node={"type": "string"},
            target_schema={"properties": {}},
            include_metadata=False,
        )

        assert result["success"] is True
        assert result["schema_path"] == "test-schema.json"
        assert result["property_path"] == "user.name"
        assert result["property"] == {"type": "string"}
        assert "schema_metadata" not in result

    def test_build_result_with_metadata(self):
        """Test building result with metadata."""
        metadata = {"version": "1.0", "description": "Test schema"}
        target_schema = {"properties": {}, "_metadata": metadata}

        result = _build_property_result(
            schema_path="test-schema.json",
            property_path="user.name",
            property_node={"type": "string"},
            target_schema=target_schema,
            include_metadata=True,
        )

        assert result["success"] is True
        assert result["schema_metadata"] == metadata

    def test_build_result_metadata_not_present(self):
        """Test building result when metadata key doesn't exist."""
        result = _build_property_result(
            schema_path="test-schema.json",
            property_path="user.name",
            property_node={"type": "string"},
            target_schema={"properties": {}},
            include_metadata=True,
        )

        assert result["success"] is True
        assert "schema_metadata" not in result


class TestBuildFullSchemaResult:
    """Test _build_full_schema_result helper function."""

    def test_build_result_without_metadata(self):
        """Test building full schema result without metadata."""
        target_schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        result = _build_full_schema_result(
            schema_path="test-schema.json",
            target_schema=target_schema,
            include_metadata=False,
            lza_version="v1.12.0",
        )

        assert result["success"] is True
        assert result["lza_version"] == "v1.12.0"
        assert result["schema_path"] == "test-schema.json"
        assert result["schema"] == target_schema
        assert "metadata" not in result

    def test_build_result_with_metadata(self):
        """Test building full schema result with metadata."""
        metadata = {"version": "1.0", "description": "Test schema"}
        target_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "_metadata": metadata,
        }

        result = _build_full_schema_result(
            schema_path="test-schema.json",
            target_schema=target_schema,
            include_metadata=True,
            lza_version="v1.12.0",
        )

        assert result["success"] is True
        assert result["metadata"] == metadata
        assert "_metadata" not in result["schema"]

    def test_build_result_excludes_metadata_from_schema(self):
        """Test that _metadata is excluded from schema copy."""
        target_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "_metadata": {"version": "1.0"},
        }

        result = _build_full_schema_result(
            schema_path="test-schema.json",
            target_schema=target_schema,
            include_metadata=False,
            lza_version="v1.12.0",
        )

        assert "_metadata" not in result["schema"]
        assert "type" in result["schema"]
        assert "properties" in result["schema"]

    def test_build_result_metadata_not_present(self):
        """Test building result when metadata key doesn't exist."""
        target_schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        result = _build_full_schema_result(
            schema_path="test-schema.json",
            target_schema=target_schema,
            include_metadata=True,
            lza_version="v1.12.0",
        )

        assert result["success"] is True
        assert "metadata" not in result
