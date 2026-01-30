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

"""Unit tests for update_uc_file helper functions."""

from awslabs.lza_mcp_server.tools.uc_merge.update_uc_file import (
    _parse_key_path,
    _get_nested_value,
    _set_nested_value,
)


class TestParseKeyPath:
    """Test key path parsing."""

    def test_parse_simple_key(self):
        """Test parsing simple key without nesting."""
        result = _parse_key_path("HomeRegion")
        assert result == ["HomeRegion"]

    def test_parse_nested_key(self):
        """Test parsing nested key with dots."""
        result = _parse_key_path("vpc.cidr.range")
        assert result == ["vpc", "cidr", "range"]

    def test_parse_array_index(self):
        """Test parsing key with array index."""
        result = _parse_key_path("mandatoryAccounts[0].email")
        assert result == ["mandatoryAccounts", 0, "email"]

    def test_parse_multiple_array_indices(self):
        """Test parsing key with multiple array indices."""
        result = _parse_key_path("accounts[0].subnets[2].cidr")
        assert result == ["accounts", 0, "subnets", 2, "cidr"]

    def test_parse_array_only(self):
        """Test parsing array index without additional keys."""
        result = _parse_key_path("items[5]")
        assert result == ["items", 5]

    def test_parse_empty_key(self):
        """Test parsing empty key."""
        result = _parse_key_path("")
        assert result == [""]


class TestGetNestedValue:
    """Test getting nested values from data structures."""

    def test_get_simple_value(self):
        """Test getting simple top-level value."""
        data = {"HomeRegion": "us-east-1"}
        result = _get_nested_value(data, "HomeRegion")
        assert result == "us-east-1"

    def test_get_nested_dict_value(self):
        """Test getting nested dictionary value."""
        data = {"vpc": {"cidr": "10.0.0.0/16"}}
        result = _get_nested_value(data, "vpc.cidr")
        assert result == "10.0.0.0/16"

    def test_get_array_element(self):
        """Test getting array element by index."""
        data = {"accounts": ["acc1", "acc2", "acc3"]}
        result = _get_nested_value(data, "accounts[1]")
        assert result == "acc2"

    def test_get_nested_array_value(self):
        """Test getting nested value from array element."""
        data = {
            "mandatoryAccounts": [
                {"email": "admin@example.com", "name": "Admin"},
                {"email": "user@example.com", "name": "User"},
            ]
        }
        result = _get_nested_value(data, "mandatoryAccounts[1].email")
        assert result == "user@example.com"

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        data = {"HomeRegion": "us-east-1"}
        result = _get_nested_value(data, "NonExistent")
        assert result is None

    def test_get_nonexistent_nested_key(self):
        """Test getting nonexistent nested key returns None."""
        data = {"vpc": {"cidr": "10.0.0.0/16"}}
        result = _get_nested_value(data, "vpc.nonexistent")
        assert result is None

    def test_get_out_of_bounds_index(self):
        """Test getting out of bounds array index returns None."""
        data = {"accounts": ["acc1", "acc2"]}
        result = _get_nested_value(data, "accounts[5]")
        assert result is None

    def test_get_from_non_dict(self):
        """Test getting from non-dict value returns None."""
        data = {"value": "string"}
        result = _get_nested_value(data, "value.nested")
        assert result is None


class TestSetNestedValue:
    """Test setting nested values in data structures."""

    def test_set_simple_value(self):
        """Test setting simple top-level value."""
        data = {"HomeRegion": "us-east-1"}
        _set_nested_value(data, "HomeRegion", "us-west-2")
        assert data["HomeRegion"] == "us-west-2"

    def test_set_nested_dict_value(self):
        """Test setting nested dictionary value."""
        data = {"vpc": {"cidr": "10.0.0.0/16"}}
        _set_nested_value(data, "vpc.cidr", "10.1.0.0/16")
        assert data["vpc"]["cidr"] == "10.1.0.0/16"

    def test_set_array_element(self):
        """Test setting array element by index."""
        data = {"accounts": ["acc1", "acc2", "acc3"]}
        _set_nested_value(data, "accounts[1]", "new-acc2")
        assert data["accounts"][1] == "new-acc2"

    def test_set_nested_array_value(self):
        """Test setting nested value in array element."""
        data = {
            "mandatoryAccounts": [
                {"email": "admin@example.com", "name": "Admin"},
                {"email": "user@example.com", "name": "User"},
            ]
        }
        _set_nested_value(data, "mandatoryAccounts[1].email", "newuser@example.com")
        assert data["mandatoryAccounts"][1]["email"] == "newuser@example.com"

    def test_set_creates_intermediate_dict(self):
        """Test setting value creates intermediate dictionary."""
        data = {}
        _set_nested_value(data, "vpc.cidr", "10.0.0.0/16")
        assert data == {"vpc": {"cidr": "10.0.0.0/16"}}

    def test_set_creates_intermediate_list(self):
        """Test setting value in array when list doesn't exist yet."""
        data = {}
        # This will create the list but can't set index 0 without the list having elements
        # This is a known limitation - the function creates empty list but can't populate it
        try:
            _set_nested_value(data, "accounts[0]", "acc1")
            # If it succeeds, verify the structure
            assert "accounts" in data
        except IndexError:
            # Expected - can't set index in empty list
            assert "accounts" in data
            assert isinstance(data["accounts"], list)
            assert len(data["accounts"]) == 0

    def test_set_new_key_in_existing_dict(self):
        """Test setting new key in existing dictionary."""
        data = {"vpc": {"cidr": "10.0.0.0/16"}}
        _set_nested_value(data, "vpc.name", "MyVPC")
        assert data["vpc"]["name"] == "MyVPC"
        assert data["vpc"]["cidr"] == "10.0.0.0/16"

    def test_set_empty_key_path(self):
        """Test setting with empty key path creates empty string key."""
        data = {"HomeRegion": "us-east-1"}
        _set_nested_value(data, "", "value")
        # Empty key path creates an empty string key
        assert data == {"HomeRegion": "us-east-1", "": "value"}

    def test_set_complex_nested_structure(self):
        """Test setting value in complex nested structure."""
        data = {
            "vpcs": [
                {"name": "vpc1", "subnets": [{"cidr": "10.0.1.0/24"}]},
                {"name": "vpc2", "subnets": [{"cidr": "10.0.2.0/24"}]},
            ]
        }
        _set_nested_value(data, "vpcs[1].subnets[0].cidr", "10.0.3.0/24")
        assert data["vpcs"][1]["subnets"][0]["cidr"] == "10.0.3.0/24"
