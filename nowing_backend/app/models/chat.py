"""Models for the chat domain."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    BigInteger,
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

from app.db.base import Base, BaseModel, TimestampMixin
from app.db.enums import (
    ChatVisibility,
    ExternalChatAccountMode,
    ExternalChatBindingState,
    ExternalChatEventKind,
    ExternalChatEventStatus,
    ExternalChatHealthStatus,
    ExternalChatPeerKind,
    ExternalChatPlatform,
    NewChatMessageRole,
    _enum_values,
)


class NewChatThread(BaseModel, TimestampMixin):
    """
    Thread model for the new chat feature using assistant-ui.
    Each thread represents a conversation with message history.
    LangGraph checkpointer uses thread_id for state persistence.
    """

    __tablename__ = "new_chat_threads"
    __table_args__ = (
        Index(
            "ix_new_chat_threads_workspace_id_client_id", "workspace_id", "client_id"
        ),
    )

    title = Column(String(500), nullable=False, default="New Chat", index=True)
    archived = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    # Visibility/sharing control
    visibility = Column(
        SQLAlchemyEnum(ChatVisibility),
        nullable=False,
        default=ChatVisibility.PRIVATE,
        server_default="PRIVATE",
        index=True,
    )

    # Foreign keys
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Track who created this chat thread (for visibility filtering)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for existing records before migration
        index=True,
    )

    # Clone tracking - for audit and history bootstrap
    cloned_from_thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cloned_from_snapshot_id = Column(
        Integer,
        ForeignKey("public_chat_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cloned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    # Flag to bootstrap LangGraph checkpointer with DB messages on first message
    needs_history_bootstrap = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    # Auto model pin for this thread: concrete resolved global LLM
    # config id. NULL means no pin; Auto will resolve on the next turn.
    # Single-writer invariant: only app.services.auto_model_pin_service sets
    # or clears this column (plus bulk clears when a workspace's
    # chat_model_id changes). Unindexed: all reads are by primary key.
    pinned_llm_config_id = Column(Integer, nullable=True)

    # Surface metadata for first-party Nowing and external chat threads.
    # Zero publishes all chat-message sources; the UI can decide which surfaces to render.
    source = Column(Text, nullable=False, default="nowing", server_default="nowing")
    client_id = Column(Text, nullable=True, index=True)
    agent_id = Column(Text, nullable=True, index=True)
    platform_metadata = Column(JSONB, nullable=True)
    external_chat_binding_id = Column(
        BigInteger,
        ForeignKey("external_chat_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    research_thread_id = Column(
        Integer,
        ForeignKey("research_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="new_chat_threads")
    created_by = relationship("User", back_populates="new_chat_threads")
    messages = relationship(
        "NewChatMessage",
        back_populates="thread",
        order_by="NewChatMessage.created_at",
        cascade="all, delete-orphan",
    )
    snapshots = relationship(
        "PublicChatSnapshot",
        back_populates="thread",
        cascade="all, delete-orphan",
        foreign_keys="[PublicChatSnapshot.thread_id]",
    )
    token_usages = relationship(
        "TokenUsage",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
    external_chat_binding = relationship(
        "ExternalChatBinding",
        foreign_keys=[external_chat_binding_id],
        back_populates="threads",
    )
    research_thread = relationship(
        "ResearchThread",
        foreign_keys=[research_thread_id],
        back_populates="new_chat_threads",
    )


class NewChatMessage(BaseModel, TimestampMixin):
    """
    Message model for the new chat feature.
    Stores individual messages in assistant-ui format.
    """

    __tablename__ = "new_chat_messages"

    # Partial unique index on (thread_id, turn_id, role) where turn_id IS NOT NULL.
    # Mirrors alembic migration 141. Lets the streaming agent and the
    # legacy frontend appendMessage call coexist idempotently — the second
    # writer trips the unique and recovers without creating a duplicate row.
    # Partial so legacy NULL turn_id rows and clone/snapshot inserts in
    # app/services/public_chat_service.py (which omit turn_id) are unaffected.
    __table_args__ = (
        Index(
            "uq_new_chat_messages_thread_turn_role",
            "thread_id",
            "turn_id",
            "role",
            unique=True,
            postgresql_where=text("turn_id IS NOT NULL"),
        ),
    )

    role = Column(SQLAlchemyEnum(NewChatMessageRole), nullable=False)
    # Content stored as JSONB to support rich content (text, tool calls, etc.)
    content = Column(JSONB, nullable=False)

    # Foreign key to thread
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Track who sent this message (for shared chats)
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Per-turn correlation id sourced from ``configurable.turn_id`` at
    # streaming time (``f"{chat_id}:{ms}"``). Nullable because legacy rows
    # predate the column. Used by C1's edit-from-arbitrary-position to map
    # a message back to the LangGraph checkpoint that produced its turn.
    turn_id = Column(String(64), nullable=True, index=True)

    # Mirrors the parent thread source for publication-level filtering.
    # This denormalization avoids join-dependent logical replication rules.
    source = Column(Text, nullable=False, default="nowing", server_default="nowing")
    platform_metadata = Column(JSONB, nullable=True)

    # Relationships
    thread = relationship("NewChatThread", back_populates="messages")
    author = relationship("User")
    comments = relationship(
        "ChatComment",
        back_populates="message",
        cascade="all, delete-orphan",
    )
    token_usage = relationship(
        "TokenUsage",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ExternalChatAccount(Base, TimestampMixin):
    __tablename__ = "external_chat_accounts"
    __allow_unmapped__ = True

    id = Column(BigInteger, primary_key=True, index=True)
    platform = Column(
        SQLAlchemyEnum(
            ExternalChatPlatform,
            name="external_chat_platform",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    mode = Column(
        SQLAlchemyEnum(
            ExternalChatAccountMode,
            name="external_chat_account_mode",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    owner_user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=True
    )
    owner_workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_system_account = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    encrypted_credentials = Column(Text, nullable=True)
    bot_username = Column(String(255), nullable=True)
    webhook_secret = Column(String(64), nullable=True)
    cursor_state = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    health_status = Column(
        SQLAlchemyEnum(
            ExternalChatHealthStatus,
            name="external_chat_health_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ExternalChatHealthStatus.UNKNOWN,
        server_default=ExternalChatHealthStatus.UNKNOWN.value,
    )
    last_health_check_at = Column(TIMESTAMP(timezone=True), nullable=True)
    suspended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    suspended_reason = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
    )

    owner = relationship("User", foreign_keys=[owner_user_id])
    owner_workspace = relationship("Workspace", foreign_keys=[owner_workspace_id])
    bindings = relationship(
        "ExternalChatBinding",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    inbound_events = relationship(
        "ExternalChatInboundEvent",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "(is_system_account = true AND owner_user_id IS NULL) OR "
            "(is_system_account = false AND owner_user_id IS NOT NULL)",
            name="ck_external_chat_accounts_owner_shape",
        ),
        Index(
            "uq_external_chat_accounts_owner_platform",
            "owner_user_id",
            "platform",
            unique=True,
            postgresql_where=text("is_system_account = false"),
        ),
        Index(
            "uq_external_chat_accounts_system_platform",
            "platform",
            unique=True,
            postgresql_where=text(
                "is_system_account = true "
                "AND NOT (cursor_state ? 'team_id') "
                "AND NOT (cursor_state ? 'guild_id')"
            ),
        ),
        Index(
            "uq_external_chat_accounts_slack_team",
            "platform",
            text("(cursor_state ->> 'team_id')"),
            unique=True,
            postgresql_where=text(
                "is_system_account = true AND cursor_state ? 'team_id'"
            ),
        ),
        Index(
            "uq_external_chat_accounts_discord_guild",
            "platform",
            text("(cursor_state ->> 'guild_id')"),
            unique=True,
            postgresql_where=text(
                "is_system_account = true AND cursor_state ? 'guild_id'"
            ),
        ),
        Index(
            "uq_external_chat_accounts_webhook_secret",
            "webhook_secret",
            unique=True,
            postgresql_where=text("webhook_secret IS NOT NULL"),
        ),
    )


class ExternalChatBinding(Base, TimestampMixin):
    __tablename__ = "external_chat_bindings"
    __allow_unmapped__ = True

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(
        BigInteger,
        ForeignKey("external_chat_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    state = Column(
        SQLAlchemyEnum(
            ExternalChatBindingState,
            name="external_chat_binding_state",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ExternalChatBindingState.PENDING,
        server_default=ExternalChatBindingState.PENDING.value,
    )
    pairing_code = Column(Text, nullable=True)
    pairing_code_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    external_peer_id = Column(Text, nullable=True)
    external_peer_kind = Column(
        SQLAlchemyEnum(
            ExternalChatPeerKind,
            name="external_chat_peer_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ExternalChatPeerKind.UNKNOWN,
        server_default=ExternalChatPeerKind.UNKNOWN.value,
    )
    external_thread_id = Column(Text, nullable=True)
    external_display_name = Column(Text, nullable=True)
    external_username = Column(Text, nullable=True)
    external_metadata = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    new_chat_thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    suspended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    suspended_reason = Column(Text, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
    )

    account = relationship("ExternalChatAccount", back_populates="bindings")
    user = relationship("User", foreign_keys=[user_id])
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    new_chat_thread = relationship("NewChatThread", foreign_keys=[new_chat_thread_id])
    threads = relationship(
        "NewChatThread",
        back_populates="external_chat_binding",
        foreign_keys="NewChatThread.external_chat_binding_id",
    )
    inbound_events = relationship(
        "ExternalChatInboundEvent",
        back_populates="binding",
        foreign_keys="ExternalChatInboundEvent.external_chat_binding_id",
    )

    __table_args__ = (
        Index(
            "uq_external_chat_bindings_account_peer_active",
            "account_id",
            "external_peer_id",
            unique=True,
            postgresql_where=text(
                "state IN ('bound', 'suspended') AND external_peer_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_external_chat_bindings_pairing_code_pending",
            "pairing_code",
            unique=True,
            postgresql_where=text("state = 'pending'"),
        ),
        Index("ix_external_chat_bindings_user_state", "user_id", "state"),
        Index("ix_external_chat_bindings_workspace_state", "workspace_id", "state"),
    )


class ExternalChatInboundEvent(Base, TimestampMixin):
    __tablename__ = "external_chat_inbound_events"
    __allow_unmapped__ = True

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(
        BigInteger,
        ForeignKey("external_chat_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_chat_binding_id = Column(
        BigInteger,
        ForeignKey("external_chat_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = Column(
        SQLAlchemyEnum(
            ExternalChatPlatform,
            name="external_chat_platform",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    event_dedupe_key = Column(Text, nullable=False)
    external_event_id = Column(Text, nullable=True)
    external_message_id = Column(Text, nullable=True)
    event_kind = Column(
        SQLAlchemyEnum(
            ExternalChatEventKind,
            name="external_chat_event_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    raw_payload = Column(JSONB, nullable=True)
    request_id = Column(String(64), nullable=True)
    status = Column(
        SQLAlchemyEnum(
            ExternalChatEventStatus,
            name="external_chat_event_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ExternalChatEventStatus.RECEIVED,
        server_default=ExternalChatEventStatus.RECEIVED.value,
    )
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    received_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("(now() AT TIME ZONE 'utc')"),
    )
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    account = relationship("ExternalChatAccount", back_populates="inbound_events")
    binding = relationship("ExternalChatBinding", back_populates="inbound_events")

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "event_dedupe_key",
            name="uq_external_chat_inbound_account_dedupe_key",
        ),
        Index("ix_external_chat_inbound_status_received_at", "status", "received_at"),
        Index(
            "ix_external_chat_inbound_binding_received_at",
            "external_chat_binding_id",
            "received_at",
        ),
        Index(
            "ix_external_chat_inbound_request_id",
            "request_id",
            postgresql_where=text("request_id IS NOT NULL"),
        ),
    )


class PublicChatSnapshot(BaseModel, TimestampMixin):
    """
    Immutable snapshot of a chat thread for public sharing.

    Each snapshot is a frozen copy of the chat at a specific point in time.
    The snapshot_data JSONB contains all messages and metadata needed to
    render the public chat without querying the original thread.
    """

    __tablename__ = "public_chat_snapshots"

    # Link to original thread - CASCADE DELETE when thread is deleted
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Public access token (unique URL identifier)
    share_token = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    content_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )

    snapshot_data = Column(JSONB, nullable=False)

    message_ids = Column(ARRAY(Integer), nullable=False)

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    thread = relationship(
        "NewChatThread",
        back_populates="snapshots",
        foreign_keys="[PublicChatSnapshot.thread_id]",
    )
    created_by = relationship("User")

    # Constraints
    __table_args__ = (
        # Prevent duplicate snapshots of the same content for the same thread
        UniqueConstraint(
            "thread_id", "content_hash", name="uq_snapshot_thread_content_hash"
        ),
    )


class ChatComment(BaseModel, TimestampMixin):
    """
    Comment model for comments on AI chat responses.
    Supports one level of nesting (replies to comments, but no replies to replies).
    """

    __tablename__ = "chat_comments"

    message_id = Column(
        Integer,
        ForeignKey("new_chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized thread_id for efficient Zero subscriptions (one per thread)
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id = Column(
        Integer,
        ForeignKey("chat_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    # Relationships
    message = relationship("NewChatMessage", back_populates="comments")
    thread = relationship("NewChatThread")
    author = relationship("User")
    parent = relationship(
        "ChatComment", remote_side="ChatComment.id", backref="replies"
    )
    mentions = relationship(
        "ChatCommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
    )


class ChatCommentMention(BaseModel, TimestampMixin):
    """
    Tracks @mentions in chat comments for notification purposes.
    """

    __tablename__ = "chat_comment_mentions"

    comment_id = Column(
        Integer,
        ForeignKey("chat_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentioned_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    comment = relationship("ChatComment", back_populates="mentions")
    mentioned_user = relationship("User")


class ChatSessionState(BaseModel):
    """
    Tracks real-time session state for shared chat collaboration.
    One record per thread, synced via Zero.
    """

    __tablename__ = "chat_session_state"

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_responding_to_user_id = Column(
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
    )

    thread = relationship("NewChatThread")
    ai_responding_to_user = relationship("User")
