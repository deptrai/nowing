"""AlertSnapshot model — per-run result snapshot for diffing."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base, TimestampMixin


class AlertSnapshot(Base, TimestampMixin):
    """Stores the output of one alert rule execution for delta comparison."""

    __tablename__ = "alert_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Normalized snapshot used by diff strategies.
    snapshot_json = Column(JSONB, nullable=False, default=dict, server_default="{}")

    # Run result summary.
    run_status = Column(String(40), nullable=False)
    degradation_reasons = Column(JSONB, nullable=True)
    new_items_count = Column(Integer, nullable=False, default=0)
    changed_items_count = Column(Integer, nullable=False, default=0)
    removed_items_count = Column(Integer, nullable=False, default=0)

    alert_rule = relationship("AlertRule", back_populates="snapshots")
