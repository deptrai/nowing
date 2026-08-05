"""Tool-call policy hints for image-generation tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
