"""Data models and schemas for Narrative Report Engine (Story 6.12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceCitation(BaseModel):
    """Citation metadata identifying an indexed source article or document."""

    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(..., description="Indexed source ID (e.g. source-1 or UUID)")
    title: str = Field(..., description="Title of the article or publication")
    url: str = Field(..., description="URL or canonical web link")
    pub_date: str | None = Field(default=None, description="ISO publication date if available")
    source_type: str = Field(default="web", description="web, news, finance, or company")


class NarrativeReportMetadata(BaseModel):
    """Structured metadata persisted in Report.report_metadata."""

    model_config = ConfigDict(extra="ignore")

    narrative_style: str = Field(..., description="digest, trend, or timeline")
    template_id: str = Field(..., description="news_digest, financial_trend, or company_timeline")
    entity_key: str | None = Field(default=None, description="Ticker, topic, or company tax code")
    citations: list[SourceCitation] = Field(default_factory=list)
    degraded: bool = Field(default=False, description="True if data was empty or fallback triggered")
    degradation_reasons: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class NarrativeTemplateParameter(BaseModel):
    """Parameter definition for narrative report template."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(...)
    label: str = Field(...)
    description: str | None = Field(default=None)
    type: str = Field(default="string")
    required: bool = Field(default=True)
    default: Any | None = Field(default=None)
    options: list[dict[str, str]] | None = Field(default=None)


class NarrativeTemplate(BaseModel):
    """Specification of a registered narrative report template."""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    name: str
    description: str
    narrative_style: str  # digest, trend, timeline
    required_capability: str
    parameters: list[NarrativeTemplateParameter]


class NarrativeReportCreateRequest(BaseModel):
    """Request payload to generate a narrative report on demand (Story 6.12)."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=255)
    parameters: dict[str, Any] = Field(default_factory=dict)
