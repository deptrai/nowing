"""``playbooks`` table — reusable, versioned automation templates."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from app.db import BaseModel, TimestampMixin

from ..enums.playbook_scope import PlaybookScope


class Playbook(BaseModel, TimestampMixin):
    __tablename__ = "playbooks"

    __table_args__ = (
        Index(
            "uq_playbooks_name_scope_system",
            "name",
            "scope",
            unique=True,
            postgresql_where=text("workspace_id IS NULL"),
        ),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    definition = Column(JSONB, nullable=False)

    # Copy of definition.inputs.schema; the source of truth for instantiation.
    inputs_schema = Column(JSONB, nullable=False)

    version = Column(Integer, nullable=False, default=1, server_default="1")

    # Allowed action type strings for runs derived from this playbook.
    tool_scope = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    verticals = Column(
        JSONB,
        nullable=False,
        default=lambda: ["general"],
        server_default=text("'[\"general\"]'::jsonb"),
    )

    scope = Column(
        SQLAlchemyEnum(
            PlaybookScope,
            name="playbook_scope",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PlaybookScope.WORKSPACE,
        server_default=PlaybookScope.WORKSPACE.value,
        index=True,
    )

    is_approved = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    workspace = relationship("Workspace", back_populates="playbooks")
    created_by = relationship("User", back_populates="playbooks")
    automations = relationship(
        "Automation",
        back_populates="playbook",
        passive_deletes=True,
    )
