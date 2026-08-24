"""build_web_app: thinking-step copy."""

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
    app_name = d.get("app_name") or "Web App"
    return ToolStartThinking(
        title=f"Building {app_name}",
        items=[f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}"],
    )


def resolve_completed_thinking(
    tool_name: str,
    tool_output: Any,
    last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    if isinstance(tool_output, dict):
        if tool_output.get("error"):
            return ("Web app generation failed", [*items, f"Error: {tool_output['error']}"])
        name = tool_output.get("name") or "Web App"
        return (f"Built {name}", [*items, "Project generated successfully"])
    return ("Built web app", [*items, "Project generated successfully"])
