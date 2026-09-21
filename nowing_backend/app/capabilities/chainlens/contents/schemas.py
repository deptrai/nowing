"""``chainlens.contents`` I/O contracts.

Maps to the ChainLens ``POST /api/v1/search`` endpoint with
``output="contents"``: clean, token-efficient markdown extraction for
explicit URLs the caller already has (Crawl4AI/Trafilatura upstream).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from app.capabilities.chainlens.research.schemas import Source

MAX_CONTENTS_URLS = 100
"""ChainLens accepts at most 100 URLs per contents request."""

ContentsOptimizationMode = Literal["instant", "fast", "balanced", "auto"]
ContentsLivecrawl = Literal["always", "fallback", "never"]


class ContentsInput(BaseModel):
    """Input for extracting clean page contents from explicit URLs."""

    urls: list[str] = Field(
        min_length=1,
        max_length=MAX_CONTENTS_URLS,
        description="Explicit URLs to read (1-100). This is a reader, not a search tool.",
    )
    query: str | None = Field(
        default=None,
        description="Optional focus query; defaults to the joined URLs when absent.",
    )
    optimizationMode: ContentsOptimizationMode | None = Field(
        default=None,
        description="Latency vs depth hint for the upstream engine.",
    )
    sources: list[str] | None = Field(
        default=None,
        description="Upstream extraction sources to use (e.g. 'web', 'crawl4ai').",
    )
    subpages: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Number of same-origin subpages to crawl per URL.",
    )
    subpageTarget: str | None = Field(
        default=None,
        description="Keyword/path filter applied to discovered subpage links.",
    )
    livecrawl: ContentsLivecrawl | None = Field(
        default=None,
        description="Livecrawl cache policy for the upstream engine.",
    )
    maxAgeHours: int | None = Field(
        default=None,
        ge=1,
        le=2160,
        description="Cache freshness window in hours.",
    )
    summary: bool | None = Field(
        default=None,
        description="Whether the engine should return an LLM summary per URL.",
    )
    highlights: bool | list[str] | None = Field(
        default=None,
        description="True for generic highlights, or a list of focus terms.",
    )
    workspace_id: int = Field(
        gt=0,
        description="Workspace context ID.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )

    @field_validator("urls", mode="before")
    @classmethod
    def validate_urls_non_empty(cls, v: Any) -> list[str]:
        """Strip URLs and reject empty entries or an empty list."""
        if not isinstance(v, (list, tuple)):
            raise ValueError("urls must be a list of strings")
        cleaned: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError("each url must be a string")
            trimmed = raw.strip()
            if not trimmed:
                raise ValueError("urls cannot contain empty or whitespace entries")
            if not trimmed.lower().startswith(("http://", "https://")):
                raise ValueError(
                    "each url must start with http:// or https://"
                )
            cleaned.append(trimmed)
        if not cleaned:
            raise ValueError("urls cannot be empty")
        return cleaned

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, v: Any) -> Any:
        """Normalize blank queries to None so the URL-join default applies."""
        if isinstance(v, str):
            trimmed = v.strip()
            return trimmed or None
        return v

    @property
    def estimated_units(self) -> int:
        """Estimated billing units for capability gate checking."""
        return min(len(self.urls), MAX_CONTENTS_URLS)


class ContentItem(BaseModel):
    """One extracted page from the contents response."""

    url: str = Field(description="Page URL that was extracted.")
    title: str | None = Field(default=None, description="Page title.")
    content: str | None = Field(
        default=None, description="Clean markdown/text content for the page."
    )
    summary: str | None = Field(
        default=None, description="Engine-generated summary when requested."
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Relevant excerpt highlights when requested.",
    )
    status: str = Field(
        default="ok",
        description="Per-item extraction status ('ok', 'unsupported_auth_wall', ...).",
    )
    error: str | None = Field(
        default=None,
        description="Upstream error detail when status != 'ok' "
        "(e.g. 'Unable to extract content from this URL').",
    )


class ContentsOutput(BaseModel):
    """Aggregated extraction output for ``chainlens.contents``."""

    items: list[ContentItem] = Field(
        default_factory=list,
        description="Per-URL extraction results, in request order.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Source citations for successfully extracted pages.",
    )
    content: str = Field(
        default="",
        description="Concatenated clean content across items for quick reads.",
    )
    status: str = Field(
        default="complete",
        description="Overall status: 'complete', 'partial', or 'engine_unavailable'.",
    )
    degraded: bool = Field(
        default=False,
        description="Whether the result is degraded due to engine unavailability.",
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
        """One unit per successfully extracted page.

        Pages that failed extraction (status != 'ok') or a fully degraded
        result bill 0 — the caller isn't charged for unusable output.
        """
        return sum(1 for it in self.items if it.status == "ok")
