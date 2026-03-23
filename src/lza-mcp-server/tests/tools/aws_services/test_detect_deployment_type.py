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

"""Unit tests for LZA deployment type detection."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import (
    ClientError,
    ConnectionError as BotocoreConnectionError,
    EndpointConnectionError,
    EndpointResolutionError,
)

from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_type import (
    DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
    DEPLOYMENT_TYPE_STANDARD,
    RUNNER_CODEPIPELINE,
    RUNNER_ECS_CONTAINER,
    RUNNER_UNKNOWN,
    _extract_qualifier_from_param_name,
    _detect_runner_for_qualifier,
    detect_lza_deployment,
)


# ---------------------------------------------------------------------------
# _extract_qualifier_from_param_name
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractQualifier:
    def test_valid_scoped_path(self):
        assert (
            _extract_qualifier_from_param_name(
                "/accelerator/container-dev-1/lza-prefix"
            )
            == "container-dev-1"
        )

    def test_root_path_returns_none(self):
        assert _extract_qualifier_from_param_name("/accelerator/lza-prefix") is None

    def test_unrelated_path_returns_none(self):
        assert (
            _extract_qualifier_from_param_name(
                "/accelerator/AWSAccelerator-InstallerStack/version"
            )
            is None
        )

    def test_deeply_nested_path_returns_none(self):
        # Only one qualifier segment is valid
        assert _extract_qualifier_from_param_name("/accelerator/a/b/lza-prefix") is None

    def test_qualifier_with_hyphens_and_numbers(self):
        assert (
            _extract_qualifier_from_param_name(
                "/accelerator/prod-pipeline-2/lza-prefix"
            )
            == "prod-pipeline-2"
        )


# ---------------------------------------------------------------------------
# _detect_runner_for_qualifier
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "operation")


@pytest.mark.unit
class TestDetectRunnerForQualifier:
    def _mock_session(
        self,
        cp_pipelines=None,
        ecs_clusters=None,
        cp_error=None,
        ecs_error=None,
    ):
        session = MagicMock()
        cp_client = MagicMock()
        ecs_client = MagicMock()

        def client_factory(service, **kwargs):
            if service == "codepipeline":
                return cp_client
            if service == "ecs":
                return ecs_client
            return MagicMock()

        session.client.side_effect = client_factory

        cp_paginator = MagicMock()
        if cp_error:
            cp_client.get_paginator.side_effect = cp_error
        else:
            cp_client.get_paginator.return_value = cp_paginator
            cp_paginator.paginate.return_value = [
                {"pipelines": [{"name": n} for n in (cp_pipelines or [])]}
            ]

        ecs_paginator = MagicMock()
        if ecs_error:
            ecs_client.get_paginator.side_effect = ecs_error
        else:
            ecs_client.get_paginator.return_value = ecs_paginator
            ecs_paginator.paginate.return_value = [{"clusterArns": ecs_clusters or []}]

        return session

    def test_codepipeline_match(self):
        session = self._mock_session(
            cp_pipelines=["container-dev-1-AWSAccelerator-Pipeline"]
        )
        result = _detect_runner_for_qualifier(session, "container-dev-1", "us-east-1")
        assert result == RUNNER_CODEPIPELINE

    def test_ecs_match_when_no_codepipeline(self):
        session = self._mock_session(
            cp_pipelines=[],
            ecs_clusters=[
                "arn:aws:ecs:eu-north-1:123456789012:cluster/container-dev-1-ecs-cluster"
            ],
        )
        result = _detect_runner_for_qualifier(session, "container-dev-1", "eu-north-1")
        assert result == RUNNER_ECS_CONTAINER

    def test_unknown_when_neither_found(self):
        session = self._mock_session(cp_pipelines=[], ecs_clusters=[])
        result = _detect_runner_for_qualifier(session, "my-qualifier", "us-east-1")
        assert result == RUNNER_UNKNOWN

    def test_codepipeline_error_falls_through_to_ecs(self):
        session = self._mock_session(
            cp_error=_make_client_error("AccessDeniedException"),
            ecs_clusters=["arn:aws:ecs:us-east-1:123:cluster/my-qualifier-cluster"],
        )
        result = _detect_runner_for_qualifier(session, "my-qualifier", "us-east-1")
        assert result == RUNNER_ECS_CONTAINER

    def test_both_services_error_returns_unknown(self):
        session = self._mock_session(
            cp_error=EndpointResolutionError(msg="endpoint not available"),
            ecs_error=EndpointResolutionError(msg="endpoint not available"),
        )
        result = _detect_runner_for_qualifier(session, "my-qualifier", "us-east-1")
        assert result == RUNNER_UNKNOWN

    def test_qualifier_case_insensitive_match(self):
        session = self._mock_session(cp_pipelines=["CONTAINER-DEV-1-Pipeline"])
        result = _detect_runner_for_qualifier(session, "container-dev-1", "us-east-1")
        assert result == RUNNER_CODEPIPELINE

    def test_codepipeline_endpoint_connection_error_falls_through_to_ecs(self):
        """ESC regions where CodePipeline doesn't exist raise EndpointConnectionError."""
        session = self._mock_session(
            cp_error=EndpointConnectionError(
                endpoint_url="https://codepipeline.eusc-de-east-1.amazonaws.eu/"
            ),
            ecs_clusters=[
                "arn:aws:ecs:eusc-de-east-1:123:cluster/my-qualifier-cluster"
            ],
        )
        result = _detect_runner_for_qualifier(session, "my-qualifier", "eusc-de-east-1")
        assert result == RUNNER_ECS_CONTAINER

    def test_codepipeline_botocore_connection_error_falls_through_to_ecs(self):
        """Generic botocore ConnectionError also falls through gracefully."""
        session = self._mock_session(
            cp_error=BotocoreConnectionError(error="Connection refused"),
            ecs_clusters=[
                "arn:aws:ecs:eusc-de-east-1:123:cluster/my-qualifier-cluster"
            ],
        )
        result = _detect_runner_for_qualifier(session, "my-qualifier", "eusc-de-east-1")
        assert result == RUNNER_ECS_CONTAINER

    def test_both_services_endpoint_connection_error_returns_unknown(self):
        """When both services are unavailable in the region, return unknown."""
        session = self._mock_session(
            cp_error=EndpointConnectionError(
                endpoint_url="https://codepipeline.eusc-de-east-1.amazonaws.eu/"
            ),
            ecs_error=EndpointConnectionError(
                endpoint_url="https://ecs.eusc-de-east-1.amazonaws.eu/"
            ),
        )
        result = _detect_runner_for_qualifier(session, "my-qualifier", "eusc-de-east-1")
        assert result == RUNNER_UNKNOWN


# ---------------------------------------------------------------------------
# detect_lza_deployment
# ---------------------------------------------------------------------------


def _make_ssm_paginator(param_names: list):
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Parameters": [{"Name": n} for n in param_names]}
    ]
    return paginator


@pytest.mark.unit
class TestDetectLzaDeployment:
    def _session_with_ssm_params(
        self, param_names, cp_pipelines=None, ecs_clusters=None
    ):
        session = MagicMock()
        ssm_client = MagicMock()
        cp_client = MagicMock()
        ecs_client = MagicMock()

        def client_factory(service, **kwargs):
            if service == "ssm":
                return ssm_client
            if service == "codepipeline":
                return cp_client
            if service == "ecs":
                return ecs_client
            return MagicMock()

        session.client.side_effect = client_factory

        ssm_client.get_paginator.return_value = _make_ssm_paginator(param_names)

        cp_paginator = MagicMock()
        cp_client.get_paginator.return_value = cp_paginator
        cp_paginator.paginate.return_value = [
            {"pipelines": [{"name": n} for n in (cp_pipelines or [])]}
        ]

        ecs_paginator = MagicMock()
        ecs_client.get_paginator.return_value = ecs_paginator
        ecs_paginator.paginate.return_value = [{"clusterArns": ecs_clusters or []}]

        return session

    def test_standard_deployment_detected(self):
        session = self._session_with_ssm_params(
            [
                "/accelerator/lza-prefix",
                "/accelerator/AWSAccelerator-InstallerStack/version",
            ]
        )
        result = detect_lza_deployment(session, "us-east-1")
        assert result["success"] is True
        assert result["deployment_type"] == DEPLOYMENT_TYPE_STANDARD

    def test_external_pipeline_single_qualifier(self):
        session = self._session_with_ssm_params(
            [
                "/accelerator/container-dev-1/lza-prefix",
                "/accelerator/container-dev-1/AWSAccelerator-InstallerContainerStack/version",
            ],
            ecs_clusters=[
                "arn:aws:ecs:eu-north-1:123:cluster/container-dev-1-ecs-cluster"
            ],
        )
        result = detect_lza_deployment(session, "eu-north-1")
        assert result["success"] is True
        assert result["deployment_type"] == DEPLOYMENT_TYPE_EXTERNAL_PIPELINE
        assert result["qualifier_names"] == ["container-dev-1"]
        assert result["qualifiers"][0]["runner"] == RUNNER_ECS_CONTAINER

    def test_external_pipeline_multiple_qualifiers(self):
        session = self._session_with_ssm_params(
            [
                "/accelerator/prod-pipeline/lza-prefix",
                "/accelerator/dev-pipeline/lza-prefix",
            ],
            cp_pipelines=["prod-pipeline-AWSAccelerator-Pipeline"],
        )
        result = detect_lza_deployment(session, "us-east-1")
        assert result["success"] is True
        assert result["deployment_type"] == DEPLOYMENT_TYPE_EXTERNAL_PIPELINE
        assert len(result["qualifier_names"]) == 2
        assert "prod-pipeline" in result["qualifier_names"]
        assert "dev-pipeline" in result["qualifier_names"]
        # next_steps should instruct agent to ask user which qualifier to use
        assert any("ask the user" in s.lower() for s in result["next_steps"])

    def test_standard_takes_precedence_over_scoped(self):
        # Root lza-prefix alongside scoped ones → standard wins
        session = self._session_with_ssm_params(
            [
                "/accelerator/lza-prefix",
                "/accelerator/some-qualifier/lza-prefix",
            ]
        )
        result = detect_lza_deployment(session, "us-east-1")
        assert result["deployment_type"] == DEPLOYMENT_TYPE_STANDARD

    def test_no_lza_params_returns_failure(self):
        session = self._session_with_ssm_params(
            [
                "/accelerator/AWSAccelerator-InstallerStack/version",
            ]
        )
        result = detect_lza_deployment(session, "us-east-1")
        assert result["success"] is False
        assert result["deployment_type"] is None
        assert "troubleshooting" in result

    def test_ssm_client_error_returns_failure(self):
        session = MagicMock()
        ssm_client = MagicMock()
        session.client.return_value = ssm_client
        ssm_client.get_paginator.side_effect = _make_client_error(
            "AccessDeniedException"
        )

        result = detect_lza_deployment(session, "us-east-1")
        assert result["success"] is False
        assert result["deployment_type"] is None
        assert "troubleshooting" in result

    def test_ssm_unexpected_error_returns_failure(self):
        session = MagicMock()
        ssm_client = MagicMock()
        session.client.return_value = ssm_client
        ssm_client.get_paginator.side_effect = Exception("network error")

        result = detect_lza_deployment(session, "us-east-1")
        assert result["success"] is False
        assert result["deployment_type"] is None
