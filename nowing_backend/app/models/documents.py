"""Models for the documents domain."""

from __future__ import annotations

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import backref, relationship

from app.config import config
from app.db.base import BaseModel, TimestampMixin
from app.db.enums import DocumentStatus, DocumentType


class Folder(BaseModel, TimestampMixin):
    __tablename__ = "folders"

    name = Column(String(255), nullable=False, index=True)
    position = Column(String(50), nullable=False, index=True)
    parent_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )
    folder_metadata = Column("metadata", JSONB, nullable=True)

    parent = relationship("Folder", remote_side="Folder.id", backref="children")
    workspace = relationship("Workspace", back_populates="folders")
    created_by = relationship("User", back_populates="folders")
    documents = relationship("Document", back_populates="folder", passive_deletes=True)


class Document(BaseModel, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_archived_at_workspace_id", "archived_at", "workspace_id"),
    )

    title = Column(String, nullable=False, index=True)
    document_type = Column(SQLAlchemyEnum(DocumentType), nullable=False)
    document_metadata = Column(JSON, nullable=True)

    content = Column(Text, nullable=False)
    # ``content_hash`` is intentionally NOT globally unique. In a real
    # filesystem two files at different paths can hold identical bytes,
    # and the agent's ``write_file`` flow needs that semantic to support
    # copy / duplicate operations. Path uniqueness lives on
    # ``unique_identifier_hash`` (per workspace). The hash remains
    # indexed because connector indexers consult it as a change-detection
    # / cross-source dedup hint via :func:`check_duplicate_document`.
    # See migration 133.
    content_hash = Column(String, nullable=False, index=True)
    unique_identifier_hash = Column(String, nullable=True, index=True, unique=True)
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    # BlockNote live editing state (NULL when never edited)
    # DEPRECATED: Will be removed in a future migration. Use source_markdown instead.
    blocknote_document = Column(JSONB, nullable=True)

    # Full raw markdown content for the Plate.js editor.
    # This is the source of truth for document content in the editor.
    # Populated from markdown at ingestion time, or from blocknote_document migration.
    source_markdown = Column(Text, nullable=True)

    # Background reindex flag (set when editor content is saved)
    content_needs_reindexing = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Track when document was last updated by indexers, processors, or editor
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Soft-archive timestamp; non-NULL documents are excluded from search/lists.
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Track who created/uploaded this document
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for backward compatibility with existing records
        index=True,
    )

    # Track which connector created this document (for cleanup on connector deletion)
    connector_id = Column(
        Integer,
        ForeignKey("search_source_connectors.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for manually uploaded docs without connector
        index=True,
    )

    # Processing status for real-time visibility (JSONB)
    # Format: {"state": "ready"} or {"state": "processing"} or {"state": "failed", "reason": "..."}
    # Default to {"state": "ready"} for backward compatibility with existing documents
    status = Column(
        JSONB,
        nullable=False,
        default=DocumentStatus.ready,
        server_default=text('\'{"state": "ready"}\'::jsonb'),
        index=True,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    created_by = relationship("User", back_populates="documents")
    connector = relationship("SearchSourceConnector", back_populates="documents")
    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.position",
    )
    # Original upload + future derived artifacts (redacted, filled-form).
    # Model lives in app.file_storage.persistence to keep that feature cohesive.
    files = relationship(
        "DocumentFile", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(BaseModel, TimestampMixin):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    source_markdown = Column(Text, nullable=True)
    content_hash = Column(String, nullable=False)
    title = Column(String, nullable=True)

    document = relationship(
        "Document", backref=backref("versions", passive_deletes=True)
    )


class Chunk(BaseModel, TimestampMixin):
    __tablename__ = "chunks"

    content = Column(Text, nullable=False)
    embedding = Column(Vector(config.embedding_model_instance.dimension))
    # Explicit document order; ids don't follow it since incremental
    # re-indexing keeps unchanged rows across edits. Deliberately not indexed:
    # ordering reads are document-scoped (covered by ix_chunks_document_id) and
    # building a position index on the large chunks table is not worth it.
    position = Column(Integer, nullable=False, server_default="0")

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document = relationship("Document", back_populates="chunks")


class ChainLensChunk(BaseModel, TimestampMixin):
    """A chunk ingested from chainlens-research into Nowing (Story 26.1 / AC-3)."""

    __tablename__ = "chainlens_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("id", "workspace_id", name="pk_chainlens_chunks"),
        Index(
            "ix_chainlens_chunks_workspace_source",
            "workspace_id",
            "source_url",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    source_url = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(
        Vector(1536),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False, server_default="0")

    workspace = relationship("Workspace", back_populates="chainlens_chunks")


class DocumentRevision(BaseModel):
    """Snapshot of a :class:`Document` row taken before a mutating tool call.

    Written by :class:`KnowledgeBasePersistenceMiddleware` (or its safety-net
    `commit_staged_filesystem_state`) ahead of any NOTE / FILE / EXTENSION
    document write. The row is referenced by ``/revert/{action_id}`` to
    restore the original content in place.
    """

    __tablename__ = "document_revisions"

    # ``ON DELETE SET NULL`` (not CASCADE) so the snapshot survives the
    # hard-delete it describes — without that, ``rm`` would wipe the row
    # we'd need to undo it. See migration ``134_relax_revision_fks``.
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_before = Column(Text, nullable=True)
    title_before = Column(String, nullable=True)
    folder_id_before = Column(Integer, nullable=True)
    chunks_before = Column(JSONB, nullable=True)
    metadata_before = Column("metadata_before", JSONB, nullable=True)
    created_by_turn_id = Column(String(64), nullable=True, index=True)
    agent_action_id = Column(
        Integer,
        ForeignKey("agent_action_log.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
        index=True,
    )


class FolderRevision(BaseModel):
    """Snapshot of a :class:`Folder` row taken before a mkdir / move."""

    __tablename__ = "folder_revisions"

    # ``ON DELETE SET NULL`` (not CASCADE) so the snapshot survives the
    # hard-delete it describes — without that, ``rmdir`` would wipe the
    # row we'd need to undo it. See migration ``134_relax_revision_fks``.
    folder_id = Column(
        Integer,
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name_before = Column(String(255), nullable=True)
    parent_id_before = Column(Integer, nullable=True)
    position_before = Column(String(50), nullable=True)
    created_by_turn_id = Column(String(64), nullable=True, index=True)
    agent_action_id = Column(
        Integer,
        ForeignKey("agent_action_log.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
        index=True,
    )
