"""Browser operator audit events model for CDP command logging (Story 32.3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base, TimestampMixin


class BrowserOperatorAuditEvent(Base, TimestampMixin):
    """Immutable audit log entry for every CDP command execution."""

    __tablename__ = "browser_operator_audit_events"

    __table_args__ = (
        Index("ix_browser_audit_mission", "mission_id"),
        Index("ix_browser_audit_workspace", "workspace_id"),
        Index("ix_browser_audit_created", "created_at"),
        Index("ix_browser_audit_command_id", "command_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dsh_missions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    command_id = Column(String(64), nullable=False)
    action = Column(String(32), nullable=False)
    target_url = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    challenge = Column(String(64), nullable=True)
    requires_human = Column(Boolean, nullable=False, default=False)
    duration_ms = Column(Integer, nullable=True)
    metadata_ = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
    )

    def __repr__(self) -> str:
        return (
            f"<BrowserOperatorAuditEvent(id={self.id}, mission_id={self.mission_id}, "
            f"action={self.action}, success={self.success})>"
        )
