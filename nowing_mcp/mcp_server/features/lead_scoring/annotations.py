"""Tool-call policy hints for lead-scoring tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

LEAD_SCORE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)

LEAD_SCORE_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
