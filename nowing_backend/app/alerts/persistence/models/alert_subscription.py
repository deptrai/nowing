"""AlertSubscription model — per-user channel preferences for an alert rule."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base, TimestampMixin


class AlertSubscription(Base, TimestampMixin):
    """Who gets notified and through which channels for a given alert rule."""

    __tablename__ = "alert_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Subset of alert_rule.notification_channels this user wants.
    channels = Column(JSONB, nullable=False, default=list, server_default="[]")
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    user = relationship("User")
    alert_rule = relationship("AlertRule", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "alert_rule_id", name="uq_alert_subscription_user_rule"
        ),
    )
