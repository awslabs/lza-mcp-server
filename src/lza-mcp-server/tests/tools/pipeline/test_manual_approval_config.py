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

"""Unit tests for S3 diff configuration toggle."""

import os
from unittest.mock import patch

from awslabs.lza_mcp_server.server_config import (
    is_s3_diff_enabled,
)


class TestIsS3DiffEnabled:
    """Test is_s3_diff_enabled() configuration toggle."""

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "true"})
    def test_returns_true_for_true(self):
        """Test returns True when env var is 'true'."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "1"})
    def test_returns_true_for_one(self):
        """Test returns True when env var is '1'."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "yes"})
    def test_returns_true_for_yes(self):
        """Test returns True when env var is 'yes'."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "TRUE"})
    def test_returns_true_for_uppercase_true(self):
        """Test returns True when env var is 'TRUE' (case-insensitive)."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "Yes"})
    def test_returns_true_for_mixed_case_yes(self):
        """Test returns True when env var is 'Yes' (case-insensitive)."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "True"})
    def test_returns_true_for_title_case_true(self):
        """Test returns True when env var is 'True' (case-insensitive)."""
        assert is_s3_diff_enabled() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_false_when_unset(self):
        """Test returns False when env var is not set (default disabled)."""
        os.environ.pop("ENABLE_S3_DIFF", None)
        assert is_s3_diff_enabled() is False

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "false"})
    def test_returns_false_for_false(self):
        """Test returns False when env var is 'false'."""
        assert is_s3_diff_enabled() is False

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": ""})
    def test_returns_false_for_empty(self):
        """Test returns False when env var is empty string."""
        assert is_s3_diff_enabled() is False

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "0"})
    def test_returns_false_for_zero(self):
        """Test returns False when env var is '0'."""
        assert is_s3_diff_enabled() is False

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "no"})
    def test_returns_false_for_no(self):
        """Test returns False when env var is 'no'."""
        assert is_s3_diff_enabled() is False

    @patch.dict(os.environ, {"ENABLE_S3_DIFF": "enabled"})
    def test_returns_false_for_other_values(self):
        """Test returns False for unrecognized values."""
        assert is_s3_diff_enabled() is False
