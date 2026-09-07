"""Models for the workspace health and adoption analytics domain (Story 29.2, AD-52)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, TimestampMixin


class WorkspaceHealthDaily(BaseModel, TimestampMixin):
    """Pre-aggregated daily health and adoption metrics for a workspace (AD-52)."""

    __tablename__ = "workspace_health_daily"

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, index=True)
    active_members_dau = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    active_members_wau = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_memories = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    memory_growth_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    recall_queries = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    remember_queries = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    research_queries = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    credits_consumed_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    cost_per_turn_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    top_sources = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_coverage_gap_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_members = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="health_daily_metrics")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "date", name="uq_workspace_health_daily_workspace_date"
        ),
    )
