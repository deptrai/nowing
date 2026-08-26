from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleDelays(BaseModel):
    """Delay configuration for a scraper rule."""

    model_config = ConfigDict(extra="forbid")

    request_ms: int = Field(default=1500, ge=0, le=60000)
    retry_base_ms: int = Field(default=1000, ge=0, le=60000)


class RuleRetries(BaseModel):
    """Retry policy for a scraper rule."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=3, ge=0, le=10)
    statuses: list[int] = Field(default_factory=lambda: [403, 429, 500, 502, 503])


class RuleCircuitBreaker(BaseModel):
    """Circuit breaker configuration for a scraper rule."""

    model_config = ConfigDict(extra="forbid")

    error_threshold_pct: int = Field(default=20, ge=0, le=100)
    min_calls: int = Field(default=10, ge=0)
    trip_duration_seconds: int = Field(default=300, ge=1, le=3600)
    tripped: bool = Field(default=False)


class RuleSchema(BaseModel):
    """Pydantic schema for the JSONB rule_schema payload.

    Matches the contract in Story 25.5.
    """

    model_config = ConfigDict(extra="forbid")

    selectors: dict[str, str] = Field(default_factory=dict)
    regexes: dict[str, str] = Field(default_factory=dict)
    delays: RuleDelays = Field(default_factory=RuleDelays)
    retries: RuleRetries = Field(default_factory=RuleRetries)
    circuit_breaker: RuleCircuitBreaker = Field(default_factory=RuleCircuitBreaker)


class ScraperRuleBase(BaseModel):
    """Base fields for scraper rule API contracts."""

    platform: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)
    rule_schema: RuleSchema
    is_active: bool = False


class ScraperRuleCreate(BaseModel):
    """Request body for creating a new scraper rule version."""

    rule_schema: RuleSchema


class ScraperRuleUpdate(BaseModel):
    """Request body for activating/deactivating a rule version."""

    is_active: bool


class ScraperRuleRead(ScraperRuleBase):
    """Response body for a single scraper rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ScraperRuleListItem(BaseModel):
    """List response item — limited public fields."""

    model_config = ConfigDict(from_attributes=True)

    platform: str
    version: int
    is_active: bool
    updated_at: datetime
    updated_by: UUID | None


class ScraperRuleListResponse(BaseModel):
    """Paginated list response."""

    items: list[ScraperRuleListItem]
    total: int


class ScraperRuleMetricsResponse(BaseModel):
    """Recent success/error metrics for a scraper platform."""

    platform: str
    successes: int
    errors: int
    total: int
    error_rate_pct: float
