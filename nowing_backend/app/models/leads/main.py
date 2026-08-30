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

from app.db.base import Base, TimestampMixin


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


__all__ = ["ExportJob", "Lead", "LeadActivityLog", "LeadAssignment", "LeadPipelineStage", "LeadScore"]
