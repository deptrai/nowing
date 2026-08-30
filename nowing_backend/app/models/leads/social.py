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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import relationship

from app.config import config
from app.db.base import Base, TimestampMixin


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


__all__ = ["OutcomeEvent", "SocialMonitoredTarget", "SocialPost", "ZaloConnection", "ZaloMessageLog"]
