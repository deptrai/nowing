"""Unit tests for the main-agent system prompt builder (Story 18.4)."""

from __future__ import annotations

from datetime import UTC

import pytest

from app.agents.chat.multi_agent_chat.main_agent.system_prompt.builder.compose import (
    _MAX_INSTRUCTIONS_LEN,
    _sanitize_agent_instructions,
    build_main_agent_system_prompt,
)
from app.db import ChatVisibility

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


def test_today_defaults_to_current_date() -> None:
    """When today is omitted, the current UTC date is rendered."""
    from datetime import datetime

    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        use_default_system_instructions=False,
    )
    assert datetime.now(UTC).date().isoformat() in prompt


def test_thread_visibility_team_uses_team_sections() -> None:
    """SEARCH_SPACE visibility must select team variants of identity/dynamic_context."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        thread_visibility=ChatVisibility.SEARCH_SPACE,
        use_default_system_instructions=False,
    )
    assert "team thread" in prompt
    assert "team_memory" in prompt


def test_thread_visibility_private_uses_private_sections() -> None:
    """Default/private visibility must select private variants."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        thread_visibility=ChatVisibility.PRIVATE,
        use_default_system_instructions=False,
    )
    assert "user_memory" in prompt


def test_whitespace_only_custom_instructions_are_ignored() -> None:
    """A whitespace-only custom instruction is treated as absent."""
    baseline = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        use_default_system_instructions=False,
    )
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions="   ",
        use_default_system_instructions=False,
    )
    assert prompt == baseline


def test_default_system_instructions_are_included_by_default() -> None:
    """Default sections must appear when use_default_system_instructions is True."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
    )
    assert "<core_behavior>" in prompt
    assert "<knowledge_base_first>" in prompt
    assert "two execution channels" in prompt
    assert "<memory_protocol>" in prompt


def test_default_system_instructions_can_be_disabled() -> None:
    """Default sections are skipped when use_default_system_instructions is False."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        use_default_system_instructions=False,
    )
    assert "<core_behavior>" not in prompt
    assert "<knowledge_base_first>" not in prompt
    assert "two execution channels" not in prompt
    assert "<memory_protocol>" not in prompt


def test_citations_enabled_by_default() -> None:
    """Citations are enabled by default."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        use_default_system_instructions=False,
    )
    assert "Cite with one token" in prompt


def test_citations_disabled_uses_off_variant() -> None:
    """citations_enabled=False switches to the disabled variant."""
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        use_default_system_instructions=False,
        citations_enabled=False,
    )
    assert "Citation markers are **disabled**" in prompt


def test_max_instruction_length_boundary_exactly() -> None:
    """An instruction of exactly 8_000 chars is preserved."""
    instruction = "x" * 8_000
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions=instruction,
        use_default_system_instructions=False,
    )
    assert instruction in prompt


def test_max_instruction_length_boundary_plus_one() -> None:
    """An instruction one char over 8_000 is clamped."""
    instruction = "x" * 8_001
    prompt = build_main_agent_system_prompt(
        today=None,
        registry_subagent_prompt_lines=_make_tool_lines(),
        custom_system_instructions=instruction,
        use_default_system_instructions=False,
    )
    assert instruction not in prompt
