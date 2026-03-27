"""Toggle for stripping LLM guidance keys from tool responses."""

import os
from typing import Any, Dict


GUIDANCE_KEYS = frozenset(
    {
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
)


def is_guidance_disabled() -> bool:
    """Check if LLM guidance should be disabled."""
    val = os.environ.get("DISABLE_LLM_GUIDANCE", "false")
    return val.lower() == "true"


def tool_description(standard: str, disable_guidance: str) -> str:
    """Return standard description when guidance is enabled, disable_guidance when disabled.

    Evaluated once at tool registration time so the MCP tool manifest
    reflects the appropriate level of detail for the current mode.
    """
    return disable_guidance if is_guidance_disabled() else standard


def strip_llm_guidance(response: Dict[str, Any]) -> Dict[str, Any]:
    """Remove LLM guidance keys from tool response when disabled.

    Recursively strips guidance keys from nested dicts so embedded
    objects (e.g. deployment results) are also cleaned.
    """
    if not is_guidance_disabled():
        return response
    return _strip_keys(response)


def _strip_keys(obj: Any) -> Any:
    """Recursively remove guidance keys from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_keys(v) for k, v in obj.items() if k not in GUIDANCE_KEYS}
    if isinstance(obj, list):
        return [_strip_keys(item) for item in obj]
    return obj
