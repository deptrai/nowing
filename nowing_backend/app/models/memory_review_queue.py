"""Memory review queue model (Story 29.5 / FR-104)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    TIMESTAMP,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db import BaseModel, TimestampMixin


class MemoryReviewQueue(BaseModel, TimestampMixin):
    """Queue for memories flagged by analysts for review."""

    __tablename__ = "memory_review_queue"

    memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flag_reason = Column(Text, nullable=False)
    flagged_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="open", index=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
