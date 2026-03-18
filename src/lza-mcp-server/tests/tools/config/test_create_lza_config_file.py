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

"""Unit tests for create_lza_config_file module."""

import json
import pytest
import yaml
from unittest.mock import patch

from awslabs.lza_mcp_server.tools.config.create_lza_config_file import (
    _get_file_format,
    _serialize_content,
    create_lza_config_file,
)


# ===========================================================================
# Pure function tests — _get_file_format
# ===========================================================================


class TestGetFileFormat:
    def test_yaml_extension(self):
        assert _get_file_format("config.yaml") == "yaml"

    def test_yml_extension(self):
        assert _get_file_format("config.yml") == "yaml"

    def test_json_extension(self):
        assert _get_file_format("policy.json") == "json"

    def test_uppercase_yaml(self):
        assert _get_file_format("CONFIG.YAML") == "yaml"

    def test_uppercase_json(self):
        assert _get_file_format("POLICY.JSON") == "json"

    def test_mixed_case_yml(self):
        assert _get_file_format("Config.YmL") == "yaml"

    def test_unsupported_extension(self):
        assert _get_file_format("config.txt") is None

    def test_no_extension(self):
        assert _get_file_format("config") is None

    def test_path_with_directories(self):
        assert _get_file_format("iam-policies/boundary.json") == "json"

    def test_nested_path_yaml(self):
        assert _get_file_format("sub/dir/config.yaml") == "yaml"


# ===========================================================================
# Pure function tests — _serialize_content
# ===========================================================================


class TestSerializeContent:
    def test_serialize_yaml(self):
        content = {"key": "value", "list": [1, 2, 3]}
        result = _serialize_content(content, "yaml")
        parsed = yaml.safe_load(result)
        assert parsed == content

    def test_serialize_json(self):
        content = {"key": "value", "list": [1, 2, 3]}
        result = _serialize_content(content, "json")
        parsed = json.loads(result)
        assert parsed == content

    def test_json_ends_with_newline(self):
        result = _serialize_content({"a": 1}, "json")
        assert result.endswith("\n")

    def test_json_is_indented(self):
        result = _serialize_content({"a": {"b": 1}}, "json")
        assert "  " in result

    def test_yaml_not_flow_style(self):
        result = _serialize_content({"items": [1, 2]}, "yaml")
        # Flow style would be {items: [1, 2]}, block style has newlines
        assert "\n" in result

    def test_serialize_empty_dict_yaml(self):
        result = _serialize_content({}, "yaml")
        parsed = yaml.safe_load(result)
        assert parsed == {} or parsed is None

    def test_serialize_empty_dict_json(self):
        result = _serialize_content({}, "json")
        parsed = json.loads(result)
        assert parsed == {}

    def test_serialize_nested_content_json(self):
        content = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"}
            ],
        }
        result = _serialize_content(content, "json")
        parsed = json.loads(result)
        assert parsed["Version"] == "2012-10-17"
        assert len(parsed["Statement"]) == 1

    def test_serialize_json_with_indent_4(self):
        result = _serialize_content({"a": 1}, "json", json_indent=4)
        assert "    " in result
        parsed = json.loads(result)
        assert parsed == {"a": 1}

    def test_serialize_json_with_tab_indent(self):
        result = _serialize_content({"a": {"b": 1}}, "json", json_indent="tab")
        assert "\t" in result
        parsed = json.loads(result)
        assert parsed == {"a": {"b": 1}}

    def test_serialize_json_with_indent_2(self):
        result = _serialize_content({"a": 1}, "json", json_indent=2)
        lines = result.strip().splitlines()
        # Second line should start with 2 spaces
        assert lines[1].startswith("  ")
        assert not lines[1].startswith("    ")

    def test_serialize_yaml_ignores_json_indent(self):
        # json_indent should have no effect on YAML output
        result_default = _serialize_content({"a": 1}, "yaml")
        result_tab = _serialize_content({"a": 1}, "yaml", json_indent="tab")
        assert result_default == result_tab

    def test_serialize_json_invalid_indent_falls_back_to_2(self):
        # Invalid indent value falls back to default (2)
        result = _serialize_content({"a": 1}, "json", json_indent=99)
        result_default = _serialize_content({"a": 1}, "json", json_indent=2)
        assert result == result_default


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def config_dir(tmp_path):
    """Create a temporary LZA config directory with retrieved-config."""
    retrieved = tmp_path / "retrieved-config"
    retrieved.mkdir()

    # Add an existing YAML file for overwrite tests
    (retrieved / "existing.yaml").write_text(
        yaml.dump({"old": "data"}, default_flow_style=False)
    )

    # Add an existing JSON file for overwrite tests
    (retrieved / "existing.json").write_text(json.dumps({"old": "data"}, indent=2))

    # Add a subdirectory to test path-is-directory check
    (retrieved / "subdir").mkdir()

    return tmp_path


def _patch_base_path(config_dir):
    """Return a patch context manager that overrides LZA_CONFIG_BASE_PATH."""
    return patch(
        "awslabs.lza_mcp_server.tools.config.create_lza_config_file.LZA_CONFIG_BASE_PATH",
        config_dir,
    )


# ===========================================================================
# Parameter validation tests
# ===========================================================================


class TestParameterValidation:
    @pytest.mark.asyncio
    async def test_missing_file_path(self, mock_mcp_context):
        result = await create_lza_config_file(
            mock_mcp_context, file_path="", content={"a": 1}
        )
        assert result["success"] is False
        assert result["error_code"] == "MISSING_FILE_PATH"

    @pytest.mark.asyncio
    async def test_none_content(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context, file_path="test.yaml", content=None
            )
        assert result["success"] is False
        assert result["error_code"] == "MISSING_CONTENT"

    @pytest.mark.asyncio
    async def test_content_not_dict(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context, file_path="test.yaml", content="not-a-dict"
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_CONTENT"

    @pytest.mark.asyncio
    async def test_content_list_not_dict(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context, file_path="test.yaml", content=[1, 2, 3]
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_CONTENT"

    @pytest.mark.asyncio
    async def test_unsupported_extension(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context, file_path="test.txt", content={"a": 1}
            )
        assert result["success"] is False
        assert result["error_code"] == "UNSUPPORTED_FORMAT"


# ===========================================================================
# File/path validation tests
# ===========================================================================


class TestFilePathValidation:
    @pytest.mark.asyncio
    async def test_config_not_retrieved(self, mock_mcp_context, tmp_path):
        with _patch_base_path(tmp_path / "nonexistent"):
            result = await create_lza_config_file(
                mock_mcp_context, file_path="test.yaml", content={"a": 1}
            )
        assert result["success"] is False
        assert result["error_code"] == "CONFIG_NOT_RETRIEVED"

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="../../../etc/evil.yaml",
                content={"a": 1},
            )
        assert result["success"] is False
        assert (
            "traversal" in result["error"].lower()
            or "PATH_TRAVERSAL" in result["error_code"]
        )

    @pytest.mark.asyncio
    async def test_absolute_path_blocked(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="/etc/evil.yaml",
                content={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "BOUNDARY_VIOLATION"

    @pytest.mark.asyncio
    async def test_path_is_directory(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="subdir",
                content={"a": 1},
            )
        # "subdir" has no supported extension
        assert result["success"] is False
        assert result["error_code"] == "UNSUPPORTED_FORMAT"

    @pytest.mark.asyncio
    async def test_path_is_existing_directory_with_yaml_name(
        self, mock_mcp_context, config_dir
    ):
        """A directory that happens to end in .yaml should be rejected."""
        dir_path = config_dir / "retrieved-config" / "tricky.yaml"
        dir_path.mkdir()
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="tricky.yaml",
                content={"a": 1},
            )
        assert result["success"] is False
        assert result["error_code"] == "PATH_IS_DIRECTORY"


# ===========================================================================
# File exists / overwrite tests
# ===========================================================================


class TestFileExistsOverwrite:
    @pytest.mark.asyncio
    async def test_file_exists_no_overwrite(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="existing.yaml",
                content={"new": "data"},
            )
        assert result["success"] is False
        assert result["error_code"] == "FILE_EXISTS"

    @pytest.mark.asyncio
    async def test_file_exists_with_overwrite(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="existing.yaml",
                content={"new": "data"},
                overwrite=True,
            )
        assert result["success"] is True
        assert result["overwritten"] is True

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "existing.yaml").read_text()
        )
        assert content == {"new": "data"}

    @pytest.mark.asyncio
    async def test_json_file_exists_with_overwrite(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="existing.json",
                content={"new": "data"},
                overwrite=True,
            )
        assert result["success"] is True
        assert result["overwritten"] is True
        assert result["format"] == "json"

        content = json.loads(
            (config_dir / "retrieved-config" / "existing.json").read_text()
        )
        assert content == {"new": "data"}


# ===========================================================================
# YAML creation tests
# ===========================================================================


class TestYamlCreation:
    @pytest.mark.asyncio
    async def test_create_simple_yaml(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="new-config.yaml",
                content={"homeRegion": "us-east-1", "enabledRegions": ["us-east-1"]},
            )
        assert result["success"] is True
        assert result["file_path"] == "new-config.yaml"
        assert result["format"] == "yaml"
        assert result["overwritten"] is False
        assert result["size_bytes"] > 0
        assert result["size_formatted"]

        content = yaml.safe_load(
            (config_dir / "retrieved-config" / "new-config.yaml").read_text()
        )
        assert content["homeRegion"] == "us-east-1"

    @pytest.mark.asyncio
    async def test_create_yml_extension(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="config.yml",
                content={"key": "value"},
            )
        assert result["success"] is True
        assert result["format"] == "yaml"

    @pytest.mark.asyncio
    async def test_create_yaml_in_subdirectory(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="custom-rules/tagging.yaml",
                content={"rules": [{"name": "require-tag", "enabled": True}]},
            )
        assert result["success"] is True

        file_path = config_dir / "retrieved-config" / "custom-rules" / "tagging.yaml"
        assert file_path.exists()
        content = yaml.safe_load(file_path.read_text())
        assert content["rules"][0]["name"] == "require-tag"

    @pytest.mark.asyncio
    async def test_create_yaml_nested_subdirectories(
        self, mock_mcp_context, config_dir
    ):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="a/b/c/deep.yaml",
                content={"deep": True},
            )
        assert result["success"] is True
        assert (
            config_dir / "retrieved-config" / "a" / "b" / "c" / "deep.yaml"
        ).exists()


# ===========================================================================
# JSON creation tests
# ===========================================================================


class TestJsonCreation:
    @pytest.mark.asyncio
    async def test_create_iam_policy_json(self, mock_mcp_context, config_dir):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": "*",
                }
            ],
        }
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="iam-policies/boundary-policy.json",
                content=policy,
            )
        assert result["success"] is True
        assert result["format"] == "json"
        assert result["overwritten"] is False

        file_path = (
            config_dir / "retrieved-config" / "iam-policies" / "boundary-policy.json"
        )
        assert file_path.exists()
        content = json.loads(file_path.read_text())
        assert content["Version"] == "2012-10-17"
        assert len(content["Statement"]) == 1

    @pytest.mark.asyncio
    async def test_create_empty_json(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="empty.json",
                content={},
            )
        assert result["success"] is True
        content = json.loads(
            (config_dir / "retrieved-config" / "empty.json").read_text()
        )
        assert content == {}

    @pytest.mark.asyncio
    async def test_create_json_with_nested_content(self, mock_mcp_context, config_dir):
        content = {
            "rules": {
                "tagging": {"required": ["Environment", "Project"]},
                "naming": {"pattern": "^[a-z][a-z0-9-]*$"},
            }
        }
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="rules.json",
                content=content,
            )
        assert result["success"] is True
        parsed = json.loads(
            (config_dir / "retrieved-config" / "rules.json").read_text()
        )
        assert parsed["rules"]["tagging"]["required"] == ["Environment", "Project"]


# ===========================================================================
# Serialization error tests
# ===========================================================================


# ===========================================================================
# JSON indent tests
# ===========================================================================


class TestJsonIndent:
    @pytest.mark.asyncio
    async def test_json_indent_2_default(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="default-indent.json",
                content={"a": {"b": 1}},
            )
        assert result["success"] is True
        raw = (config_dir / "retrieved-config" / "default-indent.json").read_text()
        # Default is 2-space indent
        assert '  "a"' in raw
        assert "\t" not in raw

    @pytest.mark.asyncio
    async def test_json_indent_4(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="four-space.json",
                content={"a": {"b": 1}},
                json_indent=4,
            )
        assert result["success"] is True
        raw = (config_dir / "retrieved-config" / "four-space.json").read_text()
        assert '    "a"' in raw

    @pytest.mark.asyncio
    async def test_json_indent_tab(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="tab-indent.json",
                content={"a": {"b": 1}},
                json_indent="tab",
            )
        assert result["success"] is True
        raw = (config_dir / "retrieved-config" / "tab-indent.json").read_text()
        assert '\t"a"' in raw
        parsed = json.loads(raw)
        assert parsed == {"a": {"b": 1}}

    @pytest.mark.asyncio
    async def test_json_indent_invalid_value(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="bad-indent.json",
                content={"a": 1},
                json_indent=8,
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_JSON_INDENT"

    @pytest.mark.asyncio
    async def test_json_indent_invalid_string(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="bad-indent.json",
                content={"a": 1},
                json_indent="spaces",
            )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_JSON_INDENT"

    @pytest.mark.asyncio
    async def test_json_indent_none_defaults_to_2(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="none-indent.json",
                content={"a": 1},
                json_indent=None,
            )
        assert result["success"] is True
        raw = (config_dir / "retrieved-config" / "none-indent.json").read_text()
        assert '  "a"' in raw

    @pytest.mark.asyncio
    async def test_json_indent_ignored_for_yaml(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="config.yaml",
                content={"key": "value"},
                json_indent="tab",
            )
        assert result["success"] is True
        assert result["format"] == "yaml"

    @pytest.mark.asyncio
    async def test_json_indent_2_explicit(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="explicit-2.json",
                content={"a": 1},
                json_indent=2,
            )
        assert result["success"] is True
        raw = (config_dir / "retrieved-config" / "explicit-2.json").read_text()
        assert '  "a"' in raw


# ===========================================================================
# Serialization error tests
# ===========================================================================


class TestSerializationErrors:
    @pytest.mark.asyncio
    async def test_yaml_serialization_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            with patch(
                "awslabs.lza_mcp_server.tools.config.create_lza_config_file.yaml.dump",
                side_effect=yaml.YAMLError("mock yaml error"),
            ):
                result = await create_lza_config_file(
                    mock_mcp_context,
                    file_path="test.yaml",
                    content={"a": 1},
                )
        assert result["success"] is False
        assert result["error_code"] == "SERIALIZATION_ERROR"

    @pytest.mark.asyncio
    async def test_json_serialization_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            with patch(
                "awslabs.lza_mcp_server.tools.config.create_lza_config_file.json.dumps",
                side_effect=TypeError("mock json error"),
            ):
                result = await create_lza_config_file(
                    mock_mcp_context,
                    file_path="test.json",
                    content={"a": 1},
                )
        assert result["success"] is False
        assert result["error_code"] == "SERIALIZATION_ERROR"


# ===========================================================================
# Write failure tests
# ===========================================================================


class TestWriteFailures:
    @pytest.mark.asyncio
    async def test_directory_create_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            with patch(
                "pathlib.Path.mkdir",
                side_effect=OSError("permission denied"),
            ):
                result = await create_lza_config_file(
                    mock_mcp_context,
                    file_path="new-dir/test.yaml",
                    content={"a": 1},
                )
        assert result["success"] is False
        assert result["error_code"] == "DIRECTORY_CREATE_ERROR"

    @pytest.mark.asyncio
    async def test_file_write_error(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            with patch(
                "pathlib.Path.write_text",
                side_effect=OSError("disk full"),
            ):
                result = await create_lza_config_file(
                    mock_mcp_context,
                    file_path="test.yaml",
                    content={"a": 1},
                )
        assert result["success"] is False
        assert result["error_code"] == "FILE_WRITE_ERROR"


# ===========================================================================
# Response structure tests
# ===========================================================================


class TestResponseStructure:
    @pytest.mark.asyncio
    async def test_success_response_shape(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="new.yaml",
                content={"key": "value"},
            )
        assert result["success"] is True
        assert "file_path" in result
        assert "format" in result
        assert "size_bytes" in result
        assert "size_formatted" in result
        assert "overwritten" in result
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_error_response_shape(self, mock_mcp_context):
        result = await create_lza_config_file(
            mock_mcp_context, file_path="", content={"a": 1}
        )
        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result
        assert "category" in result
        assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_overwrite_true_in_response(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="existing.yaml",
                content={"new": "data"},
                overwrite=True,
            )
        assert result["overwritten"] is True

    @pytest.mark.asyncio
    async def test_overwrite_false_in_response(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            result = await create_lza_config_file(
                mock_mcp_context,
                file_path="brand-new.yaml",
                content={"new": "data"},
            )
        assert result["overwritten"] is False


# ===========================================================================
# Tool registration test
# ===========================================================================


class TestToolRegistration:
    def test_create_lza_config_file_registered(self):
        from unittest.mock import Mock

        server = Mock()
        registered = {}

        def mock_tool_decorator(name=None, description=None):
            def decorator(func):
                registered[name] = {
                    "name": name,
                    "description": description,
                    "function": func,
                }
                return func

            return decorator

        server.tool = mock_tool_decorator

        from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
            register_config_tools,
        )

        register_config_tools(server)

        assert "createLzaConfigFile" in registered
        assert "create" in registered["createLzaConfigFile"]["description"].lower()
        assert "json" in registered["createLzaConfigFile"]["description"].lower()
        assert "yaml" in registered["createLzaConfigFile"]["description"].lower()

    @pytest.mark.asyncio
    async def test_registered_wrapper_delegates(self, mock_mcp_context, config_dir):
        from unittest.mock import Mock

        server = Mock()
        registered = {}

        def mock_tool_decorator(name=None, description=None):
            def decorator(func):
                registered[name] = func
                return func

            return decorator

        server.tool = mock_tool_decorator

        from awslabs.lza_mcp_server.tools.config.manage_config_tools import (
            register_config_tools,
        )

        register_config_tools(server)

        func = registered["createLzaConfigFile"]
        with _patch_base_path(config_dir):
            result = await func(
                mock_mcp_context,
                file_path="delegated.json",
                content={"test": True},
            )
        assert result["success"] is True


# ===========================================================================
# Context logging tests
# ===========================================================================


class TestContextLogging:
    @pytest.mark.asyncio
    async def test_info_logged_on_create(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            await create_lza_config_file(
                mock_mcp_context,
                file_path="logged.yaml",
                content={"a": 1},
            )
        assert any("logged.yaml" in msg for msg in mock_mcp_context.info_messages)

    @pytest.mark.asyncio
    async def test_info_logged_on_overwrite(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            await create_lza_config_file(
                mock_mcp_context,
                file_path="existing.yaml",
                content={"a": 1},
                overwrite=True,
            )
        assert any("Overwrote" in msg for msg in mock_mcp_context.info_messages)

    @pytest.mark.asyncio
    async def test_info_logged_on_new_file(self, mock_mcp_context, config_dir):
        with _patch_base_path(config_dir):
            await create_lza_config_file(
                mock_mcp_context,
                file_path="brand-new.json",
                content={"a": 1},
            )
        assert any("Created" in msg for msg in mock_mcp_context.info_messages)
