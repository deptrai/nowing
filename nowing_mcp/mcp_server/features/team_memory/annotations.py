"""Tool-call policy hints for workspace team-memory tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)
