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

"""Unit tests for update_lza_config_file module."""

import pytest
import yaml
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.config.update_lza_config_file import (
    _parse_key_path,
    _get_nested_value,
    _set_nested_value,
    _validate_update_values,
    update_lza_config_file,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

SAMPLE_NETWORK_YAML = {
    "vpcs": [
        {
            "vpcName": "prod-vpc",
            "account": "Production",
            "cidrs": [{"value": "10.1.0.0/16"}],
        },
        {
            "vpcName": "dev-vpc",
            "account": "Development",
            "cidrs": [{"value": "10.2.0.0/16"}],
        },
    ],
    "transitGateways": [],
    "endpointPolicies": [],
}

SAMPLE_ACCOUNTS_YAML = {
    "mandatoryAccounts": [
        {"name": "Management", "email": "mgmt@example.com"},
        {"name": "LogArchive", "email": "log@example.com"},
        {"name": "Audit", "email": "audit@example.com"},
    ],
    "workloadAccounts": [],
}

SAMPLE_REPLACEMENTS_YAML = {
    "globalReplacements": [
        {"key": "HomeRegion", "value": "us-east-1"},
        {"key": "HomeRegionIngressCidr", "value": "10.0.0.0/8"},
        {"key": "TransitGatewayASN", "value": 64512},
    ],
}


# ===========================================================================
# Pure function tests — _parse_key_path
# ===========================================================================


class TestParseKeyPath:
    def test_simple_key(self):
        assert _parse_key_path("homeRegion") == ["homeRegion"]

    def test_dotted_key(self):
        assert _parse_key_path("vpcs.vpcName") == ["vpcs", "vpcName"]

    def test_array_index(self):
        assert _parse_key_path("vpcs[0]") == ["vpcs", 0]

    def test_array_index_with_nested(self):
        assert _parse_key_path("mandatoryAccounts[2].email") == [
            "mandatoryAccounts",
            2,
            "email",
        ]

    def test_deep_nesting(self):
        assert _parse_key_path("vpcs[0].cidrs[1].value") == [
            "vpcs",
            0,
            "cidrs",
            1,
            "value",
        ]

    def test_multiple_array_indices(self):
        assert _parse_key_path("a[0].b[3].c") == ["a", 0, "b", 3, "c"]


# ===========================================================================
# Pure function tests — _get_nested_value
# ===========================================================================


class TestGetNestedValue:
    def test_top_level_key(self):
        assert _get_nested_value(SAMPLE_NETWORK_YAML, "transitGateways") == []

    def test_array_element(self):
        result = _get_nested_value(SAMPLE_NETWORK_YAML, "vpcs[0].vpcName")
        assert result == "prod-vpc"

    def test_deep_nested(self):
        result = _get_nested_value(SAMPLE_NETWORK_YAML, "vpcs[0].cidrs[0].value")
        assert result == "10.1.0.0/16"

    def test_missing_key_returns_none(self):
        assert _get_nested_value(SAMPLE_NETWORK_YAML, "nonexistent") is None

    def test_out_of_bounds_index_returns_none(self):
        assert _get_nested_value(SAMPLE_NETWORK_YAML, "vpcs[99].vpcName") is None

    def test_non_dict_non_list_returns_none(self):
        assert _get_nested_value({"a": "string"}, "a.b") is None

    def test_none_intermediate_returns_none(self):
        assert _get_nested_value({"a": None}, "a.b") is None


# ===========================================================================
# Pure function tests — _set_nested_value
# ===========================================================================


class TestSetNestedValue:
    def test_set_top_level(self):
        data = {"key": "old"}
        _set_nested_value(data, "key", "new")
        assert data["key"] == "new"

    def test_set_nested_dict(self):
        data = {"a": {"b": "old"}}
        _set_nested_value(data, "a.b", "new")
        assert data["a"]["b"] == "new"

    def test_set_array_element(self):
        data = {"items": ["a", "b", "c"]}
        _set_nested_value(data, "items[1]", "B")
        assert data["items"][1] == "B"

    def test_create_intermediate_dict(self):
        data = {}
        _set_nested_value(data, "a.b", "value")
        assert data["a"]["b"] == "value"

    def test_create_intermediate_list(self):
        # When the list is created empty, assigning index 0 raises IndexError
        # This is expected — insert mode should be used for appending to lists
        data = {}
        import pytest as _pt

        with _pt.raises(IndexError):
            _set_nested_value(data, "items[0]", "first")

    def test_empty_string_key_sets_empty_key(self):
        # An empty string is still a valid dict key in Python/YAML
        data = {"a": 1}
        _set_nested_value(data, "", "value")
        assert data[""] == "value"

    def test_add_new_key_to_existing_dict(self):
        data = {"existing": "value"}
        _set_nested_value(data, "newKey", "newValue")
        assert data["newKey"] == "newValue"


# ===========================================================================
# Pure function tests — _validate_update_values
# ===========================================================================


class TestValidateUpdateValues:
    def test_valid_cidr(self):
        errors = _validate_update_values({"HomeCidr": "10.0.0.0/16"})
        assert errors == []

    def test_invalid_cidr_by_key_name(self):
        errors = _validate_update_values({"HomeCidr": "not-a-cidr"})
        assert len(errors) == 1
        assert "HomeCidr" in errors[0]

    def test_invalid_cidr_by_slash_in_value(self):
        errors = _validate_update_values({"SomeField": "999.999.999.999/99"})
        assert len(errors) == 1

    def test_valid_asn(self):
        errors = _validate_update_values({"TransitGatewayASN": 64512})
        assert errors == []

    def test_invalid_asn(self):
        errors = _validate_update_values({"TransitGatewayASN": 100})
        assert len(errors) == 1
        assert "ASN" in errors[0]

    def test_valid_vpc_mask(self):
        errors = _validate_update_values({"DevVpcMaskLength": 24})
        assert errors == []

    def test_invalid_vpc_mask(self):
        errors = _validate_update_values({"DevVpcMaskLength": 8})
        assert len(errors) == 1

    def test_valid_subnet_mask(self):
        errors = _validate_update_values({"SubnetMaskLength": 24})
        assert errors == []

    def test_invalid_subnet_mask(self):
        errors = _validate_update_values({"SubnetMaskLength": 30})
        assert len(errors) == 1

    def test_non_matching_string_passes(self):
        errors = _validate_update_values({"vpcName": "my-vpc"})
        assert errors == []

    def test_non_matching_int_passes(self):
        errors = _validate_update_values({"count": 5})
        assert errors == []

    def test_multiple_errors(self):
        errors = _validate_update_values(
            {
                "BadCidr": "nope/nope",
                "BadASN": 1,
            }
        )
        assert len(errors) == 2


# ===========================================================================
# Integration tests — update_lza_config_file (async, uses filesystem)
# ===========================================================================


@pytest.fixture
def config_dir(tmp_path):
    """Create a temporary LZA config directory with sample files."""
    retrieved = tmp_path / "retrieved-config"
    retrieved.mkdir()

    # network-config.yaml
    (retrieved / "network-config.yaml").write_text(
        yaml.dump(SAMPLE_NETWORK_YAML, default_flow_style=False, sort_keys=False)
    )

    # accounts-config.yaml
    (retrieved / "accounts-config.yaml").write_text(
        yaml.dump(SAMPLE_ACCOUNTS_YAML, default_flow_style=False, sort_keys=False)
    )

    # replacements-config.yaml
    (retrieved / "replacements-config.yaml").write_text(
        yaml.dump(SAMPLE_REPLACEMENTS_YAML, default_flow_style=False, sort_keys=False)
    )

    # global-config.yaml (simple flat file)
    (retrieved / "global-config.yaml").write_text(
        yaml.dump(
            {"homeRegion": "us-east-1", "enabledRegions": ["us-east-1"]},
            default_flow_style=False,
            sort_keys=False,
        )
    )

    # empty.yaml
    (retrieved / "empty.yaml").write_text("")

    # invalid.yaml
    (retrieved / "invalid.yaml").write_text(":\n  bad: [yaml\n  broken")

    # a subdirectory (to test not-a-file check)
    (retrieved / "subdir").mkdir()

    return tmp_path


def _patch_base_path(config_dir):
    """Return a patch context manager that overrides LZA_CONFIG_BASE_PATH."""
    return patch(
        "awslabs.lza_mcp_server.tools.config.update_lza_config_file.LZA_CONFIG_BASE_PATH",
        config_dir,
    )


# ---------------------------------------------------------------------------
# Parameter validation tests
# ---------------------------------------------------------------------------


class TestParameterValidation:
    @pytest.mark.asyncio
    async def test_missing_file_path(self, mock_mcp_context):
        result = await update_lza_config_file(
            mock_mcp_context, file_path="", updates={"a": 1}
        )
        assert result["success"] is False
        assert result["error_code"] == "MISSING_FILE_PATH"

    @pytest.mark.asyncio
    async def test_mutually_exclusive_params(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates={"vpcs[0].vpcName": "x"},
                insert_path="vpcs",
                insert_value={"vpcName": "y"},
            )
        assert result["success"] is False
        assert result["error_code"] == "MUTUALLY_EXCLUSIVE_PARAMS"

    @pytest.mark.asyncio
    async def test_no_params_provided(self, mock_mcp_context):
        result = await update_lza_config_file(
            mock_mcp_context, file_path="network-config.yaml"
        )
        assert result["success"] is False
        assert result["error_code"] == "MISSING_PARAMS"

    @pytest.mark.asyncio
    async def test_insert_path_without_value(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs",
            )
        assert result["success"] is False
        assert result["error_code"] == "INCOMPLETE_INSERT_PARAMS"

    @pytest.mark.asyncio
    async def test_insert_value_without_path(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_value={"vpcName": "new"},
            )
        assert result["success"] is False
        assert result["error_code"] == "INCOMPLETE_INSERT_PARAMS"

    @pytest.mark.asyncio
    async def test_insert_value_not_dict(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value="not-a-dict",
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INSERT_VALUE"

    @pytest.mark.asyncio
    async def test_updates_not_dict(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates="not-a-dict",
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_UPDATES"


# ---------------------------------------------------------------------------
# File/path validation tests
# ---------------------------------------------------------------------------


class TestFilePathValidation:
    @pytest.mark.asyncio
    async def test_config_not_retrieved(self, mock_mcp_context, tmp_path):
        # Point to a directory that does NOT have retrieved-config
        with _patch_base_path(tmp_path / "nonexistent"):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "CONFIG_NOT_RETRIEVED"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="../../../etc/passwd",
                updates={"a": 1},
            )
        assert result["success"] is False
        assert (
            "traversal" in result["error"].lower()
            or "PATH_TRAVERSAL" in result["error_code"]
        )

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="nonexistent.yaml",
                updates={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_path_is_directory(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="subdir",
                updates={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "NOT_A_FILE"

    @pytest.mark.asyncio
    async def test_invalid_yaml_file(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="invalid.yaml",
                updates={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "YAML_PARSE_ERROR"

    @pytest.mark.asyncio
    async def test_empty_yaml_file_treated_as_empty_dict(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="empty.yaml",
                updates={"newKey": "newValue"},
            )
        assert result["success"] is True
        # Verify the file was written with the new key
        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "empty.yaml").read_text()
        )
        assert content["newKey"] == "newValue"


# ---------------------------------------------------------------------------
# Update mode tests
# ---------------------------------------------------------------------------


class TestUpdateMode:
    @pytest.mark.asyncio
    async def test_update_top_level_value(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"homeRegion": "eu-west-1"},
            )
        assert result["success"] is True
        assert result["updates_applied"]["homeRegion"]["old"] == "us-east-1"
        assert result["updates_applied"]["homeRegion"]["new"] == "eu-west-1"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "global-config.yaml").read_text()
        )
        assert content["homeRegion"] == "eu-west-1"

    @pytest.mark.asyncio
    async def test_update_nested_array_value(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates={"vpcs[0].vpcName": "renamed-vpc"},
            )
        assert result["success"] is True
        assert result["updates_applied"]["vpcs[0].vpcName"]["old"] == "prod-vpc"
        assert result["updates_applied"]["vpcs[0].vpcName"]["new"] == "renamed-vpc"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert content["vpcs"][0]["vpcName"] == "renamed-vpc"

    @pytest.mark.asyncio
    async def test_update_deep_nested_value(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates={"vpcs[0].cidrs[0].value": "10.99.0.0/16"},
            )
        assert result["success"] is True
        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert content["vpcs"][0]["cidrs"][0]["value"] == "10.99.0.0/16"

    @pytest.mark.asyncio
    async def test_update_multiple_values(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="accounts-config.yaml",
                updates={
                    "mandatoryAccounts[0].email": "new-mgmt@example.com",
                    "mandatoryAccounts[1].email": "new-log@example.com",
                },
            )
        assert result["success"] is True
        assert len(result["updates_applied"]) == 2

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "accounts-config.yaml").read_text()
        )
        assert content["mandatoryAccounts"][0]["email"] == "new-mgmt@example.com"
        assert content["mandatoryAccounts"][1]["email"] == "new-log@example.com"

    @pytest.mark.asyncio
    async def test_update_adds_new_key(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"brandNewSetting": "hello"},
            )
        assert result["success"] is True
        assert result["updates_applied"]["brandNewSetting"]["old"] is None
        assert result["updates_applied"]["brandNewSetting"]["new"] == "hello"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "global-config.yaml").read_text()
        )
        assert content["brandNewSetting"] == "hello"

    @pytest.mark.asyncio
    async def test_update_replacements_config_global_replacements(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="replacements-config.yaml",
                updates={"HomeRegion": "eu-north-1"},
            )
        assert result["success"] is True
        assert result["updates_applied"]["HomeRegion"]["old"] == "us-east-1"
        assert result["updates_applied"]["HomeRegion"]["new"] == "eu-north-1"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "replacements-config.yaml").read_text()
        )
        # Verify the globalReplacements array was updated
        home_region_entry = next(
            item
            for item in content["globalReplacements"]
            if item["key"] == "HomeRegion"
        )
        assert home_region_entry["value"] == "eu-north-1"

    @pytest.mark.asyncio
    async def test_update_replacements_config_key_not_in_global_replacements(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="replacements-config.yaml",
                updates={"BrandNewKey": "some-value"},
            )
        assert result["success"] is True
        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "replacements-config.yaml").read_text()
        )
        assert content["BrandNewKey"] == "some-value"

    @pytest.mark.asyncio
    async def test_update_validation_failure_cidr(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"HomeCidr": "not-valid"},
            )
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"
        assert len(result["context"]["validation_errors"]) == 1

    @pytest.mark.asyncio
    async def test_update_validation_failure_asn(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"TransitGatewayASN": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Insert mode tests
# ---------------------------------------------------------------------------


class TestInsertMode:
    @pytest.mark.asyncio
    async def test_insert_into_existing_list(self, mock_mcp_context, config_dir):
        new_vpc = {
            "vpcName": "staging-vpc",
            "account": "Staging",
            "cidrs": [{"value": "10.5.0.0/16"}],
        }
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value=new_vpc,
            )
        assert result["success"] is True
        assert result["inserted"]["path"] == "vpcs"
        assert result["inserted"]["new_index"] == 2
        assert result["inserted"]["value"]["vpcName"] == "staging-vpc"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert len(content["vpcs"]) == 3
        assert content["vpcs"][2]["vpcName"] == "staging-vpc"

    @pytest.mark.asyncio
    async def test_insert_into_empty_list(self, mock_mcp_context, config_dir):
        new_tgw = {"name": "main-tgw", "asn": 64512}
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="transitGateways",
                insert_value=new_tgw,
            )
        assert result["success"] is True
        assert result["inserted"]["new_index"] == 0

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert len(content["transitGateways"]) == 1
        assert content["transitGateways"][0]["name"] == "main-tgw"

    @pytest.mark.asyncio
    async def test_insert_creates_list_if_path_missing(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                insert_path="newListField",
                insert_value={"item": "first"},
            )
        assert result["success"] is True
        assert result["inserted"]["new_index"] == 0

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "global-config.yaml").read_text()
        )
        assert content["newListField"] == [{"item": "first"}]

    @pytest.mark.asyncio
    async def test_insert_target_not_a_list(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                insert_path="homeRegion",
                insert_value={"item": "value"},
            )
        assert result["success"] is False
        assert result["error_code"] == "INSERT_TARGET_NOT_LIST"

    @pytest.mark.asyncio
    async def test_insert_workload_account(self, mock_mcp_context, config_dir):
        new_account = {
            "name": "SharedServices",
            "email": "shared@example.com",
            "organizationalUnit": "Infrastructure",
        }
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="accounts-config.yaml",
                insert_path="workloadAccounts",
                insert_value=new_account,
            )
        assert result["success"] is True

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "accounts-config.yaml").read_text()
        )
        assert len(content["workloadAccounts"]) == 1
        assert content["workloadAccounts"][0]["name"] == "SharedServices"

    @pytest.mark.asyncio
    async def test_insert_nested_list(self, mock_mcp_context, config_dir):
        new_cidr = {"value": "10.99.0.0/16"}
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs[0].cidrs",
                insert_value=new_cidr,
            )
        assert result["success"] is True
        assert result["inserted"]["new_index"] == 1

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert len(content["vpcs"][0]["cidrs"]) == 2
        assert content["vpcs"][0]["cidrs"][1]["value"] == "10.99.0.0/16"


# ---------------------------------------------------------------------------
# Write failure tests
# ---------------------------------------------------------------------------


class TestWriteFailures:
    @pytest.mark.asyncio
    async def test_file_read_os_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            # Mock open to raise OSError on read (works even when running as root)
            real_open = open

            def _failing_open(path, *args, **kwargs):
                if "global-config.yaml" in str(path) and (not args or "r" in args[0]):
                    raise OSError("Permission denied")
                return real_open(path, *args, **kwargs)

            with patch("builtins.open", side_effect=_failing_open):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="global-config.yaml",
                    updates={"homeRegion": "eu-west-1"},
                )
            assert result["success"] is False
            assert result["error_code"] in ("FILE_READ_ERROR", "YAML_PARSE_ERROR")

    @pytest.mark.asyncio
    async def test_file_write_os_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            # Mock open to raise OSError on write (works even when running as root)
            real_open = open

            def _failing_open(path, *args, **kwargs):
                if "global-config.yaml" in str(path) and args and "w" in args[0]:
                    raise OSError("Permission denied")
                return real_open(path, *args, **kwargs)

            with patch("builtins.open", side_effect=_failing_open):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="global-config.yaml",
                    updates={"homeRegion": "eu-west-1"},
                )
            assert result["success"] is False
            assert result["error_code"] == "FILE_WRITE_ERROR"


# ---------------------------------------------------------------------------
# Response structure tests
# ---------------------------------------------------------------------------


class TestResponseStructure:
    @pytest.mark.asyncio
    async def test_update_success_response_shape(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"homeRegion": "eu-west-1"},
            )
        assert result["success"] is True
        assert "file_path" in result
        assert "updates_applied" in result
        assert "validation_errors" in result
        assert result["validation_errors"] == []
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_insert_success_response_shape(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value={"vpcName": "test"},
            )
        assert result["success"] is True
        assert "file_path" in result
        assert "inserted" in result
        assert "validation_errors" in result
        assert result["validation_errors"] == []
        assert "next_steps" in result
        assert "path" in result["inserted"]
        assert "value" in result["inserted"]
        assert "new_index" in result["inserted"]

    @pytest.mark.asyncio
    async def test_error_response_shape(self, mock_mcp_context):
        result = await update_lza_config_file(
            mock_mcp_context, file_path="", updates={"a": 1}
        )
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert "category" in result
        assert "troubleshooting" in result


# ---------------------------------------------------------------------------
# Tool registration test
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_get_nested_value_type_error_returns_none(self):
        # Trigger the except (TypeError) branch
        assert _get_nested_value({"a": 42}, "a[0]") is None

    def test_set_nested_value_list_navigation(self):
        # Navigate through a list in the middle of the path
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        _set_nested_value(data, "items[1].name", "updated")
        assert data["items"][1]["name"] == "updated"

    @pytest.mark.asyncio
    async def test_yaml_dump_error(self, mock_mcp_context, config_dir):
        """Cover the yaml.YAMLError branch in _write_yaml by mocking yaml.dump."""
        with _patch_base_path(config_dir):
            with patch(
                "awslabs.lza_mcp_server.tools.config.update_lza_config_file.yaml.dump",
                side_effect=yaml.YAMLError("mock dump failure"),
            ):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="global-config.yaml",
                    updates={"homeRegion": "eu-west-1"},
                )
        assert result["success"] is False
        assert result["error_code"] == "SERIALIZATION_ERROR"

    @pytest.mark.asyncio
    async def test_yaml_validation_failure_after_dump(
        self, mock_mcp_context, config_dir
    ):
        """Cover the validate_yaml_syntax failure branch in _write_yaml."""
        with _patch_base_path(config_dir):
            with patch(
                "awslabs.lza_mcp_server.tools.config.update_lza_config_file.validate_yaml_syntax",
                return_value=(False, "mock syntax error"),
            ):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="global-config.yaml",
                    updates={"homeRegion": "eu-west-1"},
                )
        assert result["success"] is False
        assert result["error_code"] == "YAML_GENERATION_ERROR"
        assert "mock syntax error" in result["error"]

    @pytest.mark.asyncio
    async def test_insert_yaml_dump_error(self, mock_mcp_context, config_dir):
        """Cover yaml.dump error in insert mode."""
        with _patch_base_path(config_dir):
            with patch(
                "awslabs.lza_mcp_server.tools.config.update_lza_config_file.yaml.dump",
                side_effect=yaml.YAMLError("mock dump failure"),
            ):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="network-config.yaml",
                    insert_path="vpcs",
                    insert_value={"vpcName": "test"},
                )
        assert result["success"] is False
        assert result["error_code"] == "SERIALIZATION_ERROR"


# ---------------------------------------------------------------------------
# Delete mode tests
# ---------------------------------------------------------------------------


class TestDeleteMode:
    @pytest.mark.asyncio
    async def test_delete_top_level_key(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                delete_path="homeRegion",
            )
        assert result["success"] is True
        assert result["deleted"]["path"] == "homeRegion"
        assert result["deleted"]["old_value"] == "us-east-1"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "global-config.yaml").read_text()
        )
        assert "homeRegion" not in content

    @pytest.mark.asyncio
    async def test_delete_list_item_by_index(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                delete_path="vpcs[1]",
            )
        assert result["success"] is True
        assert result["deleted"]["old_value"]["vpcName"] == "dev-vpc"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert len(content["vpcs"]) == 1
        assert content["vpcs"][0]["vpcName"] == "prod-vpc"

    @pytest.mark.asyncio
    async def test_delete_nested_key(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                delete_path="vpcs[0].account",
            )
        assert result["success"] is True
        assert result["deleted"]["old_value"] == "Production"

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert "account" not in content["vpcs"][0]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                delete_path="nonexistentKey",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_PATH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_index_out_of_range(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                delete_path="vpcs[99]",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_INDEX_OUT_OF_RANGE"

    @pytest.mark.asyncio
    async def test_delete_parent_not_found(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                delete_path="nonexistent.child",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_PATH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_non_index_from_list(self, mock_mcp_context, config_dir):
        """Trying to delete a string key from a list parent should fail."""
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                delete_path="vpcs.notAnIndex",
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_DELETE_PATH"

    @pytest.mark.asyncio
    async def test_delete_from_scalar_parent(self, mock_mcp_context, config_dir):
        """Trying to delete from a scalar value (string) should fail."""
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                delete_path="homeRegion.child",
            )
        assert result["success"] is False
        # Parent "homeRegion" is a string — not a dict or list
        assert result["error_code"] == "INVALID_DELETE_PATH"

    @pytest.mark.asyncio
    async def test_delete_response_shape(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                delete_path="homeRegion",
            )
        assert result["success"] is True
        assert "file_path" in result
        assert "deleted" in result
        assert "path" in result["deleted"]
        assert "old_value" in result["deleted"]
        assert "validation_errors" in result
        assert result["validation_errors"] == []
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_delete_mutually_exclusive_with_updates(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="global-config.yaml",
                updates={"homeRegion": "eu-west-1"},
                delete_path="homeRegion",
            )
        assert result["success"] is False
        assert result["error_code"] == "MUTUALLY_EXCLUSIVE_PARAMS"

    @pytest.mark.asyncio
    async def test_delete_mutually_exclusive_with_insert(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                insert_path="vpcs",
                insert_value={"vpcName": "new"},
                delete_path="vpcs[0]",
            )
        assert result["success"] is False
        assert result["error_code"] == "MUTUALLY_EXCLUSIVE_PARAMS"

    @pytest.mark.asyncio
    async def test_delete_parent_index_out_of_range(self, mock_mcp_context, config_dir):
        """Parent navigation through list with bad index should fail."""
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                delete_path="vpcs[99].vpcName",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_PATH_NOT_FOUND"


# ---------------------------------------------------------------------------
# Additional branch coverage tests
# ---------------------------------------------------------------------------


class TestBranchCoverage:
    """Tests targeting specific uncovered branches for near-100% coverage."""

    @pytest.mark.asyncio
    async def test_update_through_list_intermediate(self, mock_mcp_context, config_dir):
        """Cover _set_nested_value line 99 and _get_nested_value list branch via full tool call."""
        # vpcs[0].cidrs[0].value navigates: dict->list->dict->list->dict
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="network-config.yaml",
                updates={"vpcs[1].cidrs[0].value": "10.88.0.0/16"},
            )
        assert result["success"] is True
        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "network-config.yaml").read_text()
        )
        assert content["vpcs"][1]["cidrs"][0]["value"] == "10.88.0.0/16"

    @pytest.mark.asyncio
    async def test_update_list_element_directly(self, mock_mcp_context, config_dir):
        """Cover _set_nested_value final elif (assign to list element) via full tool call."""
        # Create a file with a simple list to update by index
        simple_yaml = {"tags": ["alpha", "beta", "gamma"]}
        (config_dir / "retrieved-config" / "tags.yaml").write_text(
            yaml.dump(simple_yaml, default_flow_style=False, sort_keys=False)
        )
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="tags.yaml",
                updates={"tags[1]": "BETA"},
            )
        assert result["success"] is True
        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "tags.yaml").read_text()
        )
        assert content["tags"][1] == "BETA"

    @pytest.mark.asyncio
    async def test_delete_navigate_through_list_parent(
        self, mock_mcp_context, config_dir
    ):
        """Cover _apply_delete list parent navigation (line 545)."""
        nested_yaml = {
            "items": [
                {"name": "first", "tags": ["a", "b"]},
                {"name": "second", "tags": ["c"]},
            ]
        }
        (config_dir / "retrieved-config" / "nested.yaml").write_text(
            yaml.dump(nested_yaml, default_flow_style=False, sort_keys=False)
        )
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="nested.yaml",
                delete_path="items[0].name",
            )
        assert result["success"] is True
        assert result["deleted"]["old_value"] == "first"

    @pytest.mark.asyncio
    async def test_delete_list_parent_index_error(self, mock_mcp_context, config_dir):
        """Cover _apply_delete except (IndexError, TypeError) in list parent nav (line 564)."""
        nested_yaml = {"items": [{"name": "only"}]}
        (config_dir / "retrieved-config" / "nested2.yaml").write_text(
            yaml.dump(nested_yaml, default_flow_style=False, sort_keys=False)
        )
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="nested2.yaml",
                delete_path="items[99].name",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_PATH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_list_parent_type_error(self, mock_mcp_context, config_dir):
        """Cover _apply_delete except TypeError when list index is not int."""
        nested_yaml = {"items": ["a", "b"]}
        (config_dir / "retrieved-config" / "nested3.yaml").write_text(
            yaml.dump(nested_yaml, default_flow_style=False, sort_keys=False)
        )
        with _patch_base_path(config_dir):
            result = await update_lza_config_file(
                mock_mcp_context,
                file_path="nested3.yaml",
                delete_path="items.badkey.child",
            )
        assert result["success"] is False
        assert result["error_code"] == "DELETE_PATH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_write_failure(self, mock_mcp_context, config_dir):
        """Cover _write_yaml FILE_WRITE_ERROR via delete mode."""
        with _patch_base_path(config_dir):
            # Mock open to raise OSError on write (works even when running as root)
            real_open = open

            def _failing_open(path, *args, **kwargs):
                if "global-config.yaml" in str(path) and args and "w" in args[0]:
                    raise OSError("Permission denied")
                return real_open(path, *args, **kwargs)

            with patch("builtins.open", side_effect=_failing_open):
                result = await update_lza_config_file(
                    mock_mcp_context,
                    file_path="global-config.yaml",
                    delete_path="homeRegion",
                )
            assert result["success"] is False
            assert result["error_code"] == "FILE_WRITE_ERROR"
