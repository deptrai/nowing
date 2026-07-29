"""``chainlens.research`` I/O contracts.

Thin mapping to the ChainLens Research ``POST /api/v1/search`` endpoint.
The caller provides a natural-language question; the executor returns a
synthesized answer plus the web sources that ground it.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

MAX_QUERY_LENGTH = 500
"""ChainLens clamps queries at 500 characters."""


class Source(BaseModel):
    """One cited source from ChainLens."""

    title: str = Field(description="Source title or page name.")
    url: str = Field(min_length=1, description="Canonical source URL.")
    content: str | None = Field(
        default=None,
        description="Snippet or markdown content when the source was deep-crawled.",
    )


class ResearchInput(BaseModel):
    """Input for a ChainLens research query."""

    query: str = Field(
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="The research question or topic.",
    )
    mode: Literal["speed", "balanced", "quality", "auto"] = Field(
        default="quality",
        description="Research depth: speed (fast), balanced, or quality (thorough).",
    )
    sources: list[Literal["web", "discussions", "academic"]] = Field(
        default_factory=lambda: ["web", "academic"],
        min_length=1,
        description="Source categories to search.",
    )
    system_instructions: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional instructions for the synthesis writer, e.g. language.",
    )
    history: list[Annotated[list[str], Field(min_length=2, max_length=2)]] = Field(
        default_factory=list,
        max_length=50,
        description="Optional conversation history as [role, content] pairs.",
    )
    chat_id: str | None = Field(
        default=None,
        description="Optional ChainLens chat session handle for continuity.",
    )

    @property
    def estimated_units(self) -> int:
        """One research call = one billed query."""
        return 1


class ResearchOutput(BaseModel):
    """Output of a ChainLens research query."""

    answer: str = Field(
        default="",
        description="Synthesized answer with inline citations when available.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Grounding sources, in the order they were cited.",
    )
    chat_id: str | None = Field(
        default=None,
        description="ChainLens chat session handle to continue this conversation.",
    )
    status: Literal["complete", "partial", "timeout", "insufficient_evidence"] = Field(
        default="complete", description="Result completeness status."
    )
    web_url: str | None = Field(
        default=None,
        description="Deep link to view the ChainLens chat session on the web.",
    )
    next_action: str | None = Field(
        default=None,
        description="Human-readable guidance when the result is partial or timed out.",
    )

    @property
    def billable_units(self) -> int:
        """Bill one unit only when the call returned usable content."""
        return 1 if self.answer or self.sources else 0
