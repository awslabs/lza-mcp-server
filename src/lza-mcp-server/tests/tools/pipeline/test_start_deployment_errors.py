"""Unit tests for start_deployment error handling."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.pipeline.start_deployment import tool_start_deployment

_CP = "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_codepipeline_client"
_SSM = "awslabs.lza_mcp_server.tools.pipeline.start_deployment.get_ssm_client"
_RETRY = "awslabs.lza_mcp_server.tools.pipeline.start_deployment.retry_with_exponential_backoff"


def _ctx():
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _ce(code, msg="err"):
    return ClientError({"Error": {"Code": code, "Message": msg}}, "op")


class TestStandardErrors:
    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_pipeline_not_found(self, mock_retry, mock_cp):
        mock_cp.return_value = Mock()
        mock_retry.side_effect = _ce("PipelineNotFoundException")
        r = await tool_start_deployment(_ctx(), pipeline_name="Bad")
        assert r["success"] is False
        assert r["error_code"] == "PipelineNotFoundException"
        assert any("qualifier" in s.lower() for s in r["troubleshooting"])

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_access_denied(self, mock_retry, mock_cp):
        mock_cp.return_value = Mock()
        mock_retry.side_effect = _ce("AccessDeniedException")
        r = await tool_start_deployment(_ctx(), pipeline_name="X")
        assert r["success"] is False

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_unexpected_exception(self, mock_retry, mock_cp):
        mock_cp.return_value = Mock()
        mock_retry.side_effect = Exception("boom")
        r = await tool_start_deployment(_ctx(), pipeline_name="X")
        assert r["success"] is False

    @pytest.mark.asyncio
    @patch(_CP)
    @patch(_RETRY)
    async def test_start_execution_fails(self, mock_retry, mock_cp):
        mock_cp.return_value = Mock()
        mock_retry.side_effect = [
            {"pipeline": {"name": "t"}},
            _ce("InvalidStructureException"),
        ]
        r = await tool_start_deployment(_ctx(), pipeline_name="X")
        assert r["success"] is False


class TestExternalErrors:
    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_neither_found(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                raise _ce("PipelineNotFoundException")
            raise _ce("InvalidDocument")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is False
        assert "No deployment infrastructure found" in r["error"]

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_cp_unexpected_exception(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                raise RuntimeError("CP boom")
            if n[0] == 2:
                return {"Document": {"Name": "q-RunEngine"}}
            return {"AutomationExecutionId": "ok"}

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is True
        assert "SSM Automation" in r["sources_started"]

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_ssm_unexpected_exception(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                return {"pipeline": {"name": "q-pipeline"}}
            if n[0] == 2:
                return {"pipelineExecutionId": "ok"}
            raise RuntimeError("SSM boom")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is True
        assert "CodePipeline" in r["sources_started"]

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_both_found_both_failed(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                return {"pipeline": {"name": "q-pipeline"}}
            if n[0] == 2:
                raise _ce("InvalidStructureException")
            if n[0] == 3:
                return {"Document": {"Name": "q-RunEngine"}}
            raise _ce("AutomationExecutionLimitExceededException")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is False
        assert "could not be started" in r["message"]

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_cp_failed_ssm_not_found(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                return {"pipeline": {"name": "q-pipeline"}}
            if n[0] == 2:
                raise _ce("InvalidStructureException")
            raise _ce("InvalidDocument")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is False

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_ssm_describe_reraises_non_invalid_document(
        self, mock_retry, mock_cp, mock_ssm
    ):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                raise _ce("PipelineNotFoundException")
            raise _ce("AccessDeniedException")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is False

    @pytest.mark.asyncio
    @patch(_SSM)
    @patch(_CP)
    @patch(_RETRY)
    async def test_ssm_start_generic_exception(self, mock_retry, mock_cp, mock_ssm):
        mock_cp.return_value = Mock()
        mock_ssm.return_value = Mock()
        n = [0]

        def se(func, *a, **kw):
            n[0] += 1
            if n[0] == 1:
                raise _ce("PipelineNotFoundException")
            if n[0] == 2:
                return {"Document": {"Name": "q-RunEngine"}}
            raise Exception("SSM generic fail")

        mock_retry.side_effect = se
        r = await tool_start_deployment(_ctx(), qualifier="q")
        assert r["success"] is False
