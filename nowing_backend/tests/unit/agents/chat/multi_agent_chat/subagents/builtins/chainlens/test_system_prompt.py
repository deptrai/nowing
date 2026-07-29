"""Red-phase scaffold for ChainLens sub-agent prompt mapping (9.1a)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


_PROMPT_PATH = "/Users/luisphan/Documents/nowing/nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/system_prompt.md"


def _prompt_text() -> str:
    with open(_PROMPT_PATH) as f:
        return f.read()


def test_prompt_maps_engine_unavailable_to_error():
    text = _prompt_text()
    assert "engine_unavailable" in text
    assert "engine_unavailable" in text.split("status_mapping")[-1]


def test_prompt_maps_degraded_partial_to_partial_or_error():
    text = _prompt_text()
    assert "engine_unavailable" in text
    assert "degraded" in text or "degraded partial" in text
