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

"""Tests for the guidance toggle utility."""

import pytest

from awslabs.lza_mcp_server.utils.guidance_toggle import (
    GUIDANCE_KEYS,
    is_guidance_disabled,
    strip_llm_guidance,
    tool_description,
)


# ---------------------------------------------------------------------------
# is_guidance_disabled
# ---------------------------------------------------------------------------


class TestIsGuidanceDisabled:
    """Tests for is_guidance_disabled()."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "env_value",
        ["true", "True", "TRUE"],
    )
    def test_truthy_values(self, monkeypatch, env_value):
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", env_value)
        assert is_guidance_disabled() is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "env_value",
        ["false", "False", "FALSE", "0", "1", "yes", "no", "", "anything"],
    )
    def test_falsy_values(self, monkeypatch, env_value):
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", env_value)
        assert is_guidance_disabled() is False

    @pytest.mark.unit
    def test_unset(self, monkeypatch):
        monkeypatch.delenv("DISABLE_LLM_GUIDANCE", raising=False)
        assert is_guidance_disabled() is False


# ---------------------------------------------------------------------------
# strip_llm_guidance
# ---------------------------------------------------------------------------


class TestStripLlmGuidance:
    """Tests for strip_llm_guidance()."""

    @pytest.mark.unit
    def test_guidance_enabled_preserves_all_keys(self, monkeypatch):
        """When guidance is enabled, all keys are preserved unchanged."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "false")
        response = {
            "success": True,
            "llm_instructions": "do this",
            "next_steps": ["step1"],
            "hint": "a hint",
            "required_action": "action",
            "instructions_for_assistant": {"msg": "hi"},
            "example": "ex",
            "troubleshooting": ["fix it"],
            "data": {"key": "value"},
        }
        result = strip_llm_guidance(response)
        assert result is response  # same object, not a copy
        assert "llm_instructions" in result
        assert "next_steps" in result
        assert "hint" in result
        assert "required_action" in result
        assert "instructions_for_assistant" in result
        assert "example" in result
        assert "troubleshooting" in result

    @pytest.mark.unit
    def test_guidance_disabled_strips_guidance_keys(self, monkeypatch):
        """When guidance is disabled, all guidance keys are removed."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "success": True,
            "llm_instructions": "do this",
            "next_steps": ["step1"],
            "hint": "a hint",
            "required_action": "action",
            "instructions_for_assistant": {"msg": "hi"},
            "example": "ex",
            "troubleshooting": ["fix it"],
            "data": {"key": "value"},
        }
        result = strip_llm_guidance(response)
        for key in GUIDANCE_KEYS:
            assert key not in result
        assert result["success"] is True
        assert result["data"] == {"key": "value"}

    @pytest.mark.unit
    def test_guidance_disabled_strips_troubleshooting(self, monkeypatch):
        """troubleshooting is stripped when guidance is disabled."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "success": False,
            "error": "something broke",
            "troubleshooting": ["step 1", "step 2"],
            "next_steps": "should be removed",
        }
        result = strip_llm_guidance(response)
        assert "troubleshooting" not in result
        assert "next_steps" not in result
        assert result["error"] == "something broke"

    @pytest.mark.unit
    def test_guidance_disabled_no_guidance_keys_present(self, monkeypatch):
        """When disabled but no guidance keys exist, response is unchanged."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {"success": True, "data": "value"}
        result = strip_llm_guidance(response)
        assert result == response

    @pytest.mark.unit
    def test_guidance_disabled_strips_nested_guidance_keys(self, monkeypatch):
        """Guidance keys inside nested dicts are also stripped."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "connected": True,
            "deployment": {
                "success": True,
                "deployment_type": "external_pipeline",
                "next_steps": ["do this", "then that"],
                "troubleshooting": ["check this"],
            },
        }
        result = strip_llm_guidance(response)
        assert "next_steps" not in result["deployment"]
        assert "troubleshooting" not in result["deployment"]
        assert result["deployment"]["success"] is True
        assert result["deployment"]["deployment_type"] == "external_pipeline"

    @pytest.mark.unit
    def test_guidance_disabled_strips_deeply_nested_keys(self, monkeypatch):
        """Guidance keys are stripped at arbitrary nesting depth."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "level1": {
                "level2": {
                    "hint": "should be removed",
                    "data": "kept",
                },
            },
        }
        result = strip_llm_guidance(response)
        assert "hint" not in result["level1"]["level2"]
        assert result["level1"]["level2"]["data"] == "kept"

    @pytest.mark.unit
    def test_guidance_unset_preserves_all_keys(self, monkeypatch):
        """When env var is unset, all keys are preserved."""
        monkeypatch.delenv("DISABLE_LLM_GUIDANCE", raising=False)
        response = {
            "success": True,
            "next_steps": "keep me",
            "hint": "keep me too",
        }
        result = strip_llm_guidance(response)
        assert result is response
        assert "next_steps" in result
        assert "hint" in result

    @pytest.mark.unit
    def test_empty_response(self, monkeypatch):
        """Empty dict returns empty dict regardless of toggle."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        assert strip_llm_guidance({}) == {}

    @pytest.mark.unit
    def test_only_guidance_keys(self, monkeypatch):
        """Response with only guidance keys returns empty dict when disabled."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "llm_instructions": "x",
            "next_steps": "y",
            "hint": "z",
            "note": "n",
            "required_action": "a",
            "instructions_for_assistant": "b",
            "example": "c",
            "troubleshooting": ["d"],
        }
        result = strip_llm_guidance(response)
        assert result == {}

    @pytest.mark.unit
    def test_guidance_disabled_strips_keys_inside_list_of_dicts(self, monkeypatch):
        """Guidance keys inside dicts that are elements of a list are stripped."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {
            "items": [
                {"name": "a", "hint": "remove me"},
                {"name": "b", "next_steps": "remove me too"},
            ]
        }
        result = strip_llm_guidance(response)
        assert result["items"][0] == {"name": "a"}
        assert result["items"][1] == {"name": "b"}

    @pytest.mark.unit
    def test_guidance_disabled_preserves_plain_list_values(self, monkeypatch):
        """Plain (non-dict) list items are preserved unchanged."""
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        response = {"data": [1, "two", 3.0, None]}
        result = strip_llm_guidance(response)
        assert result["data"] == [1, "two", 3.0, None]


# ---------------------------------------------------------------------------
# GUIDANCE_KEYS constant
# ---------------------------------------------------------------------------


class TestGuidanceKeys:
    """Tests for the GUIDANCE_KEYS constant."""

    @pytest.mark.unit
    def test_expected_keys(self):
        """GUIDANCE_KEYS contains exactly the expected set."""
        expected = {
            "llm_instructions",
            "next_steps",
            "hint",
            "note",
            "required_action",
            "instructions_for_assistant",
            "example",
            "troubleshooting",
            "usage_hint",
        }
        assert GUIDANCE_KEYS == expected

    @pytest.mark.unit
    def test_troubleshooting_in_guidance_keys(self):
        """troubleshooting must be in GUIDANCE_KEYS."""
        assert "troubleshooting" in GUIDANCE_KEYS

    @pytest.mark.unit
    def test_immutable(self):
        """GUIDANCE_KEYS is a frozenset (immutable)."""
        assert isinstance(GUIDANCE_KEYS, frozenset)


# ---------------------------------------------------------------------------
# tool_description
# ---------------------------------------------------------------------------


class TestToolDescription:
    """Tests for tool_description()."""

    @pytest.mark.unit
    def test_returns_full_when_guidance_enabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "false")
        result = tool_description(standard="full desc", disable_guidance="minimal desc")
        assert result == "full desc"

    @pytest.mark.unit
    def test_returns_minimal_when_guidance_disabled(self, monkeypatch):
        monkeypatch.setenv("DISABLE_LLM_GUIDANCE", "true")
        result = tool_description(standard="full desc", disable_guidance="minimal desc")
        assert result == "minimal desc"

    @pytest.mark.unit
    def test_returns_full_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DISABLE_LLM_GUIDANCE", raising=False)
        result = tool_description(standard="full desc", disable_guidance="minimal desc")
        assert result == "full desc"
