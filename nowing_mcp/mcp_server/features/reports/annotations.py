"""Tool-call policy hints and shared parameter types for report tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
