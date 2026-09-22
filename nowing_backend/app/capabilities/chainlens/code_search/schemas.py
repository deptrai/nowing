"""``chainlens.code_search`` I/O contracts.

Maps to the ChainLens ``POST /api/v1/search`` endpoint with
``output="code_context"`` and ``dataSources=["code"]``: code snippets and
API docs sourced from GitHub/StackOverflow/packages for programming
questions only.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from app.capabilities.chainlens.research.schemas import Source

CodeSearchMode = Literal["instant", "fast", "balanced", "auto"]

_LANGUAGE_RE = re.compile(r"^[a-z0-9+#-]+$")


class CodeSearchInput(BaseModel):
    """Input for a code-context search query."""

    query: str = Field(
        min_length=1,
        max_length=1000,
        description="Programming question to search for (required, <=1000 chars).",
    )
    language: str | None = Field(
        default=None,
        description="Programming language hint (e.g. 'typescript', 'python'); "
        "appended to the query per the upstream MCP contract.",
    )
    # CamelCase mirrors the upstream request field name (numResults).
    maxResults: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Number of code snippets to return (1-20, default 8).",
    )
    mode: CodeSearchMode = Field(
        default="fast",
        description="Latency vs depth hint for the upstream engine.",
    )
    workspace_id: int = Field(
        gt=0,
        description="Workspace context ID.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, v: Any) -> Any:
        """Reject blank/whitespace-only queries."""
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("query cannot be empty")
            return trimmed
        return v

    @field_validator("language", mode="before")
    @classmethod
    def validate_language(cls, v: Any) -> Any:
        """Normalize blank languages to None; enforce upstream charset."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("language must be a string")
        trimmed = v.strip().lower()
        if not trimmed:
            return None
        if not _LANGUAGE_RE.match(trimmed):
            raise ValueError(
                "language must match ^[a-z0-9+#-]+$ (e.g. 'python', 'c++', 'c#')"
            )
        return trimmed

    @property
    def estimated_units(self) -> int:
        """One code search call = one billed query."""
        return 1


class CodeSnippet(BaseModel):
    """One code snippet/source row from the code_context response."""

    source: str | None = Field(
        default=None,
        description="Upstream source name from metadata.source "
        "(e.g. 'github', 'stackoverflow', package registry).",
    )
    source_id: str | None = Field(
        default=None,
        description="Upstream source identifier from metadata.sourceId "
        "(typically a 'path' or 'path:line' ref).",
    )
    title: str | None = Field(default=None, description="Snippet/page title.")
    url: str | None = Field(default=None, description="Canonical source URL.")
    content: str = Field(
        description="Code snippet / fenced code block content (non-empty)."
    )
    score: float | None = Field(
        default=None, description="Upstream relevance score."
    )


class CodeSearchOutput(BaseModel):
    """Aggregated output for ``chainlens.code_search``."""

    items: list[CodeSnippet] = Field(
        default_factory=list,
        description="Code snippets with source/path refs. Named ``items`` so "
        "the run serializer pages one JSONL line per snippet.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Source citations derived from snippet URLs so the agent "
        "door can register [n] web citations.",
    )
    status: str = Field(
        default="complete",
        description="Overall status: 'complete', 'partial', 'timeout', or "
        "'engine_unavailable'.",
    )
    degraded: bool = Field(
        default=False,
        description="Whether the result is degraded due to engine unavailability.",
    )
    degradation_reason: str | None = Field(
        default=None,
        description="Machine-readable reason when ``degraded`` is True.",
    )
    next_action: str | None = Field(
        default=None,
        description="Upstream nextAction hint (e.g. on timeout) for the caller.",
    )
    message: str | None = Field(
        default=None,
        description="Optional informational or degradation message.",
    )
    cost_dollars: float | None = Field(
        default=None,
        description="Exact cost in USD reported by ChainLens, if available.",
    )
    cost_micros: int | None = Field(
        default=None,
        description="Exact cost in micros for query billing tracking; None triggers billing fallback.",
    )
    cost_basis: Literal["actual", "estimated", "fallback"] | None = Field(
        default=None,
        description="Cost basis ('actual', 'estimated', or 'fallback').",
    )

    @computed_field
    @property
    def billable_units(self) -> int:
        """One billed query when the call returned any usable snippet.

        Zero usable content = free: an empty/degraded result bills 0 so the
        caller isn't charged for an upstream failure.
        """
        return 1 if self.items else 0
