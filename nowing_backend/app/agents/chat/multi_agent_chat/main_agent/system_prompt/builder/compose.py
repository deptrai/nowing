"""Assemble the main-agent system prompt from ``prompts/``.

Section order (default flow)::

    <agent_identity>
    [user's custom_system_instructions, if any]
    <core_behavior>                 # default body
    <knowledge_base_first>          # default body
    <dynamic_context>               # always
    <routing>                       # default body
    <specialists>                   # always (dynamic roster)
    <tools>                         # always (vertical-slice)
    <memory_protocol>               # default body
    <citations>                     # always
    <output_format>                 # always
    <refusal_and_limits>            # always
    <reminder>                      # always

``custom_system_instructions`` is **additive**, not a replacement: it slots
between identity and the default body so platform safety nets (KB-first,
routing, citations, output formatting, refusal rules) always apply.

``use_default_system_instructions=False`` skips the four "default body"
sections but keeps all the always-on platform sections.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.db import ChatVisibility

from .load_md import read_prompt_md
from .sections.citations import build_citations_section
from .sections.dynamic_context import build_dynamic_context_section
from .sections.identity import build_identity_section
from .sections.memory_protocol import build_memory_protocol_section
from .sections.mode_policy import build_mode_policy_section
from .sections.specialists import build_specialists_section
from .sections.tools import build_tools_section

# AC-18.4: hard ceiling for admin-injected system instructions.
_MAX_INSTRUCTIONS_LEN = 8_000


def _sanitize_agent_instructions(instructions: str) -> str:
    """Strip any Jinja-like markers except the documented ``{resolved_today}`` placeholder."""
    placeholder = "\x00resolved_today\x00"
    s = instructions.replace("{resolved_today}", placeholder)
    s = re.sub(r"[{}]", "", s)
    return s.replace(placeholder, "{resolved_today}")


def build_main_agent_system_prompt(
    *,
    registry_subagent_prompt_lines: list[tuple[str, str]],
    today: datetime | None = None,  # pragma: no mutate
    thread_visibility: ChatVisibility | None = None,  # pragma: no mutate
    enabled_tool_names: set[str] | None = None,  # pragma: no mutate
    disabled_tool_names: set[str] | None = None,  # pragma: no mutate
    custom_system_instructions: str | None = None,  # pragma: no mutate
    use_default_system_instructions: bool = True,
    citations_enabled: bool = True,
    model_name: str | None = None,  # pragma: no mutate
    research_mode: str | None = None,  # pragma: no mutate
) -> str:
    resolved_today = (today or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    visibility = thread_visibility or ChatVisibility.PRIVATE

    parts: list[str] = []

    parts.append(
        build_identity_section(visibility=visibility, resolved_today=resolved_today)
    )

    if custom_system_instructions and custom_system_instructions.strip():
        # Only substitute the single documented ``{resolved_today}`` placeholder.
        # Registry instructions are admin-supplied and may contain literal ``{``
        # characters, so ``str.format()`` would raise ``KeyError``.
        # AC-18.4: cap length and strip any Jinja-like markers before rendering.
        clamped = custom_system_instructions[:_MAX_INSTRUCTIONS_LEN]
        normalized = _sanitize_agent_instructions(clamped).replace(
            "{resolved_today}", resolved_today
        )
        parts.append("\n" + normalized + "\n")

    if use_default_system_instructions:
        parts.append(_wrap(read_prompt_md("core_behavior.md")))
        parts.append(_wrap(read_prompt_md("kb_first.md")))

    parts.append(build_dynamic_context_section(visibility=visibility))

    if use_default_system_instructions:
        parts.append(_wrap(read_prompt_md("routing.md")))

    parts.append(build_specialists_section(registry_subagent_prompt_lines))
    parts.append(
        build_tools_section(
            visibility=visibility,
            enabled_tool_names=enabled_tool_names,
            disabled_tool_names=disabled_tool_names,
        )
    )

    parts.append(build_mode_policy_section(research_mode=research_mode))

    if use_default_system_instructions:
        parts.append(build_memory_protocol_section(visibility=visibility))

    parts.append(build_citations_section(citations_enabled=citations_enabled))
    parts.append(_wrap(read_prompt_md("output_format.md")))
    parts.append(_wrap(read_prompt_md("refusal_and_limits.md")))
    parts.append(_wrap(read_prompt_md("reminder.md")))

    return "".join(p for p in parts if p)


def _wrap(fragment: str) -> str:
    return f"\n{fragment}\n" if fragment else ""
