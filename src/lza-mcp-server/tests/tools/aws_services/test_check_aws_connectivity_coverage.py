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

"""Additional coverage tests for check_aws_connectivity."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity import (
    tool_check_aws_connectivity,
)

_SESSION = (
    "awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity.get_aws_session"
)
_DETECT = "awslabs.lza_mcp_server.tools.aws_services.check_aws_connectivity.detect_lza_deployment"


def _make_ctx():
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


class TestDeploymentDetectionInconclusive:
    """Test the deployment detection inconclusive branch."""

    @pytest.mark.asyncio
    @patch(_DETECT)
    @patch(_SESSION)
    async def test_deployment_detection_not_successful(self, mock_session, mock_detect):
        """Test when deployment detection returns success=False — inconclusive message."""
        ctx = _make_ctx()
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDA123",
        }
        session = Mock()
        session.client.return_value = mock_sts
        mock_session.return_value = session

        mock_detect.return_value = {
            "success": False,
            "message": "No LZA deployment detected",
            "deployment_type": "unknown",
        }

        result = await tool_check_aws_connectivity(ctx)

        assert result["connected"] is True
        assert result["deployment"]["success"] is False
        # Verify the inconclusive info message was sent
        ctx.info.assert_any_call(
            "Deployment detection inconclusive: No LZA deployment detected"
        )
