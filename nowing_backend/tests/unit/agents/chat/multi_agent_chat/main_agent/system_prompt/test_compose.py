"""Unit tests for the main-agent system prompt builder (Story 18.4)."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.system_prompt.builder.compose import (
    _MAX_INSTRUCTIONS_LEN,
    _sanitize_agent_instructions,
    build_main_agent_system_prompt,
)

pytestmark = pytest.mark.unit


def _make_tool_lines() -> list[tuple[str, str]]:
    """Return a minimal tool catalog description for prompt building."""
    return [("update_memory", "Updates the user's memory.")]


def test_custom_system_instructions_are_prepended() -> None:
    """AC-1: custom instructions appear after identity and before default body."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions="Focus on real estate listings.",
        use_default_system_instructions=True,
    )
    assert "Focus on real estate listings." in prompt
    assert prompt.index("Focus on real estate listings.") < prompt.index(
        "core_behavior"
    )


def test_resolved_today_placeholder_is_substituted() -> None:
    """AC-1: the {resolved_today} placeholder is replaced with the provided date."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions="Today is {resolved_today}.",
        use_default_system_instructions=False,
    )
    assert "{resolved_today}" not in prompt
    assert "Today is" in prompt


def test_jinja_like_markers_are_stripped_except_resolved_today() -> None:
    """AC-4: Jinja-style braces are stripped; only {resolved_today} survives."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions="Use {{secret}}. Today is {resolved_today}.",
        use_default_system_instructions=False,
    )
    assert "{{secret}}" not in prompt
    assert "{secret}" not in prompt
    assert "{resolved_today}" not in prompt
    assert "Today is" in prompt


def test_custom_system_instructions_are_length_capped() -> None:
    """AC-4: instructions longer than _MAX_INSTRUCTIONS_LEN are clamped."""
    overage = 1_000
    long_instruction = "x" * (_MAX_INSTRUCTIONS_LEN + overage)
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions=long_instruction,
        use_default_system_instructions=False,
    )
    assert long_instruction not in prompt


def test_sanitize_agent_instructions_preserves_resolved_today() -> None:
    """AC-4: sanitizer preserves {resolved_today}."""
    assert (
        _sanitize_agent_instructions("Today is {resolved_today}.")
        == "Today is {resolved_today}."
    )


def test_sanitize_agent_instructions_strips_other_braces() -> None:
    """AC-4: sanitizer strips all braces except {resolved_today}."""
    assert _sanitize_agent_instructions("{{foo}} and {bar}") == "foo and bar"
