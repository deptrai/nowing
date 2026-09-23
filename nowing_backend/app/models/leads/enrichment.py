"""Models for the leads domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


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


__all__ = ["CompanyDecisionMaker", "CrmConnection", "CrmSyncLog", "EnrichmentRequest", "LinkedinCompany", "LinkedinJob", "PhoneWaterfallLog", "VerifiedContact"]
