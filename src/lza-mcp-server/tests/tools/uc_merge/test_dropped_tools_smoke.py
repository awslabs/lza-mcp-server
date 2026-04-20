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

"""Smoke tests verifying dropped tools are not registered and modules are removed.

Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 5.2, 5.3, 5.4
"""

import importlib
import pytest
from pathlib import Path
from unittest.mock import Mock


TOOLS_UC_MERGE_DIR = Path(__file__).resolve().parents[3] / (
    "awslabs/lza_mcp_server/tools/uc_merge"
)


@pytest.mark.unit
@pytest.mark.uc_merge
class TestDroppedToolsNotRegistered:
    """Verify readUcFile, updateUcFile, readLzaConfigFile are not registered."""

    @pytest.fixture
    def registered_tools(self):
        """Register UC merge tools and capture registered tool names."""
        from awslabs.lza_mcp_server.tools.uc_merge.manage_uc_merge_tools import (
            register_uc_merge_tools,
        )

        registered = {}

        def tool_decorator(**kwargs):
            def wrapper(func):
                registered[func.__name__] = func
                return func

            return wrapper

        mcp = Mock()
        mcp.tool = tool_decorator
        register_uc_merge_tools(mcp, Mock())
        return registered

    def test_readUcFile_not_registered(self, registered_tools):
        """Requirement 1.1: readUcFile SHALL NOT be registered."""
        assert "readUcFile" not in registered_tools

    def test_updateUcFile_not_registered(self, registered_tools):
        """Requirement 2.1: updateUcFile SHALL NOT be registered."""
        assert "updateUcFile" not in registered_tools

    def test_readLzaConfigFile_not_registered(self, registered_tools):
        """Requirement 3.1: readLzaConfigFile SHALL NOT be registered."""
        assert "readLzaConfigFile" not in registered_tools

    def test_only_six_tools_registered(self, registered_tools):
        """After dropping 3 tools, exactly 6 tools should be registered."""
        assert len(registered_tools) == 6
        expected = {
            "validateLzaForUcMerge",
            "get_uc_releases",
            "get_uc_network_models",
            "start_uc_merge_session",
            "getUcNetworkCustomizationGuide",
            "copyUcToLzaConfig",
        }
        assert set(registered_tools.keys()) == expected


@pytest.mark.unit
@pytest.mark.uc_merge
class TestDroppedModulesRemoved:
    """Verify implementation files for dropped tools are deleted."""

    def test_read_uc_file_module_removed(self):
        """Requirement 1.2: read_uc_file.py SHALL be removed."""
        assert not (TOOLS_UC_MERGE_DIR / "read_uc_file.py").exists()

    def test_update_uc_file_module_removed(self):
        """Requirement 2.2: update_uc_file.py SHALL be removed."""
        assert not (TOOLS_UC_MERGE_DIR / "update_uc_file.py").exists()

    def test_read_lza_config_file_module_removed(self):
        """Requirement 3.2: read_lza_config_file.py SHALL be removed."""
        assert not (TOOLS_UC_MERGE_DIR / "read_lza_config_file.py").exists()

    def test_session_manager_module_removed(self):
        """Requirement 4.1: session_manager.py SHALL be removed."""
        assert not (TOOLS_UC_MERGE_DIR / "session_manager.py").exists()

    def test_read_uc_file_not_importable(self):
        """read_uc_file module should not be importable."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(
                "awslabs.lza_mcp_server.tools.uc_merge.read_uc_file"
            )

    def test_update_uc_file_not_importable(self):
        """update_uc_file module should not be importable."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(
                "awslabs.lza_mcp_server.tools.uc_merge.update_uc_file"
            )

    def test_session_manager_not_importable(self):
        """session_manager module should not be importable."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(
                "awslabs.lza_mcp_server.tools.uc_merge.session_manager"
            )


@pytest.mark.unit
@pytest.mark.uc_merge
class TestCommonLegacyGlobalsRemoved:
    """Verify common.py does not contain legacy global state."""

    def test_no_extracted_lza_config_path_variable(self):
        """Requirement 5.1: common SHALL NOT contain _extracted_lza_config_path."""
        import awslabs.lza_mcp_server.tools.uc_merge.common as common

        assert not hasattr(common, "_extracted_lza_config_path")

    def test_no_set_extracted_lza_config_path(self):
        """Requirement 5.2: common SHALL NOT contain set_extracted_lza_config_path."""
        import awslabs.lza_mcp_server.tools.uc_merge.common as common

        assert not hasattr(common, "set_extracted_lza_config_path")

    def test_no_get_extracted_lza_config_path(self):
        """Requirement 5.3: common SHALL NOT contain get_extracted_lza_config_path."""
        import awslabs.lza_mcp_server.tools.uc_merge.common as common

        assert not hasattr(common, "get_extracted_lza_config_path")

    def test_retained_functions_still_exist(self):
        """Requirement 5.5: retained functions should still be available."""
        import awslabs.lza_mcp_server.tools.uc_merge.common as common

        assert hasattr(common, "get_uc_base_path")
        assert hasattr(common, "UC_BASE_PATH")
        assert hasattr(common, "get_uc_release_path")
        assert hasattr(common, "get_uc_network_model_path")
        assert hasattr(common, "DEFAULT_UC_RELEASE")
        assert hasattr(common, "validate_path_security")
        assert hasattr(common, "create_error_response")
        assert hasattr(common, "create_success_response")
        assert hasattr(common, "categorize_uc_merge_error")
        assert hasattr(common, "format_file_size")


@pytest.mark.unit
@pytest.mark.uc_merge
class TestDescriptionsDroppedEntries:
    """Verify descriptions.py does not contain entries for dropped tools."""

    def test_no_readUcFile_description(self):
        """Requirement 11.2: readUcFile SHALL NOT be in DESCRIPTIONS."""
        from awslabs.lza_mcp_server.tools.uc_merge.descriptions import DESCRIPTIONS

        assert "readUcFile" not in DESCRIPTIONS

    def test_no_updateUcFile_description(self):
        """Requirement 11.2: updateUcFile SHALL NOT be in DESCRIPTIONS."""
        from awslabs.lza_mcp_server.tools.uc_merge.descriptions import DESCRIPTIONS

        assert "updateUcFile" not in DESCRIPTIONS

    def test_no_readLzaConfigFile_description(self):
        """readLzaConfigFile SHALL NOT be in UC merge DESCRIPTIONS."""
        from awslabs.lza_mcp_server.tools.uc_merge.descriptions import DESCRIPTIONS

        assert "readLzaConfigFile" not in DESCRIPTIONS
