"""SQLAlchemy models for Admin Third-Party Health & Operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import BaseModel, TimestampMixin


class AdminHealthStatus(BaseModel, TimestampMixin):
    """Current health snapshot for a monitored third-party service or infra component."""

    __tablename__ = "admin_health_status"
    __table_args__ = (
        Index("ix_admin_health_status_category", "category"),
        Index("ix_admin_health_status_status", "status"),
    )

    category = Column(String(50), nullable=False)
    service_id = Column(String(255), nullable=False, unique=True, index=True)
    service_name = Column(String(255), nullable=False)
    display_group = Column(String(100), nullable=False, default="General")
    status = Column(
        String(50), nullable=False, default="not_configured"
    )  # healthy, degraded, unavailable, disabled, not_configured
    last_probe_at = Column(TIMESTAMP(timezone=True), nullable=True)
    next_probe_at = Column(TIMESTAMP(timezone=True), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_rate_15m = Column(Float, nullable=False, default=0.0)
    success_rate_15m = Column(Float, nullable=False, default=100.0)
    last_error = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    metadata_payload = Column(JSONB, nullable=False, default=dict)
    alert_threshold = Column(JSONB, nullable=True)
    acknowledged_until = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class AdminHealthHistory(BaseModel, TimestampMixin):
    """Historical time-series entry of probe results."""

    __tablename__ = "admin_health_history"
    __table_args__ = (
        Index("ix_admin_health_history_service_probe", "service_id", "probe_at"),
    )

    service_id = Column(String(255), nullable=False, index=True)
    probe_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        index=True,
    )
    status = Column(String(50), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class AdminHealthAlertRule(BaseModel, TimestampMixin):
    """Alert rules for third-party health monitoring."""

    __tablename__ = "admin_health_alert_rules"

    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)  # None = all
    service_id_pattern = Column(String(255), nullable=True)  # regex / glob
    condition_json = Column(JSONB, nullable=False, default=dict)
    severity = Column(String(50), nullable=False, default="high")  # critical, high, medium, low
    channels = Column(JSONB, nullable=False, default=lambda: ["in_app"])
    cooldown_minutes = Column(Integer, nullable=False, default=15)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class AdminHealthAlert(BaseModel, TimestampMixin):
    """Triggered health alert incident."""

    __tablename__ = "admin_health_alerts"
    __table_args__ = (
        Index("ix_admin_health_alerts_service_status", "service_id", "status"),
    )

    rule_id = Column(
        Integer,
        ForeignKey("admin_health_alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_id = Column(String(255), nullable=False, index=True)
    status = Column(
        String(50), nullable=False, default="open"
    )  # open, acknowledged, resolved
    severity = Column(String(50), nullable=False, default="high")
    message = Column(Text, nullable=False)
    triggered_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_until = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )
