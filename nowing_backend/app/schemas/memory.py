"""Pydantic schemas for long-term memory resources."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.db import MemorySourceType, MemoryType
from app.utils.strict_fields import strict_top_k


class MemoryVersionRead(BaseModel):
    previous_content: str
    corrected_content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _run_citation(source_run_id: Any | None) -> str | None:
    """Render the stable ``run_<uuid>`` citation for a run-derived memory (D7).

    A *soft* citation by construction: it is derived from the id the memory
    carries, never from a live ``runs`` lookup. ``runs`` has a 30-day retention,
    so after cleanup the citation still renders identically and recall does not
    fail on a dangling reference (AC-7) — resolving it back to a run detail page
    is what becomes unavailable, not the memory.
    """
    if source_run_id is None:
        return None
    return f"run_{source_run_id}"


class MemoryRead(BaseModel):
    id: int
    workspace_id: int | None = None
    created_by_id: Any | None = None
    research_thread_id: int | None = None
    client_id: str | None = None
    agent_id: str | None = None
    type: str
    content: str
    source_type: str
    source_id: int | None = None
    # Story 3.13 (D7/AC-3): soft provenance for run-derived facts. UUID-shaped,
    # typed as ``str`` (not UUID) so JSON consumers (REST, MCP, generated
    # clients) need no UUID handling; ``None`` for chat/manual/document memories.
    source_run_id: str | None = None
    # Story 9.6a (AD-11.1): immutable source recipe from the Run that produced
    # this memory. ``None`` for chat/manual/document memories.
    source_capability: str | None = None
    source_input: Any | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime
    updated_at: datetime
    previous_versions: list[MemoryVersionRead] = Field(
        default_factory=list,
        alias="versions",
        serialization_alias="previous_versions",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def citation(self) -> str | None:
        """``run_<uuid>`` for a run-derived fact, else ``None``.

        Computed rather than stored so the citation cannot drift from
        ``source_run_id`` — every surface that serializes this model gets the
        same string without each call site formatting it by hand.
        """
        return _run_citation(self.source_run_id)

    @field_validator("source_run_id", mode="before")
    @classmethod
    def _stringify_run_id(cls, value: Any) -> Any:
        # ORM hands over a ``uuid.UUID``; normalise at the edge so both the field
        # and the citation are plain strings in every serialization mode.
        return str(value) if value is not None else None


class MemoryCreate(BaseModel):
    content: Annotated[str, Field(min_length=1)]
    type: str = "semantic"
    source_type: str = "manual"
    source_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    research_thread_id: int | None = None
    client_id: str | None = None
    agent_id: str | None = None

    @field_validator("type", "source_type", mode="before")
    @classmethod
    def _validate_enum_strings(cls, value: Any, info) -> Any:
        if not isinstance(value, str):
            return value
        enum_cls = MemoryType if info.field_name == "type" else MemorySourceType
        try:
            enum_cls(value)
        except ValueError as exc:
            raise ValueError(f"Invalid {info.field_name}: {value}") from exc
        return value


class MemoryUpdate(BaseModel):
    corrected_content: Annotated[str, Field(min_length=1)]
    client_id: str | None = None
    agent_id: str | None = None


class MemorySearchRequest(BaseModel):
    # Empty query is allowed only for thread-scoped recall (see validator);
    # nowing_continue_research relies on this to resume a thread with no query.
    query: str = Field(default="", max_length=4000)
    top_k: strict_top_k(le=5, description="Maximum memories to return.") = 5
    type: str | None = None
    tags: list[str] = Field(default_factory=list)
    research_thread_id: int | None = None
    client_id: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, value: Any) -> Any:
        if value is None or not isinstance(value, str):
            return value
        try:
            MemoryType(value)
        except ValueError as exc:
            raise ValueError(f"Invalid type: {value}") from exc
        return value

    @model_validator(mode="after")
    def _require_query_or_thread(self) -> MemorySearchRequest:
        if not self.query.strip() and self.research_thread_id is None:
            raise ValueError(
                "query must be non-empty unless research_thread_id is provided"
            )
        return self


class MemorySearchHit(BaseModel):
    id: int
    content: str
    type: str
    client_id: str | None = None
    agent_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    source_type: str
    source_id: int | None = None
    # Story 3.13 (D7/AC-3): same soft run provenance as ``MemoryRead``.
    source_run_id: str | None = None
    # Story 9.6a (AD-11.1): source recipe from the run that produced this hit.
    source_capability: str | None = None
    source_input: Any | None = None
    # Both null for a recency (query-less) hit; both finite for a ranked hit —
    # never a fake 0.0 placeholder (Story 3.14, D1/D6, AC-6).
    score: float | None = None
    similarity: float | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def citation(self) -> str | None:
        """``run_<uuid>`` for a run-derived fact, else ``None``."""
        return _run_citation(self.source_run_id)

    @field_validator("source_run_id", mode="before")
    @classmethod
    def _stringify_run_id(cls, value: Any) -> Any:
        return str(value) if value is not None else None

    @classmethod
    def from_memory(
        cls,
        memory: Any,
        *,
        score: float | None = None,
        similarity: float | None = None,
    ) -> MemorySearchHit:
        """Build a hit from an ORM ``Memory``.

        Exists because three call sites (REST search, the research-thread context
        route and the ``continue_research`` automation action) previously built
        this model field-by-field. Adding provenance to three hand-rolled literals
        is how one surface silently ends up without a citation, so the mapping now
        lives in one place. ``score`` and ``similarity`` are passed by callers that
        have them (ranked search); recency callers omit them and both stay ``None``.
        """
        return cls(
            id=memory.id,
            content=memory.content,
            type=memory.type.value,
            client_id=memory.client_id,
            agent_id=memory.agent_id,
            tags=memory.tags or [],
            confidence=memory.confidence,
            source_type=memory.source_type.value,
            source_id=memory.source_id,
            source_run_id=memory.source_run_id,
            source_capability=memory.source_capability,
            source_input=memory.source_input,
            score=score,
            similarity=similarity,
        )


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchHit]


class ThreadCitation(BaseModel):
    """A prior source cited within a research thread's chat history.

    ``url`` is populated for web-result citations (the MVP source of truth, per
    FR-33); knowledge-base chunk citations carry a ``label``/``source_type`` but
    no URL until chunk resolution lands. ``label`` is always present so the
    citation is renderable even when a locator is not available.
    """

    label: str
    url: str | None = None
    source_type: str | None = None


class ResearchThreadContext(BaseModel):
    """Continuity payload for a research thread: its ranked memories + citations."""

    thread_id: int
    title: str | None = None
    memories: list[MemorySearchHit] = Field(default_factory=list)
    citations: list[ThreadCitation] = Field(default_factory=list)


class MemoryLimits(BaseModel):
    soft: int
    hard: int


class MemoryReadLegacy(BaseModel):
    memory_md: str
    limits: MemoryLimits
