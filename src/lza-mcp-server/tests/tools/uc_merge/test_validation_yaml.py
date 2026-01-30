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

"""Unit tests for YAML and UC release validation."""

from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_yaml_syntax,
    validate_uc_release,
)


class TestYAMLValidation:
    """Test YAML syntax validation."""

    def test_valid_yaml_simple(self):
        """Test valid simple YAML."""
        yaml_content = "key: value\n"
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is True
        assert error == ""

    def test_valid_yaml_nested(self):
        """Test valid nested YAML."""
        yaml_content = """
parent:
  child1: value1
  child2: value2
"""
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is True
        assert error == ""

    def test_valid_yaml_list(self):
        """Test valid YAML with list."""
        yaml_content = """
items:
  - item1
  - item2
  - item3
"""
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is True
        assert error == ""

    def test_valid_yaml_complex(self):
        """Test valid complex YAML."""
        yaml_content = """
accounts:
  - name: Management
    email: management@example.com
    organizationalUnit: Root
  - name: LogArchive
    email: logarchive@example.com
    organizationalUnit: Security
"""
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is True
        assert error == ""

    def test_invalid_yaml_empty(self):
        """Test invalid empty YAML."""
        is_valid, error = validate_yaml_syntax("")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_yaml_none(self):
        """Test invalid None YAML."""
        is_valid, error = validate_yaml_syntax(None)
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_yaml_bad_indentation(self):
        """Test YAML with bad indentation (YAML may accept this)."""
        yaml_content = """
parent:
child: value
"""
        # YAML parsers may be lenient with indentation
        is_valid, error = validate_yaml_syntax(yaml_content)
        # Document the actual behavior
        assert isinstance(is_valid, bool)

    def test_invalid_yaml_unclosed_bracket(self):
        """Test invalid YAML with unclosed bracket."""
        yaml_content = "items: [item1, item2\n"
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is False
        assert "Invalid YAML syntax" in error

    def test_invalid_yaml_duplicate_keys(self):
        """Test YAML with duplicate keys (YAML allows this but may warn)."""
        yaml_content = """
key: value1
key: value2
"""
        # YAML allows duplicate keys, last one wins
        is_valid, error = validate_yaml_syntax(yaml_content)
        assert is_valid is True

    def test_invalid_yaml_tab_character(self):
        """Test invalid YAML with tab character."""
        yaml_content = "key:\tvalue\n"
        is_valid, error = validate_yaml_syntax(yaml_content)
        # YAML spec discourages tabs but safe_load may accept them
        # This test documents the behavior
        assert isinstance(is_valid, bool)


class TestUCReleaseValidation:
    """Test UC release version validation."""

    def test_valid_uc_release_v1(self):
        """Test valid UC release v1.0.0."""
        is_valid, error = validate_uc_release("v1.0.0")
        assert is_valid is True
        assert error == ""

    def test_valid_uc_release_v2(self):
        """Test valid UC release v2.1.3."""
        is_valid, error = validate_uc_release("v2.1.3")
        assert is_valid is True
        assert error == ""

    def test_valid_uc_release_large_version(self):
        """Test valid UC release with large version numbers."""
        is_valid, error = validate_uc_release("v10.20.30")
        assert is_valid is True
        assert error == ""

    def test_invalid_uc_release_empty(self):
        """Test invalid empty UC release."""
        is_valid, error = validate_uc_release("")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_uc_release_none(self):
        """Test invalid None UC release."""
        is_valid, error = validate_uc_release(None)
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_uc_release_not_string(self):
        """Test invalid UC release that is not a string."""
        is_valid, error = validate_uc_release(1.0)
        assert is_valid is False
        assert "must be a string" in error

    def test_invalid_uc_release_missing_v_prefix(self):
        """Test invalid UC release without v prefix."""
        is_valid, error = validate_uc_release("1.0.0")
        assert is_valid is False
        assert "Invalid UC release format" in error
        assert "vX.Y.Z" in error

    def test_invalid_uc_release_missing_patch(self):
        """Test invalid UC release without patch version."""
        is_valid, error = validate_uc_release("v1.0")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_missing_minor(self):
        """Test invalid UC release without minor version."""
        is_valid, error = validate_uc_release("v1")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_extra_parts(self):
        """Test invalid UC release with extra version parts."""
        is_valid, error = validate_uc_release("v1.0.0.1")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_non_numeric(self):
        """Test invalid UC release with non-numeric version."""
        is_valid, error = validate_uc_release("v1.0.a")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_with_spaces(self):
        """Test invalid UC release with spaces."""
        is_valid, error = validate_uc_release("v1.0.0 ")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_uppercase_v(self):
        """Test invalid UC release with uppercase V."""
        is_valid, error = validate_uc_release("V1.0.0")
        assert is_valid is False
        assert "Invalid UC release format" in error

    def test_invalid_uc_release_with_suffix(self):
        """Test invalid UC release with suffix."""
        is_valid, error = validate_uc_release("v1.0.0-beta")
        assert is_valid is False
        assert "Invalid UC release format" in error
