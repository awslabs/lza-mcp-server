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

"""Shared test fixtures for LZA MCP Server tests."""

import pytest


class MockMCPContext:
    """Mock MCP context for testing."""

    def __init__(self):
        self.info_messages = []
        self.error_messages = []

    async def info(self, message):
        """Mock info logging."""
        self.info_messages.append(message)

    async def error(self, message):
        """Mock error logging."""
        self.error_messages.append(message)


@pytest.fixture
def mock_mcp_context():
    """Provide a mock MCP context for testing."""
    return MockMCPContext()
