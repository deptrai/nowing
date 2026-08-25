"""generate_presentation: tool card + terminal summary."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)

_FAILURE_STATUSES = frozenset({"failed", "error", "validation_failed"})


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    payload = out if isinstance(out, dict) else {"result": out}
    yield ctx.emit_tool_output_card(payload)
    if not isinstance(out, dict):
        yield ctx.streaming_service.format_terminal_info(
            "Slide deck generation completed",
            "success",
        )
        return

    title = out.get("title") or "Slide deck"
    status = out.get("status")
    error = out.get("error")
    if error or status in _FAILURE_STATUSES:
        detail = (error or "Slide deck generation failed")[:60]
        yield ctx.streaming_service.format_terminal_info(
            f"Slide deck generation failed: {detail}",
            "error",
        )
        return
    if status == "degraded":
        yield ctx.streaming_service.format_terminal_info(
            f"{title} generated (preview unavailable)",
            "warning",
        )
        return
    yield ctx.streaming_service.format_terminal_info(
        f"{title} generated successfully",
        "success",
    )
