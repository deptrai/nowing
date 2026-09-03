"""Pydantic schemas for Admin Third-Party Health & Operations (Story 25.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthStatusItem(BaseModel):
    """Snapshot status of a single monitored service/probe."""

    id: int
    category: str
    service_id: str
    service_name: str
    display_group: str
    status: str
    last_probe_at: datetime | None = None
    next_probe_at: datetime | None = None
    latency_ms: int | None = None
    error_rate_15m: float = 0.0
    success_rate_15m: float = 100.0
    last_error: str | None = None
    suggested_action: str | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    alert_threshold: dict[str, Any] | None = None
    acknowledged_until: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthHistoryItem(BaseModel):
    """Historical probe log record."""

    id: int
    service_id: str
    probe_at: datetime
    status: str
    latency_ms: int | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class HealthAlertItem(BaseModel):
    """Incident alert record."""

    id: int
    rule_id: int | None = None
    service_id: str
    status: str
    severity: str
    message: str
    triggered_at: datetime
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    acknowledged_until: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class HealthAlertAcknowledgeRequest(BaseModel):
    """Request to snooze/acknowledge an open alert."""

    duration_minutes: int = Field(default=60, ge=5, le=1440)


class HealthProbeRunRequest(BaseModel):
    """Request to trigger on-demand probes for category or specific service."""

    category: str | None = None


class HealthProbeResultResponse(BaseModel):
    """Result of an on-demand probe execution."""

    service_id: str
    service_name: str
    category: str
    display_group: str
    status: str
    latency_ms: int | None = None
    last_error: str | None = None
    suggested_action: str | None = None
    error_rate_15m: float = 0.0
    success_rate_15m: float = 100.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    probed_at: datetime


class HealthOverviewResponse(BaseModel):
    """Aggregated health overview metrics."""

    overall_status: str
    total_monitored: int
    status_counts: dict[str, int]
    active_alerts_count: int
    categories: dict[str, dict[str, int]]
    registered_categories: list[str]


class HealthStatusesListResponse(BaseModel):
    """List response for health statuses."""

    items: list[HealthStatusItem]
    total: int


class HealthAlertsListResponse(BaseModel):
    """List response for active alerts."""

    items: list[HealthAlertItem]
    total: int


class HealthHistoryListResponse(BaseModel):
    """List response for service probe history."""

    service_id: str
    items: list[HealthHistoryItem]
    total: int
