"""Models for the leads domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, BaseModel, TimestampMixin


class DshMission(Base, TimestampMixin):
    """
    Long-running DSH mission state. PII/full payload and checkpoint are kept
    in private JSONB columns and intentionally NOT published to zero_publication.
    Only PII-safe columns are published so the mission progress UI stays live.
    """

    __tablename__ = "dsh_missions"
    __allow_unmapped__ = True

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'error', 'cancelled', 'dlq')",
            name="chk_dsh_missions_status",
        ),
        CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="chk_dsh_missions_progress_percent",
        ),
        Index("ix_dsh_missions_workspace_id_status", "workspace_id", "status"),
        Index(
            "ix_dsh_missions_next_fire_at",
            "workspace_id",
            "status",
            "next_fire_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    mission_type = Column(
        String(64),
        nullable=False,
        default="deep_lead_research",
    )
    status = Column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    phase = Column(String(32), nullable=True)
    progress_percent = Column(
        Integer,
        nullable=True,
        default=0,
        server_default="0",
    )
    current_subtask_id = Column(String(64), nullable=True)
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )
    # Story 6.10: scheduled recurring report support.
    schedule = Column(JSONB, nullable=True, default=dict, server_default=text("'{}'::jsonb"))
    source = Column(String(32), nullable=True)
    request_text = Column(Text, nullable=True)
    next_fire_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_fired_at = Column(TIMESTAMP(timezone=True), nullable=True)
    payload = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    checkpoint = Column(
        JSONB,
        nullable=False,
        default=lambda: {"version": 1, "phase": "crawl", "subtasks": []},
        server_default=text(
            '\'{"version": 1, "phase": "crawl", "subtasks": []}\'::jsonb'
        ),
    )
    error = Column(JSONB, nullable=True)
class TelegramCheckpointMessage(Base, TimestampMixin):
    """Maps a Telegram inline-keyboard message to a lead/contact for DSH checkpoints."""

    __tablename__ = "telegram_checkpoint_messages"

    __table_args__ = (
        UniqueConstraint(
            "callback_token", name="uq_telegram_checkpoint_callback_token"
        ),
        Index(
            "ix_telegram_checkpoint_message_peer",
            "external_message_id",
            "external_peer_id",
        ),
        Index(
            "ix_telegram_checkpoint_workspace_mission",
            "workspace_id",
            "mission_id",
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
        Index("ix_telegram_checkpoint_workspace_lead", "workspace_id", "lead_id"),
        Index("ix_telegram_checkpoint_workspace_id", "workspace_id"),
        Index("ix_telegram_checkpoint_mission_id", "mission_id"),
        Index("ix_telegram_checkpoint_lead_id", "lead_id"),
        Index("ix_telegram_checkpoint_contact_id", "contact_id"),
        Index("ix_telegram_checkpoint_user_id", "user_id"),
        CheckConstraint(
            "status IN ('sent', 'unlocked', 'dismissed', 'refunded')",
            name="ck_telegram_checkpoint_status",
        ),
        CheckConstraint(
            "callback_token ~ '^[A-Za-z0-9_-]{16,24}$'",
            name="ck_telegram_checkpoint_callback_token",
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_telegram_checkpoint_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    callback_token = Column(String(24), nullable=False)
    status = Column(String(20), nullable=False, default="sent", server_default="sent")

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    mission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dsh_missions.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id = Column(UUID(as_uuid=True), nullable=False)
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verified_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    external_message_id = Column(Text, nullable=True)
    external_peer_id = Column(Text, nullable=True)

    unlocked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    refunded_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Safe metadata only (e.g. {"dossier_visible": true}). NEVER store unmasked PII here.
    action_payload = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
class ChainLensIngestJob(BaseModel, TimestampMixin):
    """One chainlens-research scraper ingest job recorded in Nowing Postgres."""

    __tablename__ = "chainlens_ingest_jobs"
    __allow_unmapped__ = True

    __table_args__ = (
        Index(
            "ix_chainlens_ingest_jobs_workspace_created",
            "workspace_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scraper_id = Column(String(100), nullable=False, index=True)
    parent_ingest_job_id = Column(String(255), nullable=True)
    child_ingest_job_ids = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    noop_source_ids = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    ingested_source_ids = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    chunks_received_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    chunks_ingested_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status = Column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    error = Column(Text, nullable=True)
    dead_letter_payload = Column(JSONB, nullable=True)
    run_id = Column(String(255), nullable=True, index=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="chainlens_ingest_jobs")


__all__ = ["ChainLensIngestJob", "DshMission", "TelegramCheckpointMessage"]
