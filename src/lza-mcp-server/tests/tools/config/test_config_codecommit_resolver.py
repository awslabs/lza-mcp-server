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

"""Unit tests for config_codecommit_resolver module."""

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.config.config_codecommit_resolver import (
    ConfigCodeCommitLocation,
    _get_pipeline_name,
    _detect_codecommit_source,
    resolve_codecommit_location,
)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "error"}}, "op")


def _make_pipeline_response(provider: str, repo: str = "my-repo", branch: str = "main"):
    """Build a minimal get_pipeline response."""
    return {
        "pipeline": {
            "stages": [
                {
                    "actions": [
                        {
                            "actionTypeId": {
                                "category": "Source",
                                "provider": provider,
                            },
                            "configuration": {
                                "RepositoryName": repo,
                                "BranchName": branch,
                            },
                        }
                    ]
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# _get_pipeline_name
# ---------------------------------------------------------------------------


class TestGetPipelineName:
    def test_no_qualifier_returns_pipeline_suffix(self):
        # The default pipeline name always ends with "-Pipeline" regardless of
        # the LZA_PREFIX environment variable.
        result = _get_pipeline_name(None)
        assert result.endswith("-Pipeline")

    def test_qualifier_returns_qualifier_pipeline(self):
        assert _get_pipeline_name("my-qualifier") == "my-qualifier-pipeline"


# ---------------------------------------------------------------------------
# _detect_codecommit_source
# ---------------------------------------------------------------------------


class TestDetectCodeCommitSource:
    def _make_session(self, pipeline_response=None, side_effect=None):
        session = MagicMock()
        cp_client = MagicMock()
        session.client.return_value = cp_client
        if side_effect:
            cp_client.get_pipeline.side_effect = side_effect
        else:
            cp_client.get_pipeline.return_value = pipeline_response
        return session

    def test_detects_codecommit_source(self):
        session = self._make_session(
            _make_pipeline_response("CodeCommit", "lza-config-repo", "main")
        )

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is not None
        assert result.repository_name == "lza-config-repo"
        assert result.branch == "main"
        assert result.qualifier is None

    def test_returns_none_for_s3_source(self):
        session = self._make_session(_make_pipeline_response("S3", "my-bucket", ""))

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None

    def test_returns_none_when_pipeline_not_found(self):
        session = self._make_session(
            side_effect=_client_error("PipelineNotFoundException")
        )

        result = _detect_codecommit_source(session, "missing-pipeline", "us-east-1")

        assert result is None

    def test_returns_none_on_other_client_error(self):
        session = self._make_session(side_effect=_client_error("AccessDeniedException"))

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None

    def test_returns_none_on_unexpected_exception(self):
        session = self._make_session(side_effect=RuntimeError("network error"))

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None

    def test_returns_none_when_no_stages(self):
        session = self._make_session({"pipeline": {"stages": []}})

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None

    def test_returns_none_when_repo_name_missing(self):
        response = {
            "pipeline": {
                "stages": [
                    {
                        "actions": [
                            {
                                "actionTypeId": {
                                    "category": "Source",
                                    "provider": "CodeCommit",
                                },
                                "configuration": {},  # no RepositoryName
                            }
                        ]
                    }
                ]
            }
        }
        session = self._make_session(response)

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None

    def test_uses_default_branch_when_not_configured(self):
        response = {
            "pipeline": {
                "stages": [
                    {
                        "actions": [
                            {
                                "actionTypeId": {
                                    "category": "Source",
                                    "provider": "CodeCommit",
                                },
                                "configuration": {
                                    "RepositoryName": "my-repo",
                                    # BranchName absent
                                },
                            }
                        ]
                    }
                ]
            }
        }
        session = self._make_session(response)

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is not None
        assert result.branch == "main"

    def test_skips_non_source_actions(self):
        response = {
            "pipeline": {
                "stages": [
                    {
                        "actions": [
                            {
                                "actionTypeId": {
                                    "category": "Build",  # not Source
                                    "provider": "CodeCommit",
                                },
                                "configuration": {"RepositoryName": "my-repo"},
                            }
                        ]
                    }
                ]
            }
        }
        session = self._make_session(response)

        result = _detect_codecommit_source(
            session, "AWSAccelerator-Pipeline", "us-east-1"
        )

        assert result is None


# ---------------------------------------------------------------------------
# resolve_codecommit_location
# ---------------------------------------------------------------------------


class TestResolveCodeCommitLocation:
    def test_explicit_repo_name_no_branch(self):
        result = resolve_codecommit_location(repository_name="my-repo")

        assert result is not None
        assert result.repository_name == "my-repo"
        assert result.branch == "main"
        assert result.qualifier is None

    def test_explicit_repo_name_with_branch(self):
        result = resolve_codecommit_location(
            repository_name="my-repo", branch="develop"
        )

        assert result.branch == "develop"

    def test_explicit_repo_name_with_qualifier(self):
        result = resolve_codecommit_location(
            repository_name="my-repo", qualifier="my-qualifier"
        )

        assert result.repository_name == "my-repo"
        assert result.qualifier == "my-qualifier"

    def test_auto_detect_codecommit_source(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.return_value = _make_pipeline_response(
            "CodeCommit", "detected-repo", "main"
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location()

        assert result is not None
        assert result.repository_name == "detected-repo"
        assert result.branch == "main"

    def test_auto_detect_returns_none_for_s3_source(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.return_value = _make_pipeline_response("S3")

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location()

        assert result is None

    def test_auto_detect_with_qualifier_attaches_qualifier(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.return_value = _make_pipeline_response(
            "CodeCommit", "detected-repo", "main"
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location(qualifier="my-qualifier")

        assert result is not None
        assert result.qualifier == "my-qualifier"
        assert result.repository_name == "detected-repo"

    def test_auto_detect_with_qualifier_and_branch_override(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.return_value = _make_pipeline_response(
            "CodeCommit", "detected-repo", "main"
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location(
                qualifier="my-qualifier", branch="feature-branch"
            )

        assert result is not None
        assert result.branch == "feature-branch"
        assert result.qualifier == "my-qualifier"

    def test_auto_detect_branch_override_without_qualifier(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.return_value = _make_pipeline_response(
            "CodeCommit", "detected-repo", "main"
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location(branch="custom-branch")

        assert result is not None
        assert result.branch == "custom-branch"
        assert result.qualifier is None

    def test_auto_detect_pipeline_not_found_returns_none(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.side_effect = ClientError(
            {"Error": {"Code": "PipelineNotFoundException", "Message": "not found"}},
            "GetPipeline",
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location()

        assert result is None

    def test_no_args_no_pipeline_returns_none(self):
        mock_session = MagicMock()
        cp_client = MagicMock()
        mock_session.client.return_value = cp_client
        cp_client.get_pipeline.side_effect = ClientError(
            {"Error": {"Code": "PipelineNotFoundException", "Message": "not found"}},
            "GetPipeline",
        )

        with patch(
            "awslabs.lza_mcp_server.tools.config.config_codecommit_resolver.get_aws_session",
            return_value=mock_session,
        ):
            result = resolve_codecommit_location()

        assert result is None


# ---------------------------------------------------------------------------
# ConfigCodeCommitLocation dataclass
# ---------------------------------------------------------------------------


class TestConfigCodeCommitLocation:
    def test_frozen_dataclass(self):
        loc = ConfigCodeCommitLocation(
            repository_name="repo", branch="main", qualifier=None
        )
        with pytest.raises((AttributeError, TypeError)):
            loc.repository_name = "other"  # type: ignore[misc]

    def test_equality(self):
        a = ConfigCodeCommitLocation("repo", "main", None)
        b = ConfigCodeCommitLocation("repo", "main", None)
        assert a == b

    def test_inequality(self):
        a = ConfigCodeCommitLocation("repo", "main", None)
        b = ConfigCodeCommitLocation("repo", "develop", None)
        assert a != b
