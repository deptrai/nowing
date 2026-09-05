"""Models for the workspaces domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, BaseModel, TimestampMixin
from app.db.enums import DocumentRetentionAction


class Workspace(BaseModel, TimestampMixin):
    __tablename__ = "workspaces"

    __table_args__ = (
        CheckConstraint(
            "NOT auto_archive_enabled OR ("
            "document_retention_days IS NOT NULL AND "
            "document_retention_days > 0 AND "
            "document_retention_days <= 36500"
            ")",
            name="ck_workspace_retention_invariant",
        ),
        CheckConstraint(
            "NOT memory_auto_archive_enabled OR ("
            "memory_retention_days IS NOT NULL AND "
            "memory_retention_days > 0 AND "
            "memory_retention_days <= 36500"
            ")",
            name="ck_workspace_memory_retention_invariant",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    vertical = Column(
        String(64),
        nullable=False,
        default="general",
        server_default="general",
        index=True,
    )

    plan_tier = Column(
        String(20),
        nullable=False,
        default="free",
        server_default="free",
        index=True,
    )

    credit_micros_balance = Column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    citations_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Enable/disable citations
    api_access_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    web_builder_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    presentation_studio_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    qna_custom_instructions = Column(
        Text, nullable=True, default=""
    )  # User's custom instructions

    # Connection/model role bindings.
    # Note: ID values preserve the existing convention:
    #   - 0: Auto mode
    #   - Negative IDs: Global virtual models from global_llm_config.yaml
    #   - Positive IDs: User/workspace models from the models table
    chat_model_id = Column(
        Integer, nullable=True, default=0, server_default="0"
    )  # For agent/chat operations, defaults to Auto mode
    image_gen_model_id = Column(
        Integer, nullable=True, default=0, server_default="0"
    )  # For image generation, defaults to Auto mode when eligible
    vision_model_id = Column(
        Integer, nullable=True, default=0, server_default="0"
    )  # For vision/screenshot analysis, defaults to Auto mode

    # First time this workspace went ready via its own model (source=="models").
    # NULL = never self-configured. Set once, never cleared; splits a needs_setup
    # verdict into first-run vs. recovery.
    llm_setup_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Data retention / lifecycle settings.
    document_retention_days = Column(Integer, nullable=True)
    auto_archive_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    document_retention_action = Column(
        String(20),
        nullable=False,
        default=DocumentRetentionAction.ARCHIVE,
        server_default="archive",
    )
    memory_retention_days = Column(Integer, nullable=True)
    memory_auto_archive_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    memory_retention_action = Column(
        String(20),
        nullable=False,
        default=DocumentRetentionAction.ARCHIVE,
        server_default="archive",
    )

    memory_auto_extract_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Epic 21 lead scoring ICP criteria (Story 21.2).
    icp_criteria = Column(JSONB, nullable=True)

    # Story 24.6: Two-Way AI Outreach Auto-Reply Agent workspace settings.
    auto_reply_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    auto_reply_collections = Column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    auto_reply_fallback = Column(Text, nullable=True)
    auto_reply_recipient_chat_id = Column(String(255), nullable=True)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    user = relationship("User", back_populates="workspaces")

    folders = relationship(
        "Folder",
        back_populates="workspace",
        order_by="Folder.position",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document",
        back_populates="workspace",
        order_by="Document.id",
        cascade="all, delete-orphan",
    )
    new_chat_threads = relationship(
        "NewChatThread",
        back_populates="workspace",
        order_by="NewChatThread.updated_at.desc()",
        cascade="all, delete-orphan",
    )
    podcasts = relationship(
        "Podcast",
        back_populates="workspace",
        order_by="Podcast.id.desc()",
        cascade="all, delete-orphan",
    )
    video_presentations = relationship(
        "VideoPresentation",
        back_populates="workspace",
        order_by="VideoPresentation.id.desc()",
        cascade="all, delete-orphan",
    )
    meeting_minutes = relationship(
        "MeetingMinutes",
        back_populates="workspace",
        order_by="MeetingMinutes.id.desc()",
        cascade="all, delete-orphan",
    )
    reports = relationship(
        "Report",
        back_populates="workspace",
        order_by="Report.id.desc()",
        cascade="all, delete-orphan",
    )
    image_generations = relationship(
        "ImageGeneration",
        back_populates="workspace",
        order_by="ImageGeneration.id.desc()",
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "Log",
        back_populates="workspace",
        order_by="Log.id",
        cascade="all, delete-orphan",
    )
    notifications = relationship(
        "Notification",
        back_populates="workspace",
        order_by="Notification.created_at.desc()",
        cascade="all, delete-orphan",
    )
    search_source_connectors = relationship(
        "SearchSourceConnector",
        back_populates="workspace",
        order_by="SearchSourceConnector.id",
        cascade="all, delete-orphan",
    )
    connections = relationship(
        "Connection",
        back_populates="workspace",
        order_by="Connection.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    automations = relationship(
        "Automation",
        back_populates="workspace",
        order_by="Automation.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    playbooks = relationship(
        "Playbook",
        back_populates="workspace",
        order_by="Playbook.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # RBAC relationships
    roles = relationship(
        "WorkspaceRole",
        back_populates="workspace",
        order_by="WorkspaceRole.id",
        cascade="all, delete-orphan",
    )
    memberships = relationship(
        "WorkspaceMembership",
        back_populates="workspace",
        order_by="WorkspaceMembership.id",
        cascade="all, delete-orphan",
    )
    invites = relationship(
        "WorkspaceInvite",
        back_populates="workspace",
        order_by="WorkspaceInvite.id",
        cascade="all, delete-orphan",
    )
    mcp_tool_settings = relationship(
        "WorkspaceMcpToolSetting",
        back_populates="workspace",
        order_by="WorkspaceMcpToolSetting.tool_name",
        cascade="all, delete-orphan",
    )
    research_threads = relationship(
        "ResearchThread",
        back_populates="workspace",
        order_by="ResearchThread.created_at.desc()",
        cascade="all, delete-orphan",
    )
    memories = relationship(
        "Memory",
        back_populates="workspace",
        order_by="Memory.created_at.desc()",
        cascade="all, delete-orphan",
    )
    memory_relations = relationship(
        "MemoryRelation",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    workspace_limits = relationship(
        "WorkspaceLimit",
        back_populates="workspace",
        cascade="all, delete-orphan",
        uselist=False,
    )
    projects = relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="Project.created_at.desc()",
    )
    skills = relationship(
        "WorkspaceSkill",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="WorkspaceSkill.created_at.desc()",
    )
    leads = relationship(
        "Lead",
        back_populates="workspace",
        order_by="Lead.created_at.desc()",
        cascade="all, delete-orphan",
    )
    pipeline_stages = relationship(
        "LeadPipelineStage",
        back_populates="workspace",
        order_by="LeadPipelineStage.position",
        cascade="all, delete-orphan",
    )
    lead_assignments = relationship(
        "LeadAssignment",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    lead_activity_logs = relationship(
        "LeadActivityLog",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    lead_scores = relationship(
        "LeadScore",
        back_populates="workspace",
        order_by="LeadScore.computed_at.desc()",
        cascade="all, delete-orphan",
    )
    enrichment_requests = relationship(
        "EnrichmentRequest",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    verified_contacts = relationship(
        "VerifiedContact",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    chainlens_chunks = relationship(
        "ChainLensChunk",
        back_populates="workspace",
        order_by="ChainLensChunk.created_at.desc()",
        cascade="all, delete-orphan",
    )
    chainlens_ingest_jobs = relationship(
        "ChainLensIngestJob",
        back_populates="workspace",
        order_by="ChainLensIngestJob.created_at.desc()",
        cascade="all, delete-orphan",
    )
    crm_connections = relationship(
        "CrmConnection",
        back_populates="workspace",
        order_by="CrmConnection.created_at.desc()",
        cascade="all, delete-orphan",
    )
    crm_sync_logs = relationship(
        "CrmSyncLog",
        back_populates="workspace",
        order_by="CrmSyncLog.synced_at.desc()",
        cascade="all, delete-orphan",
    )
    social_monitored_targets = relationship(
        "SocialMonitoredTarget",
        back_populates="workspace",
        order_by="SocialMonitoredTarget.id",
        cascade="all, delete-orphan",
    )
    social_posts = relationship(
        "SocialPost",
        back_populates="workspace",
        order_by="SocialPost.id",
        cascade="all, delete-orphan",
    )
    zalo_connections = relationship(
        "ZaloConnection",
        back_populates="workspace",
        order_by="ZaloConnection.created_at.desc()",
        cascade="all, delete-orphan",
    )
    zalo_message_logs = relationship(
        "ZaloMessageLog",
        back_populates="workspace",
        order_by="ZaloMessageLog.created_at.desc()",
        cascade="all, delete-orphan",
    )


class WorkspaceMcpToolSetting(BaseModel, TimestampMixin):
    __tablename__ = "workspace_mcp_tool_settings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "tool_name",
            name="uq_workspace_mcp_tool",
        ),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(120), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")

    workspace = relationship("Workspace", back_populates="mcp_tool_settings")


class WorkspaceLimit(BaseModel, TimestampMixin):
    """
    Plan-default or per-workspace override limits.

    * ``plan_tier`` is set and ``workspace_id`` is NULL for plan defaults.
    * ``workspace_id`` is set and ``plan_tier`` is NULL for workspace overrides.
    * Partial unique indexes in migration 189 enforce one default per plan and
      one override per workspace.
    """

    __tablename__ = "workspace_limits"
    __table_args__ = (
        CheckConstraint(
            "(plan_tier IS NOT NULL) OR (workspace_id IS NOT NULL)",
            name="ck_workspace_limits_plan_or_workspace",
        ),
    )

    plan_tier = Column(String(20), nullable=True, index=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    max_documents = Column(Integer, nullable=True)
    max_members = Column(Integer, nullable=True)
    max_runs = Column(Integer, nullable=True)
    max_storage_bytes = Column(BigInteger, nullable=True)
    max_memory_count = Column(Integer, nullable=True)
    max_memory_bytes = Column(BigInteger, nullable=True)
    run_period_hours = Column(
        Integer,
        nullable=False,
        default=720,
        server_default="720",
    )

    # Story 8.14: per-workspace auto-extract budget caps.
    auto_extract_item_cap = Column(Integer, nullable=True)
    auto_extract_spend_cap_micros = Column(BigInteger, nullable=True)
    auto_extract_wallet_pre_check = Column(Boolean, nullable=True)

    # Story 14.2a: per-workspace news entity extraction caps.
    news_entity_extraction_item_cap = Column(Integer, nullable=True)
    news_entity_extraction_spend_cap_micros = Column(BigInteger, nullable=True)
    news_entity_extraction_wallet_pre_check = Column(Boolean, nullable=True)

    workspace = relationship(
        "Workspace", back_populates="workspace_limits", uselist=False
    )


class ResearchThread(BaseModel, TimestampMixin):
    """Container for a chain of related chat sessions that share memory."""

    __tablename__ = "research_threads"
    __table_args__ = (
        Index(
            "ix_research_threads_workspace_id_client_id",
            "workspace_id",
            "client_id",
        ),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(500), nullable=True)
    client_id = Column(Text, nullable=True, index=True)
    current_chat_thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="research_threads")
    created_by = relationship("User", back_populates="research_threads")
    current_chat_thread = relationship(
        "NewChatThread",
        foreign_keys=[current_chat_thread_id],
        uselist=False,
    )
    new_chat_threads = relationship(
        "NewChatThread",
        back_populates="research_thread",
        foreign_keys="NewChatThread.research_thread_id",
    )
    memories = relationship(
        "Memory",
        back_populates="research_thread",
        cascade="all, delete-orphan",
    )


class VerticalClient(Base, TimestampMixin):
    """Registered vertical client / partner tenant (e.g. BDS AI)."""

    __tablename__ = "vertical_clients"
    __table_args__ = (
        UniqueConstraint("client_id", name="unique_vertical_clients_client_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(CITEXT, nullable=False, unique=True)
    display_name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class WorkspaceTable(Base, TimestampMixin):
    """Saved lead table view with filter preset and column config (Story 21.13)."""

    __tablename__ = "workspace_tables"
    __table_args__ = (
        Index("ix_workspace_tables_workspace_created", "workspace_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    icon = Column(
        String(50), nullable=False, default="table", server_default=text("'table'")
    )
    filter_preset = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    columns_config = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    workspace = relationship("Workspace")
    leads = relationship("Lead", back_populates="table")


class WorkspaceDncRecord(Base, TimestampMixin):
    """Do-Not-Call (DNC) / Exclusion registry record (Story 21.14 / AD-43)."""

    __tablename__ = "workspace_dnc_records"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "record_type", "value_hmac", name="uq_workspace_dnc_entry"
        ),
        Index("ix_workspace_dnc_records_workspace_type", "workspace_id", "record_type"),
        Index("ix_workspace_dnc_records_hmac", "workspace_id", "value_hmac"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_type = Column(
        String(20), nullable=False
    )  # 'phone', 'domain', 'email', 'tax_id'
    value = Column(String(255), nullable=True)  # Masked/raw display value
    value_hmac = Column(String(64), nullable=False, index=True)
    reason = Column(
        String(255),
        nullable=True,
        default="Opt-out requested",
        server_default=text("'Opt-out requested'"),
    )
    source = Column(
        String(50), nullable=False, default="manual", server_default=text("'manual'")
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

    workspace = relationship("Workspace")


class GlobalDncRecord(Base, TimestampMixin):
    """Global Do-Not-Call (DNC) / Exclusion registry record.

    ponytail: platform-wide blacklist that applies across all workspaces.
    """

    __tablename__ = "global_dnc_records"
    __table_args__ = (
        UniqueConstraint("record_type", "value_hmac", name="uq_global_dnc_entry"),
        Index("ix_global_dnc_records_type", "record_type"),
        Index("ix_global_dnc_records_hmac", "value_hmac"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_type = Column(
        String(20), nullable=False
    )  # 'phone', 'domain', 'email', 'tax_id'
    value = Column(String(255), nullable=True)  # Masked/raw display value
    value_hmac = Column(String(64), nullable=False, index=True)
    reason = Column(
        String(255),
        nullable=True,
        default="Opt-out requested",
        server_default=text("'Opt-out requested'"),
    )
    source = Column(
        String(50), nullable=False, default="manual", server_default=text("'manual'")
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


class WorkspaceApp(Base):
    """Full-stack web application generated and deployed for a workspace (Story 27.1 / AD-113 / AD-114)."""

    __tablename__ = "workspace_apps"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", name="uq_workspace_apps_workspace_slug"
        ),
        Index("ix_workspace_apps_workspace_status", "workspace_id", "status"),
        Index("ix_workspace_apps_custom_domain", "custom_domain"),
        # Globally unique active custom domain so CNAME bindings cannot collide
        # across workspaces (Story 27.1c AC-2). Partial so unset/failed rows are
        # excluded and multiple NULLs remain allowed.
        Index(
            "uq_workspace_apps_active_custom_domain",
            "custom_domain",
            unique=True,
            postgresql_where=text("custom_domain_status = 'active'"),
        ),
        # Globally unique published slug so public URLs cannot collide across
        # workspaces (Story 27.1a AC-4).
        Index(
            "ix_workspace_apps_published_slug",
            "slug",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    # 63 chars is the DNS label limit for *.apps.nowing.net subdomains.
    slug = Column(String(63), nullable=False, index=True)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    language = Column(
        String(10), nullable=False, default="en", server_default=text("'en'")
    )
    status = Column(
        String(50),
        nullable=False,
        default="generated",
        server_default=text("'generated'"),
    )  # generated, building, preview_ready, build_failed, published, deploy_failed, error
    preview_url = Column(String(512), nullable=True)
    public_url = Column(String(512), nullable=True)
    custom_domain = Column(String(255), nullable=True)
    custom_domain_status = Column(
        String(50), nullable=True
    )  # pending_verification, active, failed
    storage_path = Column(String(512), nullable=True)
    container_id = Column(String(100), nullable=True)
    port = Column(Integer, nullable=True)
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

    workspace = relationship("Workspace", backref="apps")
    user = relationship("User", backref="apps")


class BroadcastAnnouncement(Base):
    """In-app broadcast announcements for system alerts, maintenance, and promotions (Story 25.6)."""

    __tablename__ = "broadcast_announcements"
    __table_args__ = (
        Index(
            "ix_broadcast_announcements_active_window",
            "is_active",
            "starts_at",
            "expires_at",
        ),
        Index(
            "ix_broadcast_announcements_target_workspace_ids",
            "target_workspace_ids",
            postgresql_using="gin",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    banner_type = Column(
        String(20), nullable=False, default="info", server_default=text("'info'")
    )
    target_all = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    target_workspace_ids = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    starts_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    dismissible = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
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

    created_by_user = relationship(
        "User", foreign_keys=[created_by_user_id], backref="created_broadcasts"
    )
    updated_by_user = relationship(
        "User", foreign_keys=[updated_by_user_id], backref="updated_broadcasts"
    )
