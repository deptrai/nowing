"""Models for the leads domain."""

from __future__ import annotations

import uuid

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class SignalEvent(Base, TimestampMixin):
    """A detected buying-intent signal for a company in a workspace."""

    __tablename__ = "signal_events"

    __table_args__ = (
        Index(
            "ix_signal_events_workspace_lookup",
            "workspace_id",
            "client_id",
            "company_name",
            "signal_type",
            "detected_at",
        ),
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "company_name",
            "signal_type",
            "source_url",
            "detected_at",
            name="uq_signal_events_unique_signal",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False, index=True)
    source_url = Column(Text, nullable=True)
    chunk_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    confidence = Column(Float, nullable=False, default=0.0, server_default="0")
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    processed = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    workspace = relationship("Workspace")
class SignalSubscription(Base, TimestampMixin):
    """Workspace-level signal detection subscription defaults."""

    __tablename__ = "signal_subscriptions"

    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_signal_subscriptions_workspace"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    signal_types = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    notification_channels = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workspace = relationship("Workspace")


__all__ = ["SignalEvent", "SignalSubscription"]
