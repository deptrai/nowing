"""Source risk tier mapping for scraped memory sources (Story 29.6 / FR-97)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)

from app.db.base import BaseModel, TimestampMixin


class MemorySourceLegalTier(BaseModel, TimestampMixin):
    """Legal risk tier and recommended retention window per memory source type.

    Used by the governance console to validate workspace retention policies
    and to trigger scrape pauses when a source is reclassified to high risk.
    """

    __tablename__ = "memory_source_legal_tiers"
    __table_args__ = (
        UniqueConstraint(
            "source_type", name="uq_memory_source_legal_tiers_source_type"
        ),
    )

    source_type = Column(String(50), nullable=False, index=True)
    risk_tier = Column(
        String(20),
        nullable=False,
        default="low",
        server_default=text("'low'"),
        index=True,
    )
    recommended_retention_days = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
