"""Tool-call policy hints and shared parameter types for automation tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
