"""``chainlens.research`` I/O contracts.

Thin mapping to the ChainLens Research ``POST /api/v1/search`` endpoint.
The caller provides a natural-language question; the executor returns a
synthesized answer plus the web sources that ground it.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field

MAX_QUERY_LENGTH = 500
"""ChainLens clamps queries at 500 characters."""


class Source(BaseModel):
    """One cited source from ChainLens or the workspace knowledge base."""

    title: str = Field(description="Source title or page name.")
    url: str = Field(min_length=1, description="Canonical source URL.")
    content: str | None = Field(
        default=None,
        description="Snippet or markdown content when the source was deep-crawled.",
    )
    source_type: str | None = Field(
        default=None,
        description="'web' for ChainLens sources, 'kb' for workspace chunks.",
    )
    document_id: int | None = Field(
        default=None,
        description="Workspace document id when source_type is 'kb'.",
    )
    chunk_id: int | None = Field(
        default=None,
        description="Workspace chunk id when source_type is 'kb'.",
    )

    def model_post_init(self, __context: object) -> None:
        """Derive KB locators and source type from internal URLs."""
        if self.url and self.url.startswith("nowing://documents/"):
            if self.document_id is None or self.chunk_id is None:
                match = re.match(
                    r"nowing://documents/(\d+)/chunks/(\d+)",
                    self.url,
                )
                if match:
                    if self.document_id is None:
                        self.document_id = int(match.group(1))
                    if self.chunk_id is None:
                        self.chunk_id = int(match.group(2))
            if self.source_type is None:
                self.source_type = "kb"
        elif self.url and self.source_type is None:
            self.source_type = "web"


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
    status: Literal[
        "complete",
        "partial",
        "timeout",
        "insufficient_evidence",
        "engine_unavailable",
    ] = Field(default="complete", description="Result completeness status.")
    web_url: str | None = Field(
        default=None,
        description="Deep link to view the ChainLens chat session on the web.",
    )
    next_action: str | None = Field(
        default=None,
        description="Human-readable guidance when the result is partial or timed out.",
    )
    degraded: bool | None = Field(
        default=None,
        description="True when the result came from an engine failure or KB fallback.",
    )
    degradation_reason: str | None = Field(
        default=None,
        description="Low-cardinality reason for the degradation/fallback.",
    )
    engine_reason: str | None = Field(
        default=None,
        description="Reason reported by the ChainLens engine for partial/insufficient results.",
    )
    source_type: str | None = Field(
        default=None,
        description="Type of the primary/first source (internal mirror of Source.source_type).",
    )
    document_id: int | None = Field(
        default=None,
        description="Document id of the primary/first KB fallback source.",
    )
    chunk_id: int | None = Field(
        default=None,
        description="Chunk id of the primary/first KB fallback source.",
    )
    block_type: str | None = Field(
        default=None,
        description="Block classification of the primary/first blocked source.",
    )
    fallback_hit_count: int | None = Field(
        default=None,
        description="Number of workspace chunks used as KB fallback citations.",
    )
    saw_heartbeat: bool = Field(
        default=False,
        exclude=True,
        description="Internal: parser saw a heartbeat event.",
    )
    blocked_url_coverage_by_block_type: dict[str, int] = Field(
        default_factory=dict,
        exclude=True,
        description="Internal: blocked URL counts by block type.",
    )

    def model_post_init(self, __context: object) -> None:
        """Stamp degradation defaults and infer KB fallback counters."""
        _recompute_degradation(self)
        _recompute_fallback(self)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "status":
            _recompute_degradation(self, force=True)
            _recompute_fallback(self)

    @computed_field
    @property
    def billable_units(self) -> int:
        """Bill one unit only when the call returned usable content."""
        return 1 if self.answer or self.sources else 0


def _recompute_degradation(
    output: ResearchOutput, *, force: bool = False
) -> None:
    """Keep the degradation flag, reason, and next-action in sync with status."""
    if output.status == "engine_unavailable":
        if force or output.degraded is None:
            output.degraded = True
        if output.degradation_reason is None:
            output.degradation_reason = "not_configured"
    elif force or output.degraded is None:
        output.degraded = output.status != "complete"

    if output.degradation_reason is None and output.status not in (
        "complete",
        "engine_unavailable",
    ):
        default_reason = {
            "partial": "partial",
            "insufficient_evidence": "insufficient_evidence",
            "timeout": "stream_incomplete",
        }.get(output.status)
        if default_reason:
            output.degradation_reason = default_reason

    if output.next_action is None and output.degraded:
        output.next_action = _default_next_action(
            output.status,
            output.degradation_reason,
            output.engine_reason,
        )


def _recompute_fallback(output: ResearchOutput) -> None:
    """Count KB fallback citations and mirror the primary source identifiers."""
    kb_sources = [
        s for s in output.sources if s.url and s.url.startswith("nowing://")
    ]
    output.fallback_hit_count = len(kb_sources)
    if kb_sources:
        primary = kb_sources[0]
        output.source_type = primary.source_type
        output.document_id = primary.document_id
        output.chunk_id = primary.chunk_id


def _default_next_action(
    status: str,
    degradation_reason: str | None,
    engine_reason: str | None,
) -> str | None:
    if status == "engine_unavailable":
        if degradation_reason == "not_configured":
            return "Deep research is not available in self-host Phase 1. Set CHAINLENS_API_KEY to use the hosted engine."
        if degradation_reason == "fallback_kb_empty":
            return "The deep research engine is unavailable and no matching workspace knowledge base passages were found. Try rephrasing your query."
        if degradation_reason == "fallback_kb_error":
            return "The deep research engine is unavailable and workspace knowledge base lookup failed. Try again later."
        if degradation_reason in ("timeout", "stream_incomplete"):
            return "The deep research engine timed out. Try again with a faster mode or a narrower query."
        if degradation_reason == "unreachable":
            return "The deep research engine is unreachable. Check your network and try again."
        if degradation_reason in ("auth_failed", "rate_limited", "upstream_error"):
            return "The deep research engine is temporarily unavailable. Try again later."
        return "The deep research engine is unavailable. Try again later."
    if status == "partial":
        reason = engine_reason or degradation_reason
        return f"Partial result; {reason or 'some evidence was found'}."
    if status == "insufficient_evidence":
        return "No relevant sources were found. Try rephrasing the query."
    if status == "timeout":
        return "The ChainLens stream ended before returning a complete result. Try again."
    return None
