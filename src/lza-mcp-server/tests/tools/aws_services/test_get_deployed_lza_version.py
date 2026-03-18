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

"""Unit tests for get_deployed_lza_version MCP tool.

The tool now delegates to detect_lza_deployment + detect_deployment_version,
so these tests mock those two functions and verify the tool's orchestration.
"""

import pytest
from unittest.mock import Mock, patch

from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_version import (
    tool_get_deployed_lza_version,
)


class MockContext:
    """Mock MCP context for testing."""

    async def info(self, message):
        pass

    async def error(self, message):
        pass


# Patch targets
_PATCH_SESSION = "awslabs.lza_mcp_server.tools.aws_services.detect_deployment_version.get_aws_session"
_PATCH_DETECT_DEPLOY = "awslabs.lza_mcp_server.tools.aws_services.detect_deployment_version.detect_lza_deployment"
_PATCH_DETECT_VERSION = "awslabs.lza_mcp_server.tools.aws_services.detect_deployment_version.detect_deployment_version"


def _mock_session(account_id="123456789012"):
    """Create a mock session with STS returning the given account ID."""
    session = Mock()
    sts = Mock()
    sts.get_caller_identity.return_value = {
        "Account": account_id,
        "Arn": f"arn:aws:iam::{account_id}:user/test-user",
        "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    }
    session.client.return_value = sts
    return session


class TestGetDeployedLzaVersion:
    """Test cases for the MCP tool orchestration."""

    @pytest.mark.asyncio
    async def test_standard_deployment_success(self):
        ctx = MockContext()
        session = _mock_session()

        deployment = {"success": True, "deployment_type": "standard"}
        version_result = {
            "success": True,
            "version": "v1.14.4",
            "raw_version": "1.14.4",
            "deployment_type": "standard",
            "region": "eu-north-1",
            "parameter_name": "/accelerator/AWSAccelerator-InstallerStack/version",
            "last_modified": "2026-01-15T12:00:00",
            "message": "LZA version v1.14.4 detected in region eu-north-1",
        }

        with (
            patch(_PATCH_SESSION, return_value=session),
            patch(_PATCH_DETECT_DEPLOY, return_value=deployment),
            patch(_PATCH_DETECT_VERSION, return_value=version_result),
        ):
            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is True
        assert result["version"] == "v1.14.4"
        assert result["account_id"] == "123456789012"
        assert (
            result["note"]
            == "Version is normalized with 'v' prefix for schema compatibility"
        )

    @pytest.mark.asyncio
    async def test_external_pipeline_success(self):
        ctx = MockContext()
        session = _mock_session(account_id="772412007728")

        deployment = {
            "success": True,
            "deployment_type": "external_pipeline",
            "qualifier_names": ["container-dev-1"],
        }
        version_result = {
            "success": True,
            "version": "v1.15.0-rc.10",
            "raw_version": "1.15.0-rc.10",
            "deployment_type": "external_pipeline",
            "region": "eu-north-1",
            "parameter_name": "/accelerator/container-dev-1/AWSAccelerator-InstallerContainerStack/version",
            "qualifier_versions": [
                {
                    "qualifier": "container-dev-1",
                    "success": True,
                    "version": "v1.15.0-rc.10",
                }
            ],
            "message": "LZA version v1.15.0-rc.10 detected",
        }

        with (
            patch(_PATCH_SESSION, return_value=session),
            patch(_PATCH_DETECT_DEPLOY, return_value=deployment),
            patch(_PATCH_DETECT_VERSION, return_value=version_result),
        ):
            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is True
        assert result["version"] == "v1.15.0-rc.10"
        assert result["account_id"] == "772412007728"

    @pytest.mark.asyncio
    async def test_deployment_detection_failure(self):
        ctx = MockContext()
        session = _mock_session()

        deployment = {
            "success": False,
            "deployment_type": None,
            "message": "No LZA deployment detected",
            "troubleshooting": ["Check region"],
        }

        with (
            patch(_PATCH_SESSION, return_value=session),
            patch(_PATCH_DETECT_DEPLOY, return_value=deployment),
        ):
            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is False
        assert result["account_id"] == "123456789012"
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_version_detection_failure(self):
        ctx = MockContext()
        session = _mock_session()

        deployment = {"success": True, "deployment_type": "standard"}
        version_result = {
            "success": False,
            "version": None,
            "deployment_type": "standard",
            "message": "No installer version parameter found",
            "troubleshooting": ["Check SSM"],
        }

        with (
            patch(_PATCH_SESSION, return_value=session),
            patch(_PATCH_DETECT_DEPLOY, return_value=deployment),
            patch(_PATCH_DETECT_VERSION, return_value=version_result),
        ):
            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is False
        assert result["account_id"] == "123456789012"

    @pytest.mark.asyncio
    async def test_aws_connectivity_failure(self):
        ctx = MockContext()

        with patch(_PATCH_SESSION) as mock_get_session:
            session = Mock()
            sts = Mock()
            sts.get_caller_identity.side_effect = Exception("Connection error")
            session.client.return_value = sts
            mock_get_session.return_value = session

            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        ctx = MockContext()

        with patch(_PATCH_SESSION, side_effect=Exception("Unexpected error")):
            result = await tool_get_deployed_lza_version(ctx)

        assert result["success"] is False
        assert "Unexpected error" in result["message"]
        assert "troubleshooting" in result
