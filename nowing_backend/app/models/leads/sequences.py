"""Models for the leads domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class Sequence(Base, TimestampMixin):
    """Sequence definition model for multi-channel automated drip outreach (Story 24.1 / AD-39)."""

    __tablename__ = "sequences"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_sequences"),
        ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
            name="fk_sequences_workspace_id",
        ),
        Index("ix_sequences_workspace_status", "workspace_id", "status"),
        Index("ix_sequences_workspace_client", "workspace_id", "client_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, primary_key=True, nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="active", server_default=text("'active'")
    )
    shared = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    entry_step_order = Column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    steps = relationship(
        "SequenceStep",
        back_populates="sequence",
        cascade="all, delete-orphan",
        order_by="SequenceStep.step_order",
    )
    runs = relationship(
        "SequenceRun", back_populates="sequence", cascade="all, delete-orphan"
    )
    enrollments = relationship(
        "SequenceEnrollment", back_populates="sequence", cascade="all, delete-orphan"
    )
    events = relationship(
        "SequenceEvent", back_populates="sequence", cascade="all, delete-orphan"
    )
class SequenceStep(Base, TimestampMixin):
    """Step definition inside a Sequence (Story 24.1 / AD-39)."""

    __tablename__ = "sequence_steps"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_steps"),
        ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_steps_sequence",
        ),
        Index("ix_sequence_steps_order", "workspace_id", "sequence_id", "step_order"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, primary_key=True, nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    sequence_id = Column(UUID(as_uuid=True), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_type = Column(
        String(50), nullable=False
    )  # send_email, wait, condition, update_lead_score, update_crm, tag
    channel = Column(
        String(50), nullable=False, default="email", server_default=text("'email'")
    )
    fallback_channels = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    template = Column(
        JSONB, nullable=True, default=dict, server_default=text("'{}'::jsonb")
    )
    wait_duration_seconds = Column(Integer, nullable=True)
    condition_config = Column(
        JSONB, nullable=True, default=dict, server_default=text("'{}'::jsonb")
    )
    is_enabled = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    sequence = relationship("Sequence", back_populates="steps")
class SequenceRun(Base, TimestampMixin):
    """Execution run instance triggered manually or by an AlertRule (Story 24.1 / AD-39 / AD-43)."""

    __tablename__ = "sequence_runs"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_runs"),
        ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_runs_sequence",
        ),
        Index("ix_sequence_runs_seq", "workspace_id", "sequence_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, primary_key=True, nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    sequence_id = Column(UUID(as_uuid=True), nullable=False)
    triggering_alert_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        String(50), nullable=False, default="running", server_default=text("'running'")
    )  # running, completed, cancelled
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    sequence = relationship("Sequence", back_populates="runs", overlaps="runs,sequence")
    enrollments = relationship(
        "SequenceEnrollment", back_populates="run", overlaps="enrollments,run"
    )
class SequenceEnrollment(Base, TimestampMixin):
    """Lead enrollment state in a sequence with OCC versioning (Story 24.1 / AD-39 / INV-24.7)."""

    __tablename__ = "sequence_enrollments"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_enrollments"),
        UniqueConstraint(
            "sequence_id",
            "lead_id",
            "workspace_id",
            name="uq_sequence_enrollments_seq_lead",
        ),
        ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_enrollments_sequence",
        ),
        ForeignKeyConstraint(
            ["sequence_run_id", "workspace_id"],
            ["sequence_runs.id", "sequence_runs.workspace_id"],
            ondelete="SET NULL",
            name="fk_sequence_enrollments_run",
        ),
        Index(
            "ix_sequence_enrollments_sched", "workspace_id", "status", "scheduled_at"
        ),
        Index("ix_sequence_enrollments_lead", "workspace_id", "lead_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, primary_key=True, nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    sequence_id = Column(UUID(as_uuid=True), nullable=False)
    lead_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sequence_run_id = Column(UUID(as_uuid=True), nullable=True)
    current_step = Column(Integer, nullable=False, default=1, server_default=text("1"))
    status = Column(
        String(50),
        nullable=False,
        default="scheduled",
        server_default=text("'scheduled'"),
    )  # scheduled, executing, paused, responded, unsubscribed, failed, completed
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=0, server_default=text("0"))
    last_event_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    sequence = relationship(
        "Sequence", back_populates="enrollments", overlaps="enrollments,sequence"
    )
    run = relationship(
        "SequenceRun", back_populates="enrollments", overlaps="enrollments,sequence"
    )
    events = relationship(
        "SequenceEvent",
        back_populates="enrollment",
        cascade="all, delete-orphan",
        overlaps="events,enrollment",
    )
class SequenceEvent(Base):
    """Immutable log of sequence interactions, sends, and responses (Story 24.1 / AD-39 / AD-42)."""

    __tablename__ = "sequence_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_sequence_events"),
        ForeignKeyConstraint(
            ["enrollment_id", "workspace_id"],
            ["sequence_enrollments.id", "sequence_enrollments.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_events_enrollment",
        ),
        ForeignKeyConstraint(
            ["sequence_id", "workspace_id"],
            ["sequences.id", "sequences.workspace_id"],
            ondelete="CASCADE",
            name="fk_sequence_events_sequence",
        ),
        Index(
            "ix_sequence_events_enrollment",
            "workspace_id",
            "enrollment_id",
            "event_type",
        ),
        Index(
            "ix_sequence_events_seq_type", "workspace_id", "sequence_id", "event_type"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, primary_key=True, nullable=False, index=True)
    client_id = Column(CITEXT, nullable=True, index=True)
    enrollment_id = Column(UUID(as_uuid=True), nullable=False)
    sequence_id = Column(UUID(as_uuid=True), nullable=False)
    step_id = Column(UUID(as_uuid=True), nullable=True)
    event_type = Column(
        String(50), nullable=False
    )  # sent, delivered, opened, replied, bounced, meeting_booked, failed, skipped
    event_subtype = Column(
        String(100), nullable=True
    )  # insufficient_credits, smtp_error, no_consent, opt_out, etc.
    channel = Column(
        String(50), nullable=False, default="email", server_default=text("'email'")
    )
    cost_micros = Column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    event_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    provider_msg_id = Column(String(255), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    enrollment = relationship(
        "SequenceEnrollment", back_populates="events", overlaps="events,enrollment"
    )
    sequence = relationship(
        "Sequence", back_populates="events", overlaps="enrollment,events"
    )


__all__ = ["Sequence", "SequenceEnrollment", "SequenceEvent", "SequenceRun", "SequenceStep"]
