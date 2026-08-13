"""AlertRule model — first-class saved search / alert configuration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base, TimestampMixin


class AlertRule(Base, TimestampMixin):
    """A scheduled, parameterized capability call with diff + notification rules.

    This is the first-class data model for saved searches and other alerting
    surfaces. It is NOT stored inside ``Automation.definition`` (AD-43).
    """

    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)

    # Registered capability name, e.g. "vn_jobs.aggregate".
    capability_id = Column(String(200), nullable=False, index=True)

    # User-facing name for this saved search / alert.
    name = Column(String(200), nullable=False)

    # Structured query passed to the capability (JSONB).
    query = Column(JSONB, nullable=False)

    # Human schedule label; cron is derived from this.
    schedule = Column(String(20), nullable=False, default="none", server_default="none")
    # IANA timezone, e.g. "UTC" or "Asia/Ho_Chi_Minh".
    timezone = Column(String(64), nullable=False, default="UTC", server_default="UTC")
    # Derived cron expression for the schedule selector.
    cron = Column(String(64), nullable=True)

    # Precomputed scheduler fields (same pattern as AutomationTrigger).
    next_fire_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    last_fired_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Diff strategy: "new_items" | "price_change" | "threshold_cross" | "trend_detect".
    diff_strategy = Column(String(40), nullable=False, default="new_items")
    threshold = Column(JSONB, nullable=True)

    # AD-43: signal-driven sequence enrollment fields (null for notification-only rules).
    # ponytail: FKs to Sequence/SequenceStep are deferred until those tables land;
    # keeping the columns nullable and un-fk'd lets 12.6 ship without a dangling FK.
    target_sequence_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    target_step_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Genuine notification channels only; sequence_enrollment is NOT a channel.
    notification_channels = Column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    snapshots = relationship(
        "AlertSnapshot",
        back_populates="alert_rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AlertSnapshot.created_at.desc()",
    )
    subscriptions = relationship(
        "AlertSubscription",
        back_populates="alert_rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            "ix_alert_rules_due",
            "workspace_id",
            "enabled",
            "next_fire_at",
            postgresql_where=Column("enabled"),
        ),
    )

    def compute_next_fire_at(self, *, after: datetime | None = None) -> datetime | None:
        """Return the next fire moment in UTC for this rule's cron string."""
        from app.alerts.engine.cron import compute_next_fire_at

        if not self.cron or self.schedule == "none" or not self.enabled:
            return None
        return compute_next_fire_at(
            self.cron, self.timezone, after=after or datetime.now(UTC)
        )
