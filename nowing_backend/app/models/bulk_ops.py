"""Models for bulk operations console (Story 29.4 / Admin Bulk Operations)."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, BaseModel, TimestampMixin


class BulkAction(StrEnum):
    ARCHIVE_INACTIVE_WORKSPACES = "archive_inactive_workspaces"
    ROTATE_API_KEYS = "rotate_api_keys"
    ASSIGN_ROLE = "assign_role"
    DELETE_SOURCE_TYPE_MEMORIES = "delete_source_type_memories"
    APPLY_TIER = "apply_tier"
    REVOKE_MEMBERSHIP = "revoke_membership"


class BulkOpJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class BulkOpJob(Base, TimestampMixin):
    """Represents an asynchronous bulk operation job."""

    __tablename__ = "bulk_op_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(String(64), nullable=False, index=True)
    status = Column(
        String(32),
        nullable=False,
        default=BulkOpJobStatus.QUEUED.value,
        server_default=BulkOpJobStatus.QUEUED.value,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    filter_spec = Column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    action_params = Column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    idempotency_key = Column(
        String(64), nullable=True, unique=True, index=True
    )
    request_hash = Column(
        String(64), nullable=False, default="", server_default="", index=True
    )
    total_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    processed_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    affected_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    celery_task_id = Column(String(255), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    errors = relationship(
        "BulkOpError",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="BulkOpError.id.asc()",
    )
    actor = relationship("User", foreign_keys=[actor_id])
    workspace = relationship("Workspace", foreign_keys=[workspace_id])

    __table_args__ = (
        Index("ix_bulk_op_jobs_actor_status", "actor_id", "status"),
        Index("ix_bulk_op_jobs_created_status", "created_at", "status"),
    )


class BulkOpError(BaseModel, TimestampMixin):
    """Records individual subject failures in a bulk operation job."""

    __tablename__ = "bulk_op_errors"

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bulk_op_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_type = Column(String(50), nullable=False, index=True)
    subject_id = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    retryable = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    job = relationship("BulkOpJob", back_populates="errors")

    __table_args__ = (
        Index("ix_bulk_op_errors_job_subject", "job_id", "subject_type", "subject_id"),
    )


class IdempotencyKey(BaseModel, TimestampMixin):
    """Guards bulk operations and critical actions against replay attacks / duplicate runs."""

    __tablename__ = "idempotency_keys"

    key = Column(String(64), nullable=False, unique=True, index=True)
    request_hash = Column(String(64), nullable=False, index=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bulk_op_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
