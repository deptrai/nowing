"""Tool-call policy hints and shared parameter types for memory tools."""

from __future__ import annotations

from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

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
    int,
    Field(ge=1, le=20, description="Maximum memories to return."),
]
