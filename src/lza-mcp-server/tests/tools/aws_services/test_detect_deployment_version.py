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

"""Unit tests for LZA deployment version detection."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_version import (
    _find_version_param_for_standard,
    _find_version_param_for_qualifier,
    _normalize_version,
    detect_deployment_version,
)
from awslabs.lza_mcp_server.tools.aws_services.detect_deployment_type import (
    DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
    DEPLOYMENT_TYPE_STANDARD,
)


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "operation")


LAST_MODIFIED = datetime(2026, 1, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# _normalize_version
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeVersion:
    def test_adds_v_prefix(self):
        assert _normalize_version("1.13.0") == "v1.13.0"

    def test_keeps_existing_v_prefix(self):
        assert _normalize_version("v1.13.0") == "v1.13.0"

    def test_rc_version(self):
        assert _normalize_version("1.15.0-rc.10") == "v1.15.0-rc.10"


# ---------------------------------------------------------------------------
# _find_version_param_for_standard
# ---------------------------------------------------------------------------


def _mock_ssm_get_parameter(value="1.14.4", error=None):
    """Create a mock SSM client with get_parameter configured."""
    client = MagicMock()
    if error:
        client.get_parameter.side_effect = error
    else:
        client.get_parameter.return_value = {
            "Parameter": {
                "Name": "/accelerator/AWSAccelerator-InstallerStack/version",
                "Value": value,
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        }
    return client


def _mock_ssm_with_path_scan(params, get_param_error=None):
    """Create a mock SSM client with get_parameter failing and get_parameters_by_path returning params."""
    client = MagicMock()

    # get_parameter always raises ParameterNotFound (or custom error)
    if get_param_error:
        client.get_parameter.side_effect = get_param_error
    else:
        client.get_parameter.side_effect = _make_client_error("ParameterNotFound")

    paginator = MagicMock()
    paginator.paginate.return_value = [{"Parameters": params}]
    client.get_paginator.return_value = paginator

    return client


@pytest.mark.unit
class TestFindVersionParamForStandard:
    def test_well_known_path_found(self):
        client = _mock_ssm_get_parameter(value="1.14.4")
        result = _find_version_param_for_standard(client)
        assert result is not None
        assert result["Value"] == "1.14.4"

    def test_fallback_scan_finds_param(self):
        params = [
            {
                "Name": "/accelerator/AWSAccelerator-InstallerStack/version",
                "Value": "1.13.0",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        client = _mock_ssm_with_path_scan(params)
        result = _find_version_param_for_standard(client)
        assert result is not None
        assert result["Value"] == "1.13.0"

    def test_fallback_scan_ignores_qualified_params(self):
        # Qualified params have 4 segments — should be skipped for standard
        params = [
            {
                "Name": "/accelerator/my-qualifier/AWSAccelerator-InstallerContainerStack/version",
                "Value": "1.15.0",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        client = _mock_ssm_with_path_scan(params)
        result = _find_version_param_for_standard(client)
        assert result is None

    def test_non_parameter_not_found_error_propagates(self):
        client = _mock_ssm_get_parameter(
            error=_make_client_error("AccessDeniedException")
        )
        with pytest.raises(ClientError):
            _find_version_param_for_standard(client)

    def test_no_params_returns_none(self):
        client = _mock_ssm_with_path_scan([])
        result = _find_version_param_for_standard(client)
        assert result is None


# ---------------------------------------------------------------------------
# _find_version_param_for_qualifier
# ---------------------------------------------------------------------------


def _mock_ssm_qualifier_scan(params):
    """Create a mock SSM client with get_parameters_by_path for qualifier path."""
    client = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [{"Parameters": params}]
    client.get_paginator.return_value = paginator
    return client


@pytest.mark.unit
class TestFindVersionParamForQualifier:
    def test_container_stack_found(self):
        params = [
            {
                "Name": "/accelerator/container-dev-1/AWSAccelerator-InstallerContainerStack/version",
                "Value": "1.15.0-rc.10",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        client = _mock_ssm_qualifier_scan(params)
        result = _find_version_param_for_qualifier(client, "container-dev-1")
        assert result is not None
        assert result["Value"] == "1.15.0-rc.10"

    def test_codepipeline_installer_stack_found(self):
        params = [
            {
                "Name": "/accelerator/prod-pipeline/AWSAccelerator-InstallerStack/version",
                "Value": "1.14.0",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        client = _mock_ssm_qualifier_scan(params)
        result = _find_version_param_for_qualifier(client, "prod-pipeline")
        assert result is not None
        assert result["Value"] == "1.14.0"

    def test_no_version_param_returns_none(self):
        # Only non-version params under the qualifier
        params = [
            {
                "Name": "/accelerator/my-qualifier/lza-prefix",
                "Value": "AWSAccelerator",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        client = _mock_ssm_qualifier_scan(params)
        result = _find_version_param_for_qualifier(client, "my-qualifier")
        assert result is None

    def test_client_error_propagates(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = _make_client_error("AccessDeniedException")
        client.get_paginator.return_value = paginator
        with pytest.raises(ClientError):
            _find_version_param_for_qualifier(client, "my-qualifier")


# ---------------------------------------------------------------------------
# detect_deployment_version — standard
# ---------------------------------------------------------------------------


def _mock_session_with_ssm(ssm_client):
    """Create a mock session that returns the given SSM client."""
    session = MagicMock()
    session.client.return_value = ssm_client
    return session


@pytest.mark.unit
class TestDetectDeploymentVersionStandard:
    def test_standard_success(self):
        ssm = _mock_ssm_get_parameter(value="1.14.4")
        session = _mock_session_with_ssm(ssm)
        deployment = {"success": True, "deployment_type": DEPLOYMENT_TYPE_STANDARD}

        result = detect_deployment_version(session, "eu-north-1", deployment)

        assert result["success"] is True
        assert result["version"] == "v1.14.4"
        assert result["raw_version"] == "1.14.4"
        assert result["deployment_type"] == DEPLOYMENT_TYPE_STANDARD
        assert result["region"] == "eu-north-1"

    def test_standard_not_found(self):
        ssm = _mock_ssm_with_path_scan([])
        session = _mock_session_with_ssm(ssm)
        deployment = {"success": True, "deployment_type": DEPLOYMENT_TYPE_STANDARD}

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert result["version"] is None
        assert "troubleshooting" in result

    def test_standard_access_denied(self):
        ssm = _mock_ssm_get_parameter(error=_make_client_error("AccessDeniedException"))
        session = _mock_session_with_ssm(ssm)
        deployment = {"success": True, "deployment_type": DEPLOYMENT_TYPE_STANDARD}

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert result["error_code"] == "AccessDeniedException"
        assert "troubleshooting" in result


# ---------------------------------------------------------------------------
# detect_deployment_version — external pipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectDeploymentVersionExternal:
    def test_single_qualifier_success(self):
        params = [
            {
                "Name": "/accelerator/container-dev-1/AWSAccelerator-InstallerContainerStack/version",
                "Value": "1.15.0-rc.10",
                "Type": "String",
                "LastModifiedDate": LAST_MODIFIED,
            }
        ]
        ssm = _mock_ssm_qualifier_scan(params)
        session = _mock_session_with_ssm(ssm)
        deployment = {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
            "qualifier_names": ["container-dev-1"],
        }

        result = detect_deployment_version(session, "eu-north-1", deployment)

        assert result["success"] is True
        assert result["version"] == "v1.15.0-rc.10"
        assert result["deployment_type"] == DEPLOYMENT_TYPE_EXTERNAL_PIPELINE
        assert len(result["qualifier_versions"]) == 1
        assert result["qualifier_versions"][0]["qualifier"] == "container-dev-1"
        assert result["qualifier_versions"][0]["success"] is True

    def test_multiple_qualifiers_mixed_results(self):
        """One qualifier has a version, the other doesn't."""
        session = MagicMock()

        def make_ssm_client(service, **kwargs):
            client = MagicMock()
            paginator = MagicMock()

            # Return different results based on the path argument
            def paginate_side_effect(**pg_kwargs):
                path = pg_kwargs.get("Path", "")
                if "prod-pipeline" in path:
                    return [
                        {
                            "Parameters": [
                                {
                                    "Name": "/accelerator/prod-pipeline/AWSAccelerator-InstallerStack/version",
                                    "Value": "1.14.0",
                                    "Type": "String",
                                    "LastModifiedDate": LAST_MODIFIED,
                                }
                            ]
                        }
                    ]
                return [{"Parameters": []}]

            paginator.paginate.side_effect = paginate_side_effect
            client.get_paginator.return_value = paginator
            return client

        session.client.side_effect = make_ssm_client
        deployment = {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
            "qualifier_names": ["prod-pipeline", "dev-pipeline"],
        }

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is True
        assert result["version"] == "v1.14.0"
        assert len(result["qualifier_versions"]) == 2

        prod = next(
            qv
            for qv in result["qualifier_versions"]
            if qv["qualifier"] == "prod-pipeline"
        )
        dev = next(
            qv
            for qv in result["qualifier_versions"]
            if qv["qualifier"] == "dev-pipeline"
        )
        assert prod["success"] is True
        assert dev["success"] is False

    def test_no_qualifiers_found(self):
        ssm = _mock_ssm_qualifier_scan([])
        session = _mock_session_with_ssm(ssm)
        deployment = {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
            "qualifier_names": ["missing-qualifier"],
        }

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert result["version"] is None
        assert "troubleshooting" in result

    def test_qualifier_access_denied(self):
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = _make_client_error("AccessDeniedException")
        client.get_paginator.return_value = paginator
        session = _mock_session_with_ssm(client)
        deployment = {
            "success": True,
            "deployment_type": DEPLOYMENT_TYPE_EXTERNAL_PIPELINE,
            "qualifier_names": ["locked-qualifier"],
        }

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert result["qualifier_versions"][0]["success"] is False
        assert "error" in result["qualifier_versions"][0]


# ---------------------------------------------------------------------------
# detect_deployment_version — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectDeploymentVersionEdgeCases:
    def test_failed_deployment_detection(self):
        session = MagicMock()
        deployment = {
            "success": False,
            "deployment_type": None,
            "troubleshooting": ["Check credentials"],
        }

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert result["version"] is None
        assert "troubleshooting" in result

    def test_unsupported_deployment_type(self):
        session = MagicMock()
        deployment = {"success": True, "deployment_type": "some_future_type"}

        result = detect_deployment_version(session, "us-east-1", deployment)

        assert result["success"] is False
        assert "Unsupported" in result["message"]
