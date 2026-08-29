"""Models for the connectors domain."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, TimestampMixin
from app.db.enums import ConnectionScope, LogLevel, LogStatus, SearchSourceConnectorType


class Connection(BaseModel, TimestampMixin):
    __tablename__ = "connections"

    provider = Column(String(100), nullable=False, index=True)
    base_url = Column(String(500), nullable=True)
    api_key = Column(String, nullable=True)
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")
    scope = Column(SQLAlchemyEnum(ConnectionScope), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=True
    )

    workspace = relationship("Workspace", back_populates="connections")
    user = relationship("User", back_populates="connections")
    models = relationship(
        "Model",
        back_populates="connection",
        order_by="Model.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "(scope = 'GLOBAL' AND workspace_id IS NULL AND user_id IS NULL) OR "
            "(scope = 'SEARCH_SPACE' AND workspace_id IS NOT NULL AND user_id IS NOT NULL) OR "
            "(scope = 'USER' AND user_id IS NOT NULL)",
            name="ck_connections_scope_owner",
        ),
    )


class SearchSourceConnector(BaseModel, TimestampMixin):
    __tablename__ = "search_source_connectors"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "connector_type",
            "name",
            name="uq_workspace_user_connector_type_name",
        ),
        # Mirrors migration 129; backs the ``/obsidian/connect`` upsert.
        Index(
            "search_source_connectors_obsidian_plugin_vault_uniq",
            "user_id",
            text("(config->>'vault_id')"),
            unique=True,
            postgresql_where=text(
                "connector_type = 'OBSIDIAN_CONNECTOR' "
                "AND config->>'source' = 'plugin' "
                "AND config->>'vault_id' IS NOT NULL"
            ),
        ),
        # Cross-device dedup: same vault content from different devices
        # cannot produce two connector rows.
        Index(
            "search_source_connectors_obsidian_plugin_fingerprint_uniq",
            "user_id",
            text("(config->>'vault_fingerprint')"),
            unique=True,
            postgresql_where=text(
                "connector_type = 'OBSIDIAN_CONNECTOR' "
                "AND config->>'source' = 'plugin' "
                "AND config->>'vault_fingerprint' IS NOT NULL"
            ),
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    connector_type = Column(SQLAlchemyEnum(SearchSourceConnectorType), nullable=False)
    is_indexable = Column(Boolean, nullable=False, default=False)
    last_indexed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    config = Column(JSON, nullable=False)

    # Vision LLM for image files - disabled by default to save cost/time.
    # When enabled, images are described via a vision language model instead
    # of falling back to the document parser.
    enable_vision_llm = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Periodic indexing fields
    periodic_indexing_enabled = Column(Boolean, nullable=False, default=False)
    indexing_frequency_minutes = Column(Integer, nullable=True)
    next_scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="search_source_connectors")

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    user = relationship("User", back_populates="search_source_connectors")

    # Documents created by this connector (for cleanup on connector deletion)
    documents = relationship("Document", back_populates="connector")


class Log(BaseModel, TimestampMixin):
    __tablename__ = "logs"

    level = Column(SQLAlchemyEnum(LogLevel), nullable=False, index=True)
    status = Column(SQLAlchemyEnum(LogStatus), nullable=False, index=True)
    message = Column(Text, nullable=False)
    source = Column(
        String(200), nullable=True, index=True
    )  # Service/component that generated the log
    log_metadata = Column(JSON, nullable=True, default={})  # Additional context data

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="logs")
