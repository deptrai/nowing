"""Models for the leads domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Float,
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
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.config import config
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


class SignalEvent(Base, TimestampMixin):
    """A detected buying-intent signal for a company in a workspace."""

    __tablename__ = "signal_events"

    __table_args__ = (
        Index(
            "ix_signal_events_workspace_lookup",
            "workspace_id",
            "client_id",
            "company_name",
            "signal_type",
            "detected_at",
        ),
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "company_name",
            "signal_type",
            "source_url",
            "detected_at",
            name="uq_signal_events_unique_signal",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False, index=True)
    source_url = Column(Text, nullable=True)
    chunk_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    confidence = Column(Float, nullable=False, default=0.0, server_default="0")
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    processed = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    workspace = relationship("Workspace")


class SignalSubscription(Base, TimestampMixin):
    """Workspace-level signal detection subscription defaults."""

    __tablename__ = "signal_subscriptions"

    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_signal_subscriptions_workspace"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    signal_types = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    notification_channels = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workspace = relationship("Workspace")


class Lead(Base, TimestampMixin):
    """A lead record imported or created for outbound prospecting (Story 21.2 / 23.4)."""

    __tablename__ = "leads"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_leads"),
        Index("ix_leads_workspace_created", "workspace_id", "created_at"),
        Index("ix_leads_tax_id", "tax_id"),
        Index(
            "ix_leads_needs_enrichment",
            "needs_enrichment",
            postgresql_where=text("needs_enrichment = true"),
        ),
        UniqueConstraint(
            "workspace_id",
            "value_hmac",
            name="uq_leads_workspace_value_hmac",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    source = Column(String(100), nullable=False, index=True)
    source_url = Column(Text, nullable=True)
    source_chunk_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)
    industry = Column(String(100), nullable=True, index=True)
    company_size = Column(String(50), nullable=True)
    location = Column(String(100), nullable=True)
    tech_stack = Column(ARRAY(String), nullable=True, default=list)
    fit_score = Column(Float, nullable=True)
    intent_score = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)
    schema_completeness_score = Column(Float, nullable=True)
    needs_enrichment = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    area = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="new", server_default="new")
    enriched = Column(Boolean, nullable=False, default=False, server_default="false")
    consent_status = Column(String(50), nullable=True)
    legal_basis = Column(String(50), nullable=True)
    value_hmac = Column(String(64), nullable=False, index=True)
    tax_id = Column(String(50), nullable=True)
    legal_representative = Column(String(200), nullable=True)
    charter_capital_vnd = Column(BigInteger, nullable=True)
    company_status = Column(String(100), nullable=True)
    is_zalo_active = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        doc="Generated full-text search vector across company, domain, tax, industry, location.",
    )
    embedding = Column(
        Vector(1536),
        nullable=True,
        doc="Optional semantic embedding for ICP / natural-language lead matching.",
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="leads")
    lead_scores = relationship(
        "LeadScore",
        back_populates="lead",
        primaryjoin="and_(LeadScore.lead_id == Lead.id, LeadScore.workspace_id == Lead.workspace_id)",
        order_by="LeadScore.computed_at.desc()",
        cascade="all, delete-orphan",
        overlaps="workspace,lead_scores",
    )
    enrichment_requests = relationship(
        "EnrichmentRequest",
        back_populates="lead",
        primaryjoin="and_(EnrichmentRequest.lead_id == Lead.id, EnrichmentRequest.workspace_id == Lead.workspace_id)",
        cascade="all, delete-orphan",
        overlaps="workspace,enrichment_requests",
    )
    verified_contacts = relationship(
        "VerifiedContact",
        back_populates="lead",
        primaryjoin="and_(VerifiedContact.lead_id == Lead.id, VerifiedContact.workspace_id == Lead.workspace_id)",
        cascade="all, delete-orphan",
        overlaps="workspace,verified_contacts",
    )
    phone_waterfall_logs = relationship(
        "PhoneWaterfallLog",
        back_populates="lead",
        primaryjoin="and_(PhoneWaterfallLog.lead_id == Lead.id, PhoneWaterfallLog.workspace_id == Lead.workspace_id)",
        cascade="all, delete-orphan",
        overlaps="workspace,phone_waterfall_logs",
    )
    zalo_message_logs = relationship(
        "ZaloMessageLog",
        back_populates="lead",
        primaryjoin="and_(ZaloMessageLog.lead_id == Lead.id, ZaloMessageLog.workspace_id == Lead.workspace_id)",
        order_by="ZaloMessageLog.created_at.desc()",
        cascade="all, delete-orphan",
        overlaps="workspace,zalo_message_logs",
    )
    outcome_events = relationship(
        "OutcomeEvent",
        back_populates="lead",
        primaryjoin="and_(OutcomeEvent.lead_id == Lead.id, OutcomeEvent.workspace_id == Lead.workspace_id)",
        cascade="all, delete-orphan",
        overlaps="workspace,outcome_events",
    )

    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    table = relationship("WorkspaceTable", back_populates="leads")

    # CRM Pipeline & Lead Distribution columns (Story 24.3 / INV-23.4 / INV-24.4)
    stage_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    assigned_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1, server_default="1")

    stage = relationship(
        "LeadPipelineStage",
        back_populates="leads",
        primaryjoin="and_(LeadPipelineStage.id == Lead.stage_id, LeadPipelineStage.workspace_id == Lead.workspace_id)",
        foreign_keys="[Lead.stage_id, Lead.workspace_id]",
        overlaps="workspace,leads",
    )
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
    assignments = relationship(
        "LeadAssignment",
        back_populates="lead",
        primaryjoin="and_(LeadAssignment.lead_id == Lead.id, LeadAssignment.workspace_id == Lead.workspace_id)",
        cascade="all, delete-orphan",
        overlaps="workspace,lead_assignments",
    )
    activity_logs = relationship(
        "LeadActivityLog",
        back_populates="lead",
        primaryjoin="and_(LeadActivityLog.lead_id == Lead.id, LeadActivityLog.workspace_id == Lead.workspace_id)",
        order_by="LeadActivityLog.created_at.desc()",
        cascade="all, delete-orphan",
        overlaps="workspace,lead_activity_logs",
    )


class ExportJob(Base, TimestampMixin):
    """Lead export batch job for CSV / Lark / Google Sheets (Story 21.13)."""

    __tablename__ = "export_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    export_type = Column(String(50), nullable=False)
    status = Column(
        String(50), nullable=False, default="pending", server_default=text("'pending'")
    )
    total_rows = Column(Integer, nullable=False, default=0, server_default="0")
    processed_rows = Column(Integer, nullable=False, default=0, server_default="0")
    target_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    config = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    workspace = relationship("Workspace")
    table = relationship("WorkspaceTable")


class LeadPipelineStage(Base, TimestampMixin):
    """Pipeline stages for multi-seat CRM Kanban board (Story 24.3 / INV-23.4)."""

    __tablename__ = "lead_pipeline_stages"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_pipeline_stages"),
        UniqueConstraint(
            "workspace_id", "slug", name="uq_lead_pipeline_stages_workspace_slug"
        ),
        Index("ix_lead_pipeline_stages_workspace_pos", "workspace_id", "position"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), nullable=False)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    color = Column(String(30), nullable=True)
    is_system = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="pipeline_stages")
    leads = relationship(
        "Lead",
        back_populates="stage",
        primaryjoin="and_(Lead.stage_id == LeadPipelineStage.id, Lead.workspace_id == LeadPipelineStage.workspace_id)",
        foreign_keys="[Lead.stage_id, Lead.workspace_id]",
        overlaps="workspace,leads",
    )


class LeadAssignment(Base, TimestampMixin):
    """Team lead assignment record for Round-Robin distribution (Story 24.3 / INV-23.4)."""

    __tablename__ = "lead_assignments"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_assignments"),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_assignments_lead_id_workspace_id",
        ),
        Index("ix_lead_assignments_lookup", "workspace_id", "lead_id", "created_at"),
        Index(
            "ix_lead_assignments_user", "workspace_id", "assigned_to_user_id", "status"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    lead_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    assigned_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_by = Column(
        String(50),
        nullable=False,
        default="auto_round_robin",
        server_default="auto_round_robin",
    )
    status = Column(
        String(30), nullable=False, default="assigned", server_default="assigned"
    )
    reason = Column(String(255), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="lead_assignments")
    lead = relationship(
        "Lead",
        back_populates="assignments",
        primaryjoin="and_(LeadAssignment.lead_id == Lead.id, LeadAssignment.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,lead_assignments,assignments",
    )
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
    assigned_by_user = relationship("User", foreign_keys=[assigned_by_user_id])


class LeadActivityLog(Base, TimestampMixin):
    """Timeline interaction and audit logs for leads (Story 24.3 / INV-23.4)."""

    __tablename__ = "lead_activity_logs"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_lead_activity_logs"),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_activity_logs_lead_id_workspace_id",
        ),
        Index(
            "ix_lead_activity_logs_timeline", "workspace_id", "lead_id", "created_at"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    lead_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    activity_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    details = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="lead_activity_logs")
    lead = relationship(
        "Lead",
        back_populates="activity_logs",
        primaryjoin="and_(LeadActivityLog.lead_id == Lead.id, LeadActivityLog.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,lead_activity_logs,activity_logs",
    )
    actor = relationship("User", foreign_keys=[actor_user_id])


class LeadScore(Base, TimestampMixin):
    """Composite lead score snapshot (Story 21.2 / 23.4)."""

    __tablename__ = "lead_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    __table_args__ = (
        Index(
            "ix_lead_scores_workspace_lookup",
            "workspace_id",
            "client_id",
            "lead_id",
            "computed_at",
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_lead_scores_lead_id_workspace_id",
        ),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    previous_score_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lead_scores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_name = Column(String(200), nullable=False, index=True)
    score = Column(Float, nullable=False)
    fit_score = Column(Float, nullable=False)
    intent_score = Column(Float, nullable=False)
    classification = Column(String(10), nullable=False)
    factors_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    trend = Column(String(10), nullable=True)
    converted_similarity = Column(Float, nullable=True)
    computed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    workspace = relationship("Workspace", back_populates="lead_scores")
    lead = relationship(
        "Lead",
        back_populates="lead_scores",
        primaryjoin="and_(LeadScore.lead_id == Lead.id, LeadScore.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,lead_scores",
    )
    previous_score = relationship(
        "LeadScore",
        remote_side=[id],
        uselist=False,
    )


class EnrichmentRequest(Base, TimestampMixin):
    """A contact-enrichment request and its lifecycle (Story 21.3, AC-3 / 23.4).

    ``provider_results`` records the raw per-provider responses (redacted of
    PII) plus any degradation reasons; it is never surfaced on non-privileged
    UI surfaces (AD-25 / AD-49).
    """

    __tablename__ = "enrichment_requests"
    __table_args__ = (
        Index(
            "ix_enrichment_requests_tenant_lookup",
            "workspace_id",
            "client_id",
            "lead_id",
            text("created_at DESC"),
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_enrichment_requests_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        CITEXT,
        ForeignKey("vertical_clients.client_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    provider_results = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    contact_count = Column(Integer, nullable=False, default=0, server_default="0")
    requested_count = Column(Integer, nullable=False, default=5, server_default="5")

    workspace = relationship("Workspace", back_populates="enrichment_requests")
    lead = relationship(
        "Lead",
        back_populates="enrichment_requests",
        primaryjoin="and_(EnrichmentRequest.lead_id == Lead.id, EnrichmentRequest.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,enrichment_requests",
    )
    contacts = relationship(
        "VerifiedContact",
        back_populates="enrichment_request",
        cascade="all, delete-orphan",
    )


class VerifiedContact(Base, TimestampMixin):
    """A verified contact discovered by enrichment (Story 21.3, AC-3 / 23.4).

    Raw PII (name/title/email/phone) is encrypted at rest (AD-42/AD-49); this
    table is the authoritative source for outreach and is never passed through
    PII redaction.
    """

    __tablename__ = "verified_contacts"
    __table_args__ = (
        Index(
            "ix_verified_contacts_tenant_lookup",
            "workspace_id",
            "client_id",
            "lead_id",
            text("created_at DESC"),
        ),
        UniqueConstraint(
            "workspace_id",
            "value_hmac",
            name="uq_verified_contacts_workspace_hmac",
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_verified_contacts_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        CITEXT,
        ForeignKey("vertical_clients.client_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    enrichment_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enrichment_requests.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(200), nullable=True)
    title = Column(String(200), nullable=True)
    email = Column(CITEXT, nullable=True, index=True)
    phone = Column(String(200), nullable=True)
    verification_status = Column(
        String(20), nullable=False, default="unverified", server_default="unverified"
    )
    confidence = Column(Float, nullable=False, default=0.0, server_default="0")
    source_provider = Column(
        String(50), nullable=False, default="fallback", server_default="fallback"
    )
    consent = Column(Boolean, nullable=False, default=False, server_default="false")
    consent_status = Column(String(50), nullable=True)
    legal_basis = Column(String(50), nullable=True)
    value_hmac = Column(String(64), nullable=True, index=True)
    phone_hmac = Column(String(64), nullable=True, index=True)
    email_hmac = Column(String(64), nullable=True, index=True)
    is_valid = Column(Boolean, nullable=False, default=True, server_default="true")
    is_unlocked = Column(Boolean, nullable=False, default=False, server_default="false")
    pii_access_audit_logs = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    external_chat_ids = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    refunded_at = Column(TIMESTAMP(timezone=True), nullable=True)
    invalid_reason = Column(String(255), nullable=True)

    workspace = relationship("Workspace", back_populates="verified_contacts")
    lead = relationship(
        "Lead",
        back_populates="verified_contacts",
        primaryjoin="and_(VerifiedContact.lead_id == Lead.id, VerifiedContact.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,verified_contacts",
    )
    enrichment_request = relationship("EnrichmentRequest", back_populates="contacts")
    phone_waterfall_logs = relationship("PhoneWaterfallLog", back_populates="contact")


class PhoneWaterfallLog(Base, TimestampMixin):
    """Log entry for 3-tier phone resolution waterfall (Story 21.3 / 23.4 / AD-36).

    Tracks the exact tier, provider, response envelope, phone hash (SHA-256),
    masked phone, and refund SLA state without storing raw PII.
    """

    __tablename__ = "phone_waterfall_logs"
    __table_args__ = (
        Index(
            "ix_phone_waterfall_logs_tenant_lookup",
            "workspace_id",
            "client_id",
            "lead_id",
            text("created_at DESC"),
        ),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_phone_waterfall_logs_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        CITEXT,
        ForeignKey("vertical_clients.client_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("verified_contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tier_reached = Column(Integer, nullable=False, default=1, server_default="1")
    provider_used = Column(
        String(50), nullable=False, default="unknown", server_default="unknown"
    )
    status = Column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    phone_hash = Column(String(64), nullable=True, index=True)
    phone_masked = Column(String(50), nullable=True)
    raw_response = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    refunded_at = Column(TIMESTAMP(timezone=True), nullable=True)
    refund_reason = Column(String(255), nullable=True)

    workspace = relationship("Workspace")
    lead = relationship(
        "Lead",
        back_populates="phone_waterfall_logs",
        primaryjoin="and_(PhoneWaterfallLog.lead_id == Lead.id, PhoneWaterfallLog.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,phone_waterfall_logs",
    )
    contact = relationship("VerifiedContact", back_populates="phone_waterfall_logs")


class CrmConnection(Base, TimestampMixin):
    """CRM OAuth connection (Story 21.5)."""

    __tablename__ = "crm_connections"

    __table_args__ = (
        Index(
            "ix_crm_connections_workspace_lookup",
            "workspace_id",
            "client_id",
            "provider",
            "status",
        ),
        UniqueConstraint(
            "workspace_id",
            "client_id",
            "provider",
            name="uq_crm_connections_workspace_client_provider",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    credentials_encrypted = Column(Text, nullable=False)
    sync_config = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    last_sync_at = Column(TIMESTAMP(timezone=True), nullable=True)

    workspace = relationship("Workspace", back_populates="crm_connections")
    sync_logs = relationship(
        "CrmSyncLog",
        back_populates="connection",
        order_by="CrmSyncLog.synced_at.desc()",
        cascade="all, delete-orphan",
    )


class CrmSyncLog(Base, TimestampMixin):
    """CRM sync audit log (Story 21.5)."""

    __tablename__ = "crm_sync_logs"

    __table_args__ = (
        Index(
            "ix_crm_sync_logs_workspace_lookup",
            "workspace_id",
            "client_id",
            "connection_id",
            "synced_at",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crm_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction = Column(String(20), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)
    synced_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    workspace = relationship("Workspace", back_populates="crm_sync_logs")
    connection = relationship("CrmConnection", back_populates="sync_logs")


class LinkedinCompany(Base, TimestampMixin):
    """A company ingested from LinkedIn Guest Jobs/Pages (Story 21.9 / AD-LI-1 / AD-LI-5)."""

    __tablename__ = "linkedin_companies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_slug = Column(String(255), nullable=False, unique=True, index=True)
    company_name = Column(Text, nullable=False, index=True)
    website = Column(Text, nullable=True)
    industry = Column(String(255), nullable=True)
    headcount_range = Column(String(50), nullable=True)
    headquarters = Column(String(255), nullable=True)
    active_jobs_count = Column(Integer, nullable=False, default=0, server_default="0")
    decision_makers = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    jobs = relationship(
        "LinkedinJob",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    decision_maker_records = relationship(
        "CompanyDecisionMaker",
        back_populates="company",
        cascade="all, delete-orphan",
    )


class LinkedinJob(Base, TimestampMixin):
    """A job posting ingested from LinkedIn Public Guest API (Story 21.9 / AD-LI-1 / AD-LI-5)."""

    __tablename__ = "linkedin_jobs"

    __table_args__ = (
        Index("idx_li_jobs_company_name", "company_name"),
        Index("idx_li_jobs_posted", "posted_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, unique=True, index=True)
    company_id = Column(
        BigInteger,
        ForeignKey("linkedin_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_name = Column(String(255), nullable=False, index=True)
    title = Column(Text, nullable=False)
    location = Column(String(255), nullable=True)
    workplace_type = Column(String(50), nullable=True)
    seniority_level = Column(String(50), nullable=True)
    employment_type = Column(String(50), nullable=True)
    description_text = Column(Text, nullable=True)
    skills = Column(ARRAY(String), nullable=True, default=list)
    posted_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    raw_entities = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    company = relationship("LinkedinCompany", back_populates="jobs")


class CompanyDecisionMaker(Base, TimestampMixin):
    """Executive decision-maker mapped for B2B outreach (Story 21.9 / AD-LI-4 / AD-LI-5)."""

    __tablename__ = "company_decision_makers"

    __table_args__ = (
        UniqueConstraint("company_id", "linkedin_slug", name="uq_company_executive"),
        Index("idx_executives_company_title", "company_name", "title"),
        Index("idx_executives_slug", "linkedin_slug"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        BigInteger,
        ForeignKey("linkedin_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    company_name = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    title = Column(Text, nullable=True)
    department = Column(String(100), nullable=True, default="Executive Leadership")
    linkedin_url = Column(Text, nullable=False)
    linkedin_slug = Column(String(255), nullable=False, index=True)
    corporate_email = Column(String(255), nullable=True, index=True)
    email_confidence = Column(Float, nullable=False, default=0.7)
    verified_mx = Column(Boolean, nullable=False, default=False)
    source_platform = Column(String(50), nullable=False, default="linkedin_guest")
    raw_entities = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    confidence_score = Column(Float, nullable=False, default=0.0, server_default="0")
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)

    company = relationship("LinkedinCompany", back_populates="decision_maker_records")


class SocialMonitoredTarget(Base, TimestampMixin):
    """Monitored social groups, pages, or search terms (Story 21.8 / AD-SOC-1 to AD-SOC-7)."""

    __tablename__ = "social_monitored_targets"

    __table_args__ = (
        UniqueConstraint("platform", "target_id", name="uq_social_target"),
        Index("idx_social_targets_platform", "platform"),
        Index("idx_social_targets_active", "is_active"),
        Index("idx_social_targets_workspace_id", "workspace_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform = Column(
        String(50), nullable=False
    )  # 'facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'
    target_id = Column(String(255), nullable=False)
    target_name = Column(Text, nullable=False)
    target_url = Column(Text, nullable=True)
    category = Column(
        String(50), nullable=False, default="general", server_default=text("'general'")
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    realtime_stream = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # scrape_interval_minutes is the canonical scrape/poll cadence. The legacy
    # poll_interval_seconds concept maps to scrape_interval_minutes * 60.
    scrape_interval_minutes = Column(
        Integer, nullable=False, default=15, server_default="15"
    )
    status = Column(
        String(50), nullable=False, default="active", server_default=text("'active'")
    )
    last_polled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_scraped_at = Column(TIMESTAMP(timezone=True), nullable=True)
    proxy_url = Column(Text, nullable=True)

    workspace = relationship("Workspace", back_populates="social_monitored_targets")
    posts = relationship(
        "SocialPost",
        back_populates="target",
        cascade="all, delete-orphan",
    )


class SocialPost(Base, TimestampMixin):
    """Ingested social post from Facebook or Twitter (Story 21.8 / AD-SOC-1 to AD-SOC-7)."""

    __tablename__ = "social_posts"

    __table_args__ = (
        UniqueConstraint("platform", "external_post_id", name="uq_social_post"),
        Index("idx_social_posts_platform_ext", "platform", "external_post_id"),
        Index("idx_social_posts_published", "published_at"),
        Index("idx_social_posts_intent", "intent_tag"),
        Index(
            "idx_social_posts_platform_intent_published",
            "platform",
            "intent_tag",
            "published_at",
        ),
        Index("idx_social_posts_gin_entities", "raw_entities", postgresql_using="gin"),
        Index(
            "idx_social_posts_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("embedding IS NOT NULL"),
        ),
        Index("idx_social_posts_workspace_id", "workspace_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id = Column(
        BigInteger,
        ForeignKey("social_monitored_targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(String(50), nullable=False)  # 'facebook', 'twitter'
    external_post_id = Column(String(255), nullable=False)
    author_name = Column(Text, nullable=True)
    author_id = Column(String(255), nullable=True)
    author_url = Column(Text, nullable=True)
    post_url = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    intent_tag = Column(
        String(50), nullable=True
    )  # 'sell', 'buy', 'hiring', 'seeking', 'news', 'other'
    fit_score = Column(Float, nullable=False, default=0.0, server_default="0")
    reactions_count = Column(Integer, nullable=False, default=0, server_default="0")
    comments_count = Column(Integer, nullable=False, default=0, server_default="0")
    shares_count = Column(Integer, nullable=False, default=0, server_default="0")
    raw_entities = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    media_urls = Column(ARRAY(Text), nullable=True)
    embedding = Column(Vector(config.embedding_model_instance.dimension), nullable=True)
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
        index=True,
    )

    workspace = relationship("Workspace", back_populates="social_posts")
    target = relationship("SocialMonitoredTarget", back_populates="posts")


class ZaloConnection(Base, TimestampMixin):
    """Zalo Official Account connection for a workspace (Story 21.6 / AD-41)."""

    __tablename__ = "zalo_connections"

    __table_args__ = (
        UniqueConstraint("workspace_id", "oa_id", name="uq_workspace_zalo_oa"),
        Index("idx_zalo_connections_workspace_id", "workspace_id"),
        Index("idx_zalo_connections_oa_id", "oa_id"),
        Index("idx_zalo_connections_active", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    oa_id = Column(String(100), nullable=False)
    oa_name = Column(String(255), nullable=True)
    app_id = Column(String(100), nullable=True)
    app_secret_encrypted = Column(Text, nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    webhook_secret = Column(String(255), nullable=True)
    settings = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
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

    workspace = relationship("Workspace", back_populates="zalo_connections")
    message_logs = relationship(
        "ZaloMessageLog",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class ZaloMessageLog(Base, TimestampMixin):
    """Audit log of Zalo outreach drafts, ZNS messages, and inbound replies (Story 21.6 / 23.4)."""

    __tablename__ = "zalo_message_logs"

    __table_args__ = (
        Index("idx_zalo_message_logs_workspace_id", "workspace_id"),
        Index("idx_zalo_message_logs_lead_id", "lead_id"),
        Index("idx_zalo_message_logs_phone", "recipient_phone"),
        Index("idx_zalo_message_logs_created_at", "created_at"),
        Index("idx_zalo_message_logs_msg_type", "message_type"),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="SET NULL",
            name="fk_zalo_message_logs_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    zalo_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("zalo_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    recipient_phone = Column(String(50), nullable=True)
    recipient_zalo_id = Column(String(100), nullable=True)
    message_type = Column(
        String(50), nullable=False, default="assisted_draft"
    )  # 'assisted_draft', 'zns', 'oa_chat', 'webhook_inbound'
    template_id = Column(String(100), nullable=True)
    template_data = Column(
        JSONB, nullable=True, default=dict, server_default=text("'{}'::jsonb")
    )
    content = Column(Text, nullable=False)
    status = Column(
        String(50), nullable=False, default="generated"
    )  # 'generated', 'sent', 'delivered', 'failed', 'received'
    external_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
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

    workspace = relationship("Workspace", back_populates="zalo_message_logs")
    connection = relationship("ZaloConnection", back_populates="message_logs")
    lead = relationship(
        "Lead",
        back_populates="zalo_message_logs",
        primaryjoin="and_(ZaloMessageLog.lead_id == Lead.id, ZaloMessageLog.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,zalo_message_logs",
    )


class OutcomeEvent(Base, TimestampMixin):
    """An outcome event (e.g. meeting booked, verified lead outcome) for outcome-based pricing (Story 21.7 / 23.4 / AD-42)."""

    __tablename__ = "outcome_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_outcome_events_lead_id_workspace_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    event_type = Column(
        String(50), nullable=False, index=True
    )  # outcome_meeting_booked, outcome_lead_enriched
    lead_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    sequence_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    attribution = Column(
        String(100), nullable=False, default="direct", server_default="direct"
    )
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    outcome_metadata = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    workspace = relationship("Workspace")
    lead = relationship(
        "Lead",
        back_populates="outcome_events",
        primaryjoin="and_(OutcomeEvent.lead_id == Lead.id, OutcomeEvent.workspace_id == Lead.workspace_id)",
        foreign_keys=[lead_id, workspace_id],
        overlaps="workspace,outcome_events",
    )


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
