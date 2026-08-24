"""build_web_app: tool card + terminal summary."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    payload = out if isinstance(out, dict) else {"result": out}
    yield ctx.emit_tool_output_card(payload)
    if isinstance(out, dict):
        if out.get("error"):
            yield ctx.streaming_service.format_terminal_info(
                f"Web app build failed: {out['error'][:60]}",
                "error",
            )
        else:
            name = out.get("name") or "Web app"
            yield ctx.streaming_service.format_terminal_info(
                f"{name} generated successfully",
                "success",
            )
    else:
        yield ctx.streaming_service.format_terminal_info(
            "Web app build completed",
            "success",
        )
