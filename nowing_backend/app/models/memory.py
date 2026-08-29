"""Models for the memory domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    Float,
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

from app.config import config
from app.db.base import BaseModel, TimestampMixin
from app.db.enums import (
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    ModelSource,
    PromptMode,
)


class Model(BaseModel, TimestampMixin):
    __tablename__ = "models"

    connection_id = Column(
        Integer,
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    source = Column(
        SQLAlchemyEnum(ModelSource),
        nullable=False,
        default=ModelSource.DISCOVERED,
        server_default=ModelSource.DISCOVERED.value,
    )
    supports_chat = Column(Boolean, nullable=True)
    max_input_tokens = Column(Integer, nullable=True)
    supports_image_input = Column(Boolean, nullable=True)
    supports_tools = Column(Boolean, nullable=True)
    supports_image_generation = Column(Boolean, nullable=True)
    capabilities_override = Column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    billing_tier = Column(String(50), nullable=True, index=True)
    catalog = Column(JSONB, nullable=False, default=dict, server_default="{}")

    connection = relationship("Connection", back_populates="models")

    __table_args__ = (
        UniqueConstraint(
            "connection_id", "model_id", name="uq_models_connection_model_id"
        ),
        Index("ix_models_model_id", "model_id"),
    )


class ImageGeneration(BaseModel, TimestampMixin):
    """
    Stores image generation requests and results using litellm.aimage_generation().

    Since aimage_generation is a single async call (not a background job),
    there is no status enum. A row with response_data means success;
    a row with error_message means failure.

    Response data is stored as JSONB matching the litellm output format:
    {
        "created": int,
        "data": [{"b64_json": str|None, "revised_prompt": str|None, "url": str|None}],
        "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    }
    """

    __tablename__ = "image_generations"

    # Request parameters (matching litellm.aimage_generation() params)
    prompt = Column(Text, nullable=False)
    model = Column(String(200), nullable=True)  # e.g., "dall-e-3", "gpt-image-1"
    n = Column(Integer, nullable=True, default=1)
    quality = Column(
        String(50), nullable=True
    )  # "auto", "high", "medium", "low", "hd", "standard"
    size = Column(
        String(50), nullable=True
    )  # "1024x1024", "1536x1024", "1024x1536", etc.
    style = Column(String(50), nullable=True)  # Model-specific style parameter
    response_format = Column(String(50), nullable=True)  # "url" or "b64_json"

    # Image generation model provenance.
    # 0 = Auto mode, negative IDs = GLOBAL models, positive IDs = Model records.
    image_gen_model_id = Column(Integer, nullable=True)

    # Response data (full litellm response as JSONB) — present on success
    response_data = Column(JSONB, nullable=True)
    # Error message — present on failure
    error_message = Column(Text, nullable=True)

    # Signed access token for serving images via <img> tags.
    # Stored in DB so it survives SECRET_KEY rotation.
    access_token = Column(String(64), nullable=True, index=True)

    # Foreign keys
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="image_generations")
    created_by = relationship("User", back_populates="image_generations")


class AgentConfig(BaseModel, TimestampMixin):
    """Registry of agents available to vertical clients (AD-30)."""

    __tablename__ = "agent_configs"
    __table_args__ = (
        UniqueConstraint("client_id", "slug", name="unique_agent_configs_client_slug"),
        UniqueConstraint("client_id", "name", name="unique_agent_configs_client_name"),
    )

    # Override BaseModel's Integer id with UUID as required by AD-30.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        CITEXT,
        ForeignKey("vertical_clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(Text, nullable=False)
    display_name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    system_instructions = Column(Text, nullable=True)
    enabled_tools = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    disabled_tools = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    model_name = Column(Text, nullable=True)
    citations_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class Memory(BaseModel, TimestampMixin):
    """A single, embedded long-term memory fact."""

    __tablename__ = "memories"
    __table_args__ = (
        Index(
            "ix_memories_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_memories_content_search",
            text("to_tsvector('english', content)"),
            postgresql_using="gin",
        ),
        # Serves the thread-recency read (`WHERE workspace_id = :w AND
        # research_thread_id = :t ORDER BY created_at DESC, id DESC LIMIT n`)
        # via backward index scan — without it PostgreSQL top-N sorts the
        # whole thread (migrations 181 and 183).
        Index(
            "ix_memories_thread_recency",
            "workspace_id",
            "research_thread_id",
            "created_at",
            "id",
            postgresql_where=text("research_thread_id IS NOT NULL"),
        ),
        # AC-18.6: hard tenant filter for vertical-client memories.
        Index(
            "ix_memories_workspace_id_client_id",
            "workspace_id",
            "client_id",
        ),
        Index(
            "ix_memories_archived_at_workspace_id",
            "archived_at",
            "workspace_id",
        ),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    research_thread_id = Column(
        Integer,
        ForeignKey("research_threads.id", ondelete="SET NULL"),
        nullable=True,
        # No single-column index: every production filter on this column is
        # always paired with a workspace_id/user_id scope condition (D5,
        # app/services/memory/search.py), and ix_memories_thread_recency
        # (leading columns workspace_id, research_thread_id, migrations 181/183)
        # already serves that combined equality+ORDER BY pattern strictly better.
        # Migration 182 drops the single-column ix_memories_research_thread_id
        # that index=True used to create here — keep this Column in sync with it.
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    agent_id = Column(Text, nullable=True)
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    type = Column(
        SQLAlchemyEnum(
            MemoryType,
            name="memory_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MemoryType.SEMANTIC,
        index=True,
    )
    content = Column(Text, nullable=False)
    embedding = Column(
        Vector(config.embedding_model_instance.dimension), nullable=False
    )
    source_type = Column(
        SQLAlchemyEnum(
            MemorySourceType,
            name="memory_source_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MemorySourceType.UNKNOWN,
    )
    source_id = Column(Integer, nullable=True, index=True)
    # Soft provenance for scraper-run-derived memory (Story 3.13, D4).
    # Deliberately NOT a foreign key to ``runs.id``: run logs are retained ~30
    # days and cleaned up opportunistically, while the memory they produced is
    # durable. A hard FK would either delete the memory with its run or block
    # the cleanup. ``source_id`` stays an integer (chat message ids); the run's
    # UUID lives here instead of being coerced into it.
    source_run_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    # Authoritative source pointer for Epic 21 UUID-keyed entities (AD-44 / AD-47).
    # ``source_run_id`` may be set alongside these for audit context, but
    # ``source_uuid`` + ``source_entity_type`` are the canonical provenance.
    source_uuid = Column(UUID(as_uuid=True), nullable=True, index=True)
    source_entity_type = Column(String(100), nullable=True)
    # Source recipe for re-validation (Story 9.6a, AD-11.1).
    # A soft copy of Run.capability and Run.input, not a live reference, so the
    # memory remains re-executable after the run log is cleaned up.
    source_capability = Column(String(100), nullable=True)
    source_input = Column(JSONB, nullable=True)
    tags = Column(ARRAY(String), nullable=True, default=list)
    confidence = Column(Float, nullable=False, default=1.0, server_default="1.0")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    workspace = relationship("Workspace", back_populates="memories")
    created_by = relationship("User", back_populates="memories")
    research_thread = relationship("ResearchThread", back_populates="memories")
    versions = relationship(
        "MemoryVersion",
        back_populates="memory",
        order_by="MemoryVersion.created_at",
        cascade="all, delete-orphan",
    )
    relations = relationship(
        "MemoryRelation",
        foreign_keys="MemoryRelation.from_memory_id",
        back_populates="memory",
        cascade="all, delete-orphan",
    )


class MemoryVersion(BaseModel, TimestampMixin):
    """Immutable prior content for a memory (audit/correction trail)."""

    __tablename__ = "memory_versions"

    memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_content = Column(Text, nullable=False)
    corrected_content = Column(Text, nullable=False)
    corrected_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    memory = relationship("Memory", back_populates="versions")
    corrected_by = relationship("User", back_populates="memory_versions")


class MemoryRelation(BaseModel, TimestampMixin):
    """Links a memory to another memory, document, chat, or scraper run."""

    __tablename__ = "memory_relations"
    __table_args__ = (
        # AC-18.6/Story 3.13: hard tenant filter for vertical-client relations.
        Index(
            "ix_memory_relations_workspace_id_client_id",
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
    client_id = Column(CITEXT, nullable=True, index=True)
    from_memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_memory_id = Column(Integer, nullable=True, index=True)
    relation_type = Column(
        SQLAlchemyEnum(
            MemoryRelationType,
            name="memory_relation_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    weight = Column(Float, nullable=False, default=1.0, server_default="1.0")

    workspace = relationship("Workspace", back_populates="memory_relations")
    memory = relationship(
        "Memory",
        foreign_keys=[from_memory_id],
        back_populates="relations",
    )


class Prompt(BaseModel, TimestampMixin):
    __tablename__ = "prompts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "default_prompt_slug",
            name="uq_prompt_user_default_slug",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    default_prompt_slug = Column(String(100), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    prompt = Column(Text, nullable=False)
    mode = Column(
        SQLAlchemyEnum(PromptMode, name="prompt_mode", create_type=False),
        nullable=False,
    )
    version = Column(Integer, nullable=False, default=1)
    is_public = Column(Boolean, nullable=False, default=False)

    user = relationship("User")
    workspace = relationship("Workspace")


class AgentActionLog(BaseModel):
    """Append-only audit trail of every tool call dispatched by the agent.

    One row per ``ToolMessage`` produced; written by ``ActionLogMiddleware``
    in its ``aafter_tool`` hook. Rows are referenced by the
    ``/api/threads/{thread_id}/revert/{action_id}`` route to look up an
    action's stored ``reverse_descriptor`` and replay it.

    The table is intentionally narrow: large tool outputs are NOT stored
    here. Result text lives in the langgraph checkpoint; this row only
    keeps a short ``result_id`` (the LangChain ``ToolMessage.id`` or a
    spilled-content path) for correlation.
    """

    __tablename__ = "agent_action_log"

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ``turn_id`` historically held the LangChain ``tool_call.id``. It has
    # been renamed to ``tool_call_id`` (with a parallel column kept for one
    # release for back-compat). The real chat-turn id lives in
    # ``chat_turn_id`` and is sourced from ``configurable.turn_id``.
    turn_id = Column(String(64), nullable=True, index=True)
    tool_call_id = Column(String(64), nullable=True, index=True)
    chat_turn_id = Column(String(64), nullable=True, index=True)
    message_id = Column(String(128), nullable=True, index=True)
    tool_name = Column(String(255), nullable=False, index=True)
    args = Column(JSONB, nullable=True)
    result_id = Column(String(255), nullable=True)
    reversible = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    reverse_descriptor = Column(JSONB, nullable=True)
    error = Column(JSONB, nullable=True)
    reverse_of = Column(
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

    __table_args__ = (
        Index("ix_agent_action_log_thread_created", "thread_id", "created_at"),
        # Partial unique index enforces "at most one revert per
        # original action". Created in migration 137 with
        # ``WHERE reverse_of IS NOT NULL`` so non-revert rows
        # (the vast majority) are unaffected and NULLs don't collide.
        Index(
            "ux_agent_action_log_reverse_of",
            "reverse_of",
            unique=True,
            postgresql_where=text("reverse_of IS NOT NULL"),
        ),
    )


class AgentPermissionRule(BaseModel):
    """Persistent permission rule consumed by :class:`PermissionMiddleware`.

    Scoped at one of: workspace-wide (``user_id`` and ``thread_id`` NULL),
    user-wide (``user_id`` set, ``thread_id`` NULL), or per-thread
    (``thread_id`` set). Loaded at agent build time and converted to
    :class:`Rule` instances inside the agent factory.
    """

    __tablename__ = "agent_permission_rules"

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
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    permission = Column(String(255), nullable=False)
    pattern = Column(String(255), nullable=False, default="*", server_default="*")
    action = Column(String(16), nullable=False)  # allow / deny / ask
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "thread_id",
            "permission",
            "pattern",
            "action",
            name="uq_agent_permission_rules_scope",
        ),
    )
