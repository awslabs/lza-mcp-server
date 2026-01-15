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

"""Unit tests for validation utilities."""

import pytest
from awslabs.lza_mcp_server.tools.uc_merge.validation import (
    validate_fresh_installation_accounts,
    validate_fresh_installation_network,
    validate_fresh_installation_iam,
)


# Unit Tests


@pytest.mark.unit
@pytest.mark.uc_merge
class TestFreshInstallationValidation:
    """Unit tests for fresh installation validation functions."""

    def test_validate_accounts_empty_workload_accounts(self):
        """Test validation passes with empty workloadAccounts.

        Requirements: 4.1
        """
        accounts_config = {
            "mandatoryAccounts": [
                {"name": "Management", "email": "management@example.com"},
                {"name": "LogArchive", "email": "logarchive@example.com"},
                {"name": "Audit", "email": "audit@example.com"},
            ],
            "workloadAccounts": [],
        }

        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_accounts_missing_workload_accounts(self):
        """Test validation passes when workloadAccounts is missing.

        Requirements: 4.1
        """
        accounts_config = {
            "mandatoryAccounts": [
                {"name": "Management", "email": "management@example.com"}
            ]
        }

        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_accounts_none_workload_accounts(self):
        """Test validation passes when workloadAccounts is None.

        Requirements: 4.1
        """
        accounts_config = {"mandatoryAccounts": [], "workloadAccounts": None}

        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_accounts_with_workload_accounts_fails(self):
        """Test validation fails when workloadAccounts contains accounts.

        Requirements: 4.1, 4.4
        """
        accounts_config = {
            "mandatoryAccounts": [],
            "workloadAccounts": [
                {"name": "Dev", "email": "dev@example.com"},
                {"name": "Prod", "email": "prod@example.com"},
            ],
        }

        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)

        assert is_valid is False
        assert "not fresh" in error_msg
        assert "2 accounts" in error_msg
        assert "UC merge requires" in error_msg

    def test_validate_accounts_invalid_type(self):
        """Test validation fails when accounts_config is not a dict.

        Requirements: 4.4
        """
        is_valid, error_msg = validate_fresh_installation_accounts("not a dict")

        assert is_valid is False
        assert "must be a dictionary" in error_msg

    def test_validate_accounts_workload_accounts_not_list(self):
        """Test validation fails when workloadAccounts is not a list.

        Requirements: 4.4
        """
        accounts_config = {"workloadAccounts": "not a list"}

        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)

        assert is_valid is False
        assert "must be a list" in error_msg

    def test_validate_network_minimal_config(self):
        """Test validation passes with minimal network config.

        Requirements: 4.2
        """
        network_config = {"transitGateways": [], "endpointPolicies": [], "vpcs": []}

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_network_missing_fields(self):
        """Test validation passes when fields are missing.

        Requirements: 4.2
        """
        network_config = {}

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_network_none_values(self):
        """Test validation passes when fields are None.

        Requirements: 4.2
        """
        network_config = {
            "transitGateways": None,
            "endpointPolicies": None,
            "vpcs": None,
        }

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_network_with_transit_gateways_fails(self):
        """Test validation fails when transitGateways contains items.

        Requirements: 4.2, 4.4
        """
        network_config = {
            "transitGateways": [{"name": "tgw-1", "asn": 64512}],
            "endpointPolicies": [],
            "vpcs": [],
        }

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is False
        assert "not fresh" in error_msg
        assert "transitGateways" in error_msg
        assert "1 transitGateways" in error_msg

    def test_validate_network_with_vpcs_fails(self):
        """Test validation fails when vpcs contains items.

        Requirements: 4.2, 4.4
        """
        network_config = {
            "transitGateways": [],
            "endpointPolicies": [],
            "vpcs": [{"name": "vpc-1", "cidr": "10.0.0.0/16"}],
        }

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is False
        assert "not fresh" in error_msg
        assert "vpcs" in error_msg

    def test_validate_network_invalid_type(self):
        """Test validation fails when network_config is not a dict.

        Requirements: 4.4
        """
        is_valid, error_msg = validate_fresh_installation_network("not a dict")

        assert is_valid is False
        assert "must be a dictionary" in error_msg

    def test_validate_network_field_not_list(self):
        """Test validation fails when a field is not a list.

        Requirements: 4.4
        """
        network_config = {"transitGateways": "not a list"}

        is_valid, error_msg = validate_fresh_installation_network(network_config)

        assert is_valid is False
        assert "must be a list" in error_msg

    def test_validate_iam_minimal_config(self):
        """Test validation passes with minimal IAM config.

        Requirements: 4.3
        """
        iam_config = {
            "providers": [],
            "policySets": [],
            "roleSets": [],
            "groupSets": [],
            "userSets": [],
        }

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_iam_missing_fields(self):
        """Test validation passes when fields are missing.

        Requirements: 4.3
        """
        iam_config = {}

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_iam_none_values(self):
        """Test validation passes when fields are None.

        Requirements: 4.3
        """
        iam_config = {
            "providers": None,
            "policySets": None,
            "roleSets": None,
            "groupSets": None,
            "userSets": None,
        }

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_iam_with_providers_fails(self):
        """Test validation fails when providers contains items.

        Requirements: 4.3, 4.4
        """
        iam_config = {
            "providers": [{"name": "provider-1"}],
            "policySets": [],
            "roleSets": [],
            "groupSets": [],
            "userSets": [],
        }

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is False
        assert "not fresh" in error_msg
        assert "providers" in error_msg
        assert "1 providers" in error_msg

    def test_validate_iam_with_role_sets_fails(self):
        """Test validation fails when roleSets contains items.

        Requirements: 4.3, 4.4
        """
        iam_config = {
            "providers": [],
            "policySets": [],
            "roleSets": [{"name": "role-1"}],
            "groupSets": [],
            "userSets": [],
        }

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is False
        assert "not fresh" in error_msg
        assert "roleSets" in error_msg

    def test_validate_iam_invalid_type(self):
        """Test validation fails when iam_config is not a dict.

        Requirements: 4.4
        """
        is_valid, error_msg = validate_fresh_installation_iam("not a dict")

        assert is_valid is False
        assert "must be a dictionary" in error_msg

    def test_validate_iam_field_not_list(self):
        """Test validation fails when a field is not a list.

        Requirements: 4.4
        """
        iam_config = {"providers": "not a list"}

        is_valid, error_msg = validate_fresh_installation_iam(iam_config)

        assert is_valid is False
        assert "must be a list" in error_msg

    def test_validation_error_messages_are_specific(self):
        """Test that validation errors indicate which file has issues.

        Requirements: 4.4, 4.5
        """
        # Test accounts error message
        accounts_config = {"workloadAccounts": [{"name": "Dev"}]}
        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)
        assert is_valid is False
        assert "workloadAccounts" in error_msg

        # Test network error message
        network_config = {"vpcs": [{"name": "vpc-1"}]}
        is_valid, error_msg = validate_fresh_installation_network(network_config)
        assert is_valid is False
        assert "vpcs" in error_msg

        # Test IAM error message
        iam_config = {"roleSets": [{"name": "role-1"}]}
        is_valid, error_msg = validate_fresh_installation_iam(iam_config)
        assert is_valid is False
        assert "roleSets" in error_msg

    def test_validation_success_includes_empty_error_message(self):
        """Test that successful validation returns empty error message.

        Requirements: 4.5
        """
        # Test accounts
        accounts_config = {"workloadAccounts": []}
        is_valid, error_msg = validate_fresh_installation_accounts(accounts_config)
        assert is_valid is True
        assert error_msg == ""

        # Test network
        network_config = {"transitGateways": [], "endpointPolicies": [], "vpcs": []}
        is_valid, error_msg = validate_fresh_installation_network(network_config)
        assert is_valid is True
        assert error_msg == ""

        # Test IAM
        iam_config = {
            "providers": [],
            "policySets": [],
            "roleSets": [],
            "groupSets": [],
            "userSets": [],
        }
        is_valid, error_msg = validate_fresh_installation_iam(iam_config)
        assert is_valid is True
        assert error_msg == ""
