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

"""Property-based tests for file classification in getUcNetworkCustomizationGuide.

Feature: uc-workspace-rework, Property 4: File classification by type

Property 4: For any list of workspace file paths, the classification function SHALL
assign every .yaml/.yml file at the root level to config_files, every directory whose
name contains a policy keyword to policy_directories, and all other directories to
supporting_directories, with no file appearing in more than one category.

Validates: Requirements 8.2
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from awslabs.lza_mcp_server.tools.uc_merge.get_uc_network_customization_guide import (
    _scan_configuration_files,
    _is_policy_directory,
)


# --- Strategies ---

# Valid filename characters (no slashes, no dots at start for non-hidden)
_safe_chars = st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_")

_filename_base = st.text(_safe_chars, min_size=1, max_size=20)

# Policy keywords that trigger policy directory classification
POLICY_KEYWORDS = ["policy", "policies", "firewall", "rules", "rcp"]

# Generate a directory name that IS a policy directory
_policy_dir_name = st.one_of(
    # keyword alone
    st.sampled_from(POLICY_KEYWORDS),
    # keyword with prefix/suffix
    st.tuples(_filename_base, st.sampled_from(POLICY_KEYWORDS), _filename_base).map(
        lambda t: f"{t[0]}-{t[1]}-{t[2]}"
    ),
)

# Generate a directory name that is NOT a policy directory
_non_policy_dir_name = _filename_base.filter(
    lambda name: not _is_policy_directory(name)
)

# Root-level YAML file
_root_yaml = st.one_of(
    _filename_base.map(lambda n: f"{n}.yaml"),
    _filename_base.map(lambda n: f"{n}.yml"),
)

# Root-level non-YAML file (e.g. .json, .txt, .md)
_root_non_yaml = _filename_base.map(lambda n: f"{n}.txt")

# File inside a policy directory
_policy_dir_file = st.tuples(_policy_dir_name, _filename_base).map(
    lambda t: f"{t[0]}/{t[1]}.yaml"
)

# File inside a non-policy directory
_non_policy_dir_file = st.tuples(_non_policy_dir_name, _filename_base).map(
    lambda t: f"{t[0]}/{t[1]}.yaml"
)

# Hidden file at root (should be excluded)
_hidden_file = _filename_base.map(lambda n: f".{n}.json")

# Mixed file list strategy
_file_list = st.lists(
    st.one_of(
        _root_yaml,
        _root_non_yaml,
        _policy_dir_file,
        _non_policy_dir_file,
        _hidden_file,
    ),
    min_size=0,
    max_size=30,
)


@pytest.mark.property
@pytest.mark.uc_merge
class TestFileClassificationProperty:
    """Property 4: File classification by type.

    **Validates: Requirements 8.2**
    """

    @given(file_list=_file_list)
    @settings(max_examples=150)
    def test_root_yaml_files_classified_as_config(self, file_list):
        """Every root-level .yaml/.yml file appears in config_files."""
        result = _scan_configuration_files(file_list)

        for path in file_list:
            if path.startswith("."):
                continue
            parts = path.split("/")
            if len(parts) == 1 and (path.endswith(".yaml") or path.endswith(".yml")):
                assert path in result["config_files"], (
                    f"Root YAML '{path}' missing from config_files"
                )

    @given(file_list=_file_list)
    @settings(max_examples=150)
    def test_policy_dirs_classified_correctly(self, file_list):
        """Directories with policy keywords appear in policy_directories."""
        result = _scan_configuration_files(file_list)

        for path in file_list:
            if path.startswith("."):
                continue
            parts = path.split("/")
            if len(parts) > 1:
                top_dir = parts[0]
                if not top_dir.startswith(".") and _is_policy_directory(top_dir):
                    assert top_dir in result["policy_directories"], (
                        f"Policy dir '{top_dir}' missing from policy_directories"
                    )

    @given(file_list=_file_list)
    @settings(max_examples=150)
    def test_non_policy_dirs_classified_as_supporting(self, file_list):
        """Non-policy directories appear in supporting_directories."""
        result = _scan_configuration_files(file_list)

        for path in file_list:
            if path.startswith("."):
                continue
            parts = path.split("/")
            if len(parts) > 1:
                top_dir = parts[0]
                if not top_dir.startswith(".") and not _is_policy_directory(top_dir):
                    assert top_dir in result["supporting_directories"], (
                        f"Non-policy dir '{top_dir}' missing from supporting_directories"
                    )

    @given(file_list=_file_list)
    @settings(max_examples=150)
    def test_no_overlap_between_categories(self, file_list):
        """No directory appears in both policy_directories and supporting_directories."""
        result = _scan_configuration_files(file_list)

        policy_set = set(result["policy_directories"])
        supporting_set = set(result["supporting_directories"])
        config_set = set(result["config_files"])

        # No overlap between policy and supporting directories
        overlap = policy_set & supporting_set
        assert not overlap, f"Overlap between policy and supporting: {overlap}"

        # Config files (root-level) should not appear in directory lists
        config_in_policy = config_set & policy_set
        config_in_supporting = config_set & supporting_set
        assert not config_in_policy, f"Config files in policy dirs: {config_in_policy}"
        assert not config_in_supporting, (
            f"Config files in supporting dirs: {config_in_supporting}"
        )

    @given(file_list=_file_list)
    @settings(max_examples=150)
    def test_hidden_files_excluded(self, file_list):
        """Hidden files (starting with .) are excluded from all categories."""
        result = _scan_configuration_files(file_list)

        all_items = (
            result["config_files"]
            + result["policy_directories"]
            + result["supporting_directories"]
        )
        for item in all_items:
            assert not item.startswith("."), f"Hidden item '{item}' should be excluded"
