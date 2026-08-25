"""generate_presentation: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.deliverables.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    prompt = d.get("prompt", "") if isinstance(tool_input, dict) else str(tool_input)
    title = d.get("title") or "Slide deck"
    return ToolStartThinking(
        title=f"Building {title}",
        items=[f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}"],
    )


_FAILURE_STATUSES = frozenset({"failed", "error", "validation_failed"})


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    if not isinstance(tool_output, dict):
        return ("Built slide deck", [*items, "Slides generated successfully"])

    title = tool_output.get("title") or "Slide deck"
    status = tool_output.get("status")
    error = tool_output.get("error")
    if error or status in _FAILURE_STATUSES:
        detail = error or "Slide deck generation failed"
        return (
            "Slide deck generation failed",
            [*items, f"Error: {detail}"],
        )
    if status == "degraded":
        reason = tool_output.get("degradation_reason") or "preview unavailable"
        return (
            f"Built {title} (limited preview)",
            [*items, f"Degraded: {reason}"],
        )
    return (f"Built {title}", [*items, "Slides generated successfully"])
