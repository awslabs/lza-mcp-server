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

"""Unit tests for CIDR validation."""

from awslabs.lza_mcp_server.tools.uc_merge.validation import validate_cidr_format


class TestCIDRValidation:
    """Test CIDR format validation."""

    def test_valid_cidr_class_a(self):
        """Test valid Class A CIDR."""
        is_valid, error = validate_cidr_format("10.0.0.0/8")
        assert is_valid is True
        assert error == ""

    def test_valid_cidr_class_b(self):
        """Test valid Class B CIDR."""
        is_valid, error = validate_cidr_format("172.16.0.0/16")
        assert is_valid is True
        assert error == ""

    def test_valid_cidr_class_c(self):
        """Test valid Class C CIDR."""
        is_valid, error = validate_cidr_format("192.168.1.0/24")
        assert is_valid is True
        assert error == ""

    def test_valid_cidr_single_host(self):
        """Test valid single host CIDR."""
        is_valid, error = validate_cidr_format("10.0.0.1/32")
        assert is_valid is True
        assert error == ""

    def test_valid_cidr_minimum_mask(self):
        """Test valid CIDR with minimum mask."""
        is_valid, error = validate_cidr_format("0.0.0.0/0")
        assert is_valid is True
        assert error == ""

    def test_invalid_cidr_empty_string(self):
        """Test invalid empty CIDR."""
        is_valid, error = validate_cidr_format("")
        assert is_valid is False
        assert "non-empty string" in error

    def test_invalid_cidr_none(self):
        """Test invalid None CIDR."""
        is_valid, error = validate_cidr_format(None)
        assert is_valid is False
        assert "non-empty string" in error

    def test_invalid_cidr_not_string(self):
        """Test invalid non-string CIDR."""
        is_valid, error = validate_cidr_format(123)
        assert is_valid is False
        assert "non-empty string" in error

    def test_invalid_cidr_missing_slash(self):
        """Test invalid CIDR without slash."""
        is_valid, error = validate_cidr_format("10.0.0.0")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_missing_mask(self):
        """Test invalid CIDR with missing mask."""
        is_valid, error = validate_cidr_format("10.0.0.0/")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_missing_ip(self):
        """Test invalid CIDR with missing IP."""
        is_valid, error = validate_cidr_format("/24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_too_few_octets(self):
        """Test invalid CIDR with too few octets."""
        is_valid, error = validate_cidr_format("10.0.0/24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_too_many_octets(self):
        """Test invalid CIDR with too many octets."""
        is_valid, error = validate_cidr_format("10.0.0.0.0/24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_octet_too_large(self):
        """Test invalid CIDR with octet > 255."""
        is_valid, error = validate_cidr_format("10.0.256.0/24")
        assert is_valid is False
        assert "out of range" in error

    def test_invalid_cidr_octet_negative(self):
        """Test invalid CIDR with negative octet."""
        is_valid, error = validate_cidr_format("10.0.-1.0/24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_mask_too_large(self):
        """Test invalid CIDR with mask > 32."""
        is_valid, error = validate_cidr_format("10.0.0.0/33")
        assert is_valid is False
        assert "out of range" in error

    def test_invalid_cidr_mask_negative(self):
        """Test invalid CIDR with negative mask."""
        is_valid, error = validate_cidr_format("10.0.0.0/-1")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_non_numeric_octet(self):
        """Test invalid CIDR with non-numeric octet."""
        is_valid, error = validate_cidr_format("10.0.abc.0/24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_non_numeric_mask(self):
        """Test invalid CIDR with non-numeric mask."""
        is_valid, error = validate_cidr_format("10.0.0.0/abc")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_with_spaces(self):
        """Test invalid CIDR with spaces."""
        is_valid, error = validate_cidr_format("10.0.0.0 / 24")
        assert is_valid is False
        assert "Invalid CIDR format" in error

    def test_invalid_cidr_with_extra_characters(self):
        """Test invalid CIDR with extra characters."""
        is_valid, error = validate_cidr_format("10.0.0.0/24extra")
        assert is_valid is False
        assert "Invalid CIDR format" in error
