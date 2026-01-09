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

"""Validation utilities for UC merge operations."""

import re
from typing import Tuple, Any, Dict
import yaml


def validate_cidr_format(cidr: str) -> Tuple[bool, str]:
    """Validate CIDR notation format.

    Args:
        cidr: CIDR string to validate (e.g., "10.0.0.0/8")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not cidr or not isinstance(cidr, str):
        return False, "CIDR must be a non-empty string"

    # Pattern: X.X.X.X/Y where X is 0-255 and Y is 0-32
    cidr_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$"

    if not re.match(cidr_pattern, cidr):
        return (
            False,
            f"Invalid CIDR format: '{cidr}'. Expected format: X.X.X.X/Y (e.g., 10.0.0.0/8)",
        )

    # Validate octets and mask
    try:
        ip_part, mask_part = cidr.split("/")
        octets = [int(x) for x in ip_part.split(".")]
        mask = int(mask_part)

        # Check octet ranges (0-255)
        for octet in octets:
            if octet < 0 or octet > 255:
                return (
                    False,
                    f"Invalid CIDR: octet value {octet} out of range (0-255)",
                )

        # Check mask range (0-32)
        if mask < 0 or mask > 32:
            return (False, f"Invalid CIDR: mask value {mask} out of range (0-32)")

    except (ValueError, AttributeError):
        return (False, f"Invalid CIDR format: '{cidr}'")

    return True, ""


def validate_asn_range(asn: int) -> Tuple[bool, str]:
    """Validate AWS Transit Gateway ASN is in private range.

    Args:
        asn: Autonomous System Number

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(asn, int):
        return False, "ASN must be an integer"

    # Private ASN range for Transit Gateway
    if asn < 64512 or asn > 65534:
        return (
            False,
            f"ASN {asn} out of valid range. Transit Gateway ASN must be between 64512 and 65534",
        )

    return True, ""


def validate_vpc_mask_length(mask_length: int) -> Tuple[bool, str]:
    """Validate VPC mask length is in reasonable range.

    Args:
        mask_length: VPC CIDR mask length

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(mask_length, int):
        return False, "Mask length must be an integer"

    # VPC mask lengths typically 16-28
    if mask_length < 16 or mask_length > 28:
        return (False, f"VPC mask length {mask_length} out of reasonable range (16-28)")

    return True, ""


def validate_subnet_mask_length(subnet_mask: int, vpc_mask: int) -> Tuple[bool, str]:
    """Validate subnet mask length is larger than VPC mask.

    Args:
        subnet_mask: Subnet CIDR mask length
        vpc_mask: VPC CIDR mask length

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(subnet_mask, int) or not isinstance(vpc_mask, int):
        return False, "Mask lengths must be integers"

    if subnet_mask <= vpc_mask:
        return (
            False,
            f"Subnet mask ({subnet_mask}) must be larger than VPC mask ({vpc_mask})",
        )

    if subnet_mask > 28:
        return (False, f"Subnet mask {subnet_mask} too large (maximum 28)")

    return True, ""


def validate_yaml_syntax(yaml_content: str) -> Tuple[bool, str]:
    """Validate YAML syntax.

    Args:
        yaml_content: YAML content as string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not yaml_content:
        return False, "YAML content cannot be empty"

    try:
        yaml.safe_load(yaml_content)
        return True, ""
    except yaml.YAMLError as e:
        return (False, f"Invalid YAML syntax: {str(e)}")


def validate_fresh_installation_accounts(
    accounts_config: Dict[str, Any],
) -> Tuple[bool, str]:
    """Validate that accounts-config.yaml represents a fresh installation.

    A fresh installation should have:
    - Only 3 mandatory accounts (Management, LogArchive, Audit)
    - Empty or missing workloadAccounts section

    Args:
        accounts_config: Parsed accounts-config.yaml content

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(accounts_config, dict):
        return False, "Accounts configuration must be a dictionary"

    # Check workloadAccounts
    workload_accounts = accounts_config.get("workloadAccounts", [])

    if workload_accounts is None:
        workload_accounts = []

    if not isinstance(workload_accounts, list):
        return (False, "workloadAccounts must be a list or empty")

    if len(workload_accounts) > 0:
        return (
            False,
            f"Installation is not fresh: workloadAccounts contains {len(workload_accounts)} accounts. "
            "UC merge requires a fresh LZA installation with only 3 mandatory accounts.",
        )

    return True, ""


def validate_fresh_installation_network(
    network_config: Dict[str, Any],
) -> Tuple[bool, str]:
    """Validate that network-config.yaml represents a fresh installation.

    A fresh installation should have:
    - Empty transitGateways array
    - Empty endpointPolicies array
    - Empty vpcs array

    Args:
        network_config: Parsed network-config.yaml content

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(network_config, dict):
        return False, "Network configuration must be a dictionary"

    # Check required arrays are empty
    required_empty_fields = ["transitGateways", "endpointPolicies", "vpcs"]

    for field in required_empty_fields:
        value = network_config.get(field, [])

        if value is None:
            value = []

        if not isinstance(value, list):
            return (False, f"Network configuration field '{field}' must be a list")

        if len(value) > 0:
            return (
                False,
                f"Installation is not fresh: network-config.yaml contains {len(value)} {field}. "
                "UC merge requires minimal network configuration.",
            )

    return True, ""


def validate_fresh_installation_iam(iam_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that iam-config.yaml represents a fresh installation.

    A fresh installation should have:
    - Empty providers array
    - Empty policySets array
    - Empty roleSets array
    - Empty groupSets array
    - Empty userSets array

    Args:
        iam_config: Parsed iam-config.yaml content

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(iam_config, dict):
        return False, "IAM configuration must be a dictionary"

    # Check required arrays are empty
    required_empty_fields = [
        "providers",
        "policySets",
        "roleSets",
        "groupSets",
        "userSets",
    ]

    for field in required_empty_fields:
        value = iam_config.get(field, [])

        if value is None:
            value = []

        if not isinstance(value, list):
            return (False, f"IAM configuration field '{field}' must be a list")

        if len(value) > 0:
            return (
                False,
                f"Installation is not fresh: iam-config.yaml contains {len(value)} {field}. "
                "UC merge requires minimal IAM configuration.",
            )

    return True, ""


def validate_network_model(network_model: str) -> Tuple[bool, str]:
    """Validate network model name.

    Args:
        network_model: Network model name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not network_model:
        return False, "Network model cannot be empty"

    if not isinstance(network_model, str):
        return False, "Network model must be a string"

    # We don't enforce known models to allow for future additions
    # Just validate it's a reasonable string
    if not re.match(r"^[a-z0-9-]+$", network_model):
        return (
            False,
            f"Invalid network model format: '{network_model}'. "
            "Must contain only lowercase letters, numbers, and hyphens",
        )

    return True, ""


def validate_uc_release(uc_release: str) -> Tuple[bool, str]:
    """Validate UC release version format.

    Args:
        uc_release: UC release version (e.g., "v1.0.0")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not uc_release:
        return False, "UC release cannot be empty"

    if not isinstance(uc_release, str):
        return False, "UC release must be a string"

    # Validate version format (e.g., v1.0.0, v2.1.3)
    version_pattern = r"^v\d+\.\d+\.\d+$"

    if not re.match(version_pattern, uc_release):
        return (
            False,
            f"Invalid UC release format: '{uc_release}'. "
            "Expected format: vX.Y.Z (e.g., v1.0.0)",
        )

    return True, ""
