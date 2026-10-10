"""Webset Campaign tracking model (Story 41.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class WebsetCampaign(Base, TimestampMixin):
    """Tracks asynchronous ChainLens Webset builds for lead campaigns."""

    __tablename__ = "webset_campaigns"
    __table_args__ = (
        Index("ix_webset_campaigns_webset_id", "webset_id", unique=True),
        Index("ix_webset_campaigns_workspace_id", "workspace_id"),
        Index("ix_webset_campaigns_campaign_id", "campaign_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    webset_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="ChainLens Webset ID (e.g. wbs_...)",
    )
    campaign_id = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Associated Nowing campaign ID or client_id",
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_secret = Column(
        String(255),
        nullable=False,
        doc="Per-webset secret for verifying inbound webhooks via constant-time compare",
    )
    stats = Column(
        JSONB,
        nullable=True,
        default=dict,
        doc="Snapshot stats from webset run / webhook payload",
    )
    last_delivery_id = Column(
        String(255),
        nullable=True,
        doc="Delivery UUID from ChainLens webhook for deduplication",
    )
    imported_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Count of imported leads from this webset",
    )
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        doc="Status of the webset campaign: pending, completed, failed, degraded",
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace")
