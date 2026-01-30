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

"""Unit tests for network-related validation."""

from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_asn_range,
    validate_vpc_mask_length,
    validate_subnet_mask_length,
    validate_network_model,
)


class TestASNValidation:
    """Test ASN range validation."""

    def test_valid_asn_minimum(self):
        """Test valid ASN at minimum range."""
        is_valid, error = validate_asn_range(64512)
        assert is_valid is True
        assert error == ""

    def test_valid_asn_maximum(self):
        """Test valid ASN at maximum range."""
        is_valid, error = validate_asn_range(65534)
        assert is_valid is True
        assert error == ""

    def test_valid_asn_middle(self):
        """Test valid ASN in middle of range."""
        is_valid, error = validate_asn_range(65000)
        assert is_valid is True
        assert error == ""

    def test_invalid_asn_too_low(self):
        """Test invalid ASN below minimum."""
        is_valid, error = validate_asn_range(64511)
        assert is_valid is False
        assert "out of valid range" in error
        assert "64512" in error
        assert "65534" in error

    def test_invalid_asn_too_high(self):
        """Test invalid ASN above maximum."""
        is_valid, error = validate_asn_range(65535)
        assert is_valid is False
        assert "out of valid range" in error

    def test_invalid_asn_not_integer(self):
        """Test invalid ASN that is not an integer."""
        is_valid, error = validate_asn_range("64512")
        assert is_valid is False
        assert "must be an integer" in error

    def test_invalid_asn_none(self):
        """Test invalid None ASN."""
        is_valid, error = validate_asn_range(None)
        assert is_valid is False
        assert "must be an integer" in error

    def test_invalid_asn_float(self):
        """Test invalid float ASN."""
        is_valid, error = validate_asn_range(64512.5)
        assert is_valid is False
        assert "must be an integer" in error


class TestVPCMaskValidation:
    """Test VPC mask length validation."""

    def test_valid_vpc_mask_minimum(self):
        """Test valid VPC mask at minimum."""
        is_valid, error = validate_vpc_mask_length(16)
        assert is_valid is True
        assert error == ""

    def test_valid_vpc_mask_maximum(self):
        """Test valid VPC mask at maximum."""
        is_valid, error = validate_vpc_mask_length(28)
        assert is_valid is True
        assert error == ""

    def test_valid_vpc_mask_typical(self):
        """Test valid typical VPC mask."""
        is_valid, error = validate_vpc_mask_length(24)
        assert is_valid is True
        assert error == ""

    def test_invalid_vpc_mask_too_small(self):
        """Test invalid VPC mask below minimum."""
        is_valid, error = validate_vpc_mask_length(15)
        assert is_valid is False
        assert "out of reasonable range" in error
        assert "16-28" in error

    def test_invalid_vpc_mask_too_large(self):
        """Test invalid VPC mask above maximum."""
        is_valid, error = validate_vpc_mask_length(29)
        assert is_valid is False
        assert "out of reasonable range" in error

    def test_invalid_vpc_mask_not_integer(self):
        """Test invalid VPC mask that is not an integer."""
        is_valid, error = validate_vpc_mask_length("24")
        assert is_valid is False
        assert "must be an integer" in error

    def test_invalid_vpc_mask_none(self):
        """Test invalid None VPC mask."""
        is_valid, error = validate_vpc_mask_length(None)
        assert is_valid is False
        assert "must be an integer" in error


class TestSubnetMaskValidation:
    """Test subnet mask length validation."""

    def test_valid_subnet_mask(self):
        """Test valid subnet mask larger than VPC mask."""
        is_valid, error = validate_subnet_mask_length(26, 24)
        assert is_valid is True
        assert error == ""

    def test_valid_subnet_mask_maximum(self):
        """Test valid subnet mask at maximum."""
        is_valid, error = validate_subnet_mask_length(28, 24)
        assert is_valid is True
        assert error == ""

    def test_invalid_subnet_mask_equal_to_vpc(self):
        """Test invalid subnet mask equal to VPC mask."""
        is_valid, error = validate_subnet_mask_length(24, 24)
        assert is_valid is False
        assert "must be larger than VPC mask" in error

    def test_invalid_subnet_mask_smaller_than_vpc(self):
        """Test invalid subnet mask smaller than VPC mask."""
        is_valid, error = validate_subnet_mask_length(22, 24)
        assert is_valid is False
        assert "must be larger than VPC mask" in error

    def test_invalid_subnet_mask_too_large(self):
        """Test invalid subnet mask above maximum."""
        is_valid, error = validate_subnet_mask_length(29, 24)
        assert is_valid is False
        assert "too large" in error
        assert "maximum 28" in error

    def test_invalid_subnet_mask_not_integer(self):
        """Test invalid subnet mask that is not an integer."""
        is_valid, error = validate_subnet_mask_length("26", 24)
        assert is_valid is False
        assert "must be integers" in error

    def test_invalid_vpc_mask_not_integer(self):
        """Test invalid VPC mask that is not an integer."""
        is_valid, error = validate_subnet_mask_length(26, "24")
        assert is_valid is False
        assert "must be integers" in error

    def test_invalid_both_masks_not_integer(self):
        """Test invalid when both masks are not integers."""
        is_valid, error = validate_subnet_mask_length("26", "24")
        assert is_valid is False
        assert "must be integers" in error


class TestNetworkModelValidation:
    """Test network model validation."""

    def test_valid_network_model_hub_and_spoke(self):
        """Test valid hub-and-spoke network model."""
        is_valid, error = validate_network_model("hub-and-spoke")
        assert is_valid is True
        assert error == ""

    def test_valid_network_model_simple(self):
        """Test valid simple network model name."""
        is_valid, error = validate_network_model("simple")
        assert is_valid is True
        assert error == ""

    def test_valid_network_model_with_numbers(self):
        """Test valid network model with numbers."""
        is_valid, error = validate_network_model("model-v2")
        assert is_valid is True
        assert error == ""

    def test_valid_network_model_all_lowercase(self):
        """Test valid network model all lowercase."""
        is_valid, error = validate_network_model("mynetworkmodel")
        assert is_valid is True
        assert error == ""

    def test_invalid_network_model_empty(self):
        """Test invalid empty network model."""
        is_valid, error = validate_network_model("")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_network_model_none(self):
        """Test invalid None network model."""
        is_valid, error = validate_network_model(None)
        assert is_valid is False
        assert "cannot be empty" in error

    def test_invalid_network_model_not_string(self):
        """Test invalid network model that is not a string."""
        is_valid, error = validate_network_model(123)
        assert is_valid is False
        assert "must be a string" in error

    def test_invalid_network_model_uppercase(self):
        """Test invalid network model with uppercase."""
        is_valid, error = validate_network_model("Hub-And-Spoke")
        assert is_valid is False
        assert "Invalid network model format" in error
        assert "lowercase" in error

    def test_invalid_network_model_spaces(self):
        """Test invalid network model with spaces."""
        is_valid, error = validate_network_model("hub and spoke")
        assert is_valid is False
        assert "Invalid network model format" in error

    def test_invalid_network_model_special_chars(self):
        """Test invalid network model with special characters."""
        is_valid, error = validate_network_model("hub_and_spoke")
        assert is_valid is False
        assert "Invalid network model format" in error

    def test_invalid_network_model_dots(self):
        """Test invalid network model with dots."""
        is_valid, error = validate_network_model("hub.and.spoke")
        assert is_valid is False
        assert "Invalid network model format" in error
