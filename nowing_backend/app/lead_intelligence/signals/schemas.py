"""Pydantic schemas for signal detection."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db import MemorySourceType


class SignalInput(BaseModel):
    """Input to a signal detection capability."""

    company_name: str = Field(..., min_length=1, max_length=200)
    domain: str | None = Field(None, max_length=255)
    lookback_days: int = Field(default=30, ge=0)
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=100.0)
    signal_types: list[str] | None = None

    @field_validator("company_name")
    @classmethod
    def _strip_and_require_company_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("company_name must not be empty or whitespace")
        return v


class SignalDetectInput(SignalInput):
    """REST payload for running a one-shot signal detection."""

    signal_type: str = "funding"


class SignalEventRead(BaseModel):
    """A single detected signal event, returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    client_id: str | None
    company_name: str
    signal_type: str
    source_url: str | None
    chunk_id: UUID | None
    confidence: float
    detected_at: datetime
    processed: bool

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(100.0, v))

    @model_validator(mode="after")
    def _no_score_fields(self):
        # Guard against any score fields leaking into the read model.
        for forbidden in ("lead_score", "fit_score", "intent_score"):
            if forbidden in self.model_dump():
                raise ValueError(f"SignalEventRead must not contain {forbidden}")
        return self


class SignalOutput(BaseModel):
    """Aggregate output from a signal detection run."""

    items: list[SignalEventRead] = Field(default_factory=list)
    cost_micros: int = 0
    degraded: bool = False
    degradation_reasons: list[str] | None = None

    @field_validator("items")
    @classmethod
    def _items_are_signal_events(cls, v: list[Any]) -> list[Any]:
        return v


class SignalListParams(BaseModel):
    """Query parameters for listing signal events."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    signal_type: str | None = None
    company_name: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    confidence_min: float = Field(default=0.0, ge=0.0, le=100.0)
    sort: str = Field(default="detected_at_desc")

    @model_validator(mode="after")
    def _date_range(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before to_date")
        return self


class SignalSubscriptionRead(BaseModel):
    """Read view of a workspace signal subscription."""

    workspace_id: int
    client_id: str | None
    signal_types: list[str]
    notification_channels: list[str]
    created_by_user_id: UUID | None


class SignalListResponse(BaseModel):
    """Paginated list of signal events."""

    items: list[SignalEventRead]
    total: int
    limit: int
    offset: int


class SignalSubscriptionUpdate(BaseModel):
    """Update a workspace signal subscription."""

    signal_types: list[str]
    notification_channels: list[str]


class MemorySignalSummary(BaseModel):
    """Redacted summary stored as a Memory row for a signal."""

    content: str
    source_type: MemorySourceType = MemorySourceType.SIGNAL
    source_entity_type: str = "SignalEvent"
    source_capability: str
    source_input: dict
    tags: list[str] = ["lead_signal"]
    confidence: float
