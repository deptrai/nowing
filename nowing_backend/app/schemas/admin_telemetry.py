from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LlmCostBucket(BaseModel):
    """One provider/model/workspace bucket of LLM cost and token usage."""

    key: str
    total_tokens: int = 0
    cost_micros: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    model_config = ConfigDict(from_attributes=True)


class LlmCostTimeSeriesPoint(BaseModel):
    """One time bucket of aggregate LLM cost and tokens."""

    period: str
    total_tokens: int = 0
    cost_micros: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    model_config = ConfigDict(from_attributes=True)


class LlmCostBreakdown(BaseModel):
    """Aggregate LLM cost and token usage broken down by provider, model, and workspace."""

    window_hours: int
    provider: str | None = None
    workspace_id: int | None = None
    total_tokens: int = 0
    total_cost_micros: int = 0
    non_llm_cost_micros: int = 0
    billing_cost_micros: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_provider: list[LlmCostBucket] = Field(default_factory=list)
    by_model: list[LlmCostBucket] = Field(default_factory=list)
    by_workspace: list[LlmCostBucket] = Field(default_factory=list)
    by_usage_type: list[LlmCostBucket] = Field(default_factory=list)
    time_series: list[LlmCostTimeSeriesPoint] = Field(default_factory=list)
    unreported_cost_rows: int = 0

    model_config = ConfigDict(from_attributes=True)


class GrossMarginPoint(BaseModel):
    """One time bucket of revenue, COGS, and gross margin."""

    period: str
    revenue_micros: int = 0
    cogs_micros: int = 0
    gross_margin: float | None = None

    model_config = ConfigDict(from_attributes=True)


class GrossMarginSummary(BaseModel):
    """Revenue, COGS, and gross margin over a time window."""

    window_hours: int
    total_revenue_micros: int = 0
    total_cogs_micros: int = 0
    billing_cost_micros: int = 0
    non_llm_cost_micros: int = 0
    overall_gross_margin: float | None = None
    worst_workspace_id: int | None = None
    worst_workspace_margin: float | None = None
    worst_model: str | None = None
    points: list[GrossMarginPoint] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProxyHealthSnapshot(BaseModel):
    """A single proxy endpoint health reading."""

    provider: str
    url: str | None = None
    latency_ms: int | None = None
    success_rate: float = 0.0
    status: str  # healthy | degraded | dead | not_configured
    last_error: str | None = None
    last_probed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProxyHealthResponse(BaseModel):
    """Proxy pool health overview."""

    status: str  # healthy | degraded | dead | not_configured
    provider: str
    snapshots: list[ProxyHealthSnapshot] = Field(default_factory=list)
    total: int = 0
    healthy: int = 0
    degraded: int = 0
    dead: int = 0

    model_config = ConfigDict(from_attributes=True)


class CeleryQueueInfo(BaseModel):
    """Telemetry for one Celery queue."""

    name: str
    length: int = 0
    workers: int = 0
    throughput_per_min: int = 0
    stalled_count: int = 0
    status: str  # healthy | backed_up | unavailable

    model_config = ConfigDict(from_attributes=True)


class CeleryQueueResponse(BaseModel):
    """Celery worker and queue telemetry."""

    status: str  # healthy | degraded | unavailable
    active_workers: int = 0
    queues: list[CeleryQueueInfo] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PurgeDeadQueueResponse(BaseModel):
    """Result of a dead-queue purge."""

    queue_name: str
    purged_count: int = 0
    idempotency_key: str

    model_config = ConfigDict(from_attributes=True)
