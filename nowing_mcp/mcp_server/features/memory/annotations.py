"""Tool-call policy hints and shared parameter types for memory tools."""

from __future__ import annotations

from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import BeforeValidator, Field, StrictInt


def _reject_bool_top_k(value: object) -> object:
    # Pydantic's lax-mode int validation silently coerces True/False to 1/0
    # even with ge/le constraints, so a bool must be turned away here, before
    # that coercion runs (Story 3.14, D9 — "bool is invalid everywhere").
    if isinstance(value, bool):
        raise ValueError("top_k must be an integer, not a boolean")
    return value


READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
UPDATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)

MemoryId = Annotated[
    int,
    Field(description="Memory id from nowing_recall or nowing_remember results."),
]

MemoryType = Annotated[
    str,
    Field(
        description="Memory type: semantic, episodic, procedural, or working.",
    ),
]

MemoryTags = Annotated[
    list[str] | None,
    Field(description="Optional keyword tags for filtering and recall."),
]

ResearchThreadId = Annotated[
    int,
    Field(description="Research thread id to scope memory search to."),
]

OptionalResearchThreadId = Annotated[
    int | None,
    Field(description="Optional research thread id to scope memory search to."),
]

TopK = Annotated[
    StrictInt,
    BeforeValidator(_reject_bool_top_k),
    Field(ge=1, le=5, description="Maximum memories to return (1-5)."),
]
