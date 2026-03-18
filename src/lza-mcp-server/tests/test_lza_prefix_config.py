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

"""Tests for LZA_PREFIX configuration."""

import os
from unittest.mock import patch


class TestLzaPrefixConfiguration:
    """Test LZA_PREFIX environment variable configuration."""

    def test_default_lza_prefix(self):
        """Test that default LZA_PREFIX is AWSAccelerator."""
        # Clear any existing LZA_PREFIX
        with patch.dict(os.environ, {}, clear=False):
            if "LZA_PREFIX" in os.environ:
                del os.environ["LZA_PREFIX"]

            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            assert constants.LZA_PREFIX == "AWSAccelerator"
            assert constants.DEFAULT_PIPELINE_NAME == "AWSAccelerator-Pipeline"

    def test_custom_lza_prefix(self):
        """Test that custom LZA_PREFIX is respected."""
        with patch.dict(os.environ, {"LZA_PREFIX": "MyOrg"}):
            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            assert constants.LZA_PREFIX == "MyOrg"
            assert constants.DEFAULT_PIPELINE_NAME == "MyOrg-Pipeline"

    def test_lza_prefix_empty_string(self):
        """Test that empty string LZA_PREFIX falls back to default."""
        with patch.dict(os.environ, {"LZA_PREFIX": ""}):
            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            # Empty string should fall back to default to prevent invalid resource names
            assert constants.LZA_PREFIX == "AWSAccelerator"
            assert constants.DEFAULT_PIPELINE_NAME == "AWSAccelerator-Pipeline"

    def test_lza_prefix_whitespace_only(self):
        """Test that whitespace-only LZA_PREFIX falls back to default."""
        with patch.dict(os.environ, {"LZA_PREFIX": "   "}):
            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            # Whitespace-only should fall back to default after stripping
            assert constants.LZA_PREFIX == "AWSAccelerator"
            assert constants.DEFAULT_PIPELINE_NAME == "AWSAccelerator-Pipeline"

    def test_lza_prefix_with_special_characters(self):
        """Test that LZA_PREFIX with special characters is handled."""
        with patch.dict(os.environ, {"LZA_PREFIX": "My-Org_123"}):
            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            assert constants.LZA_PREFIX == "My-Org_123"
            assert constants.DEFAULT_PIPELINE_NAME == "My-Org_123-Pipeline"

    def test_lza_prefix_case_sensitive(self):
        """Test that LZA_PREFIX is case-sensitive."""
        with patch.dict(os.environ, {"LZA_PREFIX": "myorg"}):
            # Reimport to get fresh constants
            import importlib
            from awslabs.lza_mcp_server import constants

            importlib.reload(constants)

            assert constants.LZA_PREFIX == "myorg"
            assert constants.DEFAULT_PIPELINE_NAME == "myorg-Pipeline"
