import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import StrEnum

import anyio
from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, backref, declared_attr, relationship

from app.config import config

if config.AUTH_TYPE == "GOOGLE":
    from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID

logger = logging.getLogger(__name__)

DATABASE_URL = config.DATABASE_URL


class DocumentType(StrEnum):
    EXTENSION = "EXTENSION"
    CRAWLED_URL = "CRAWLED_URL"
    FILE = "FILE"
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    TEAMS_CONNECTOR = "TEAMS_CONNECTOR"
    ONEDRIVE_FILE = "ONEDRIVE_FILE"
    NOTION_CONNECTOR = "NOTION_CONNECTOR"
    YOUTUBE_VIDEO = "YOUTUBE_VIDEO"
    GITHUB_CONNECTOR = "GITHUB_CONNECTOR"
    LINEAR_CONNECTOR = "LINEAR_CONNECTOR"
    DISCORD_CONNECTOR = "DISCORD_CONNECTOR"
    JIRA_CONNECTOR = "JIRA_CONNECTOR"
    CONFLUENCE_CONNECTOR = "CONFLUENCE_CONNECTOR"
    CLICKUP_CONNECTOR = "CLICKUP_CONNECTOR"
    GOOGLE_CALENDAR_CONNECTOR = "GOOGLE_CALENDAR_CONNECTOR"
    GOOGLE_GMAIL_CONNECTOR = "GOOGLE_GMAIL_CONNECTOR"
    GOOGLE_DRIVE_FILE = "GOOGLE_DRIVE_FILE"
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    BOOKSTACK_CONNECTOR = "BOOKSTACK_CONNECTOR"
    CIRCLEBACK = "CIRCLEBACK"
    OBSIDIAN_CONNECTOR = "OBSIDIAN_CONNECTOR"
    NOTE = "NOTE"
    DROPBOX_FILE = "DROPBOX_FILE"
    COMPOSIO_GOOGLE_DRIVE_CONNECTOR = "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
    COMPOSIO_GMAIL_CONNECTOR = "COMPOSIO_GMAIL_CONNECTOR"
    COMPOSIO_GOOGLE_CALENDAR_CONNECTOR = "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"
    LOCAL_FOLDER_FILE = "LOCAL_FOLDER_FILE"
    NEWS_CONNECTOR = "NEWS_CONNECTOR"


# Native Google document types → their legacy Composio equivalents.
# Old documents may still carry the Composio type until they are re-indexed;
# search, browse, and indexing must transparently handle both.
NATIVE_TO_LEGACY_DOCTYPE: dict[str, str] = {
    "GOOGLE_DRIVE_FILE": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "COMPOSIO_GMAIL_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}


class SearchSourceConnectorType(StrEnum):
    SERPER_API = "SERPER_API"  # NOT IMPLEMENTED YET : DON'T REMEMBER WHY : MOST PROBABLY BECAUSE WE NEED TO CRAWL THE RESULTS RETURNED BY IT
    TAVILY_API = "TAVILY_API"
    SEARXNG_API = "SEARXNG_API"
    LINKUP_API = "LINKUP_API"
    BAIDU_SEARCH_API = "BAIDU_SEARCH_API"  # Baidu AI Search API for Chinese web search
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    TEAMS_CONNECTOR = "TEAMS_CONNECTOR"
    ONEDRIVE_CONNECTOR = "ONEDRIVE_CONNECTOR"
    NOTION_CONNECTOR = "NOTION_CONNECTOR"
    GITHUB_CONNECTOR = "GITHUB_CONNECTOR"
    LINEAR_CONNECTOR = "LINEAR_CONNECTOR"
    DISCORD_CONNECTOR = "DISCORD_CONNECTOR"
    JIRA_CONNECTOR = "JIRA_CONNECTOR"
    CONFLUENCE_CONNECTOR = "CONFLUENCE_CONNECTOR"
    CLICKUP_CONNECTOR = "CLICKUP_CONNECTOR"
    GOOGLE_CALENDAR_CONNECTOR = "GOOGLE_CALENDAR_CONNECTOR"
    GOOGLE_GMAIL_CONNECTOR = "GOOGLE_GMAIL_CONNECTOR"
    GOOGLE_DRIVE_CONNECTOR = "GOOGLE_DRIVE_CONNECTOR"
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    WEBCRAWLER_CONNECTOR = "WEBCRAWLER_CONNECTOR"
    BOOKSTACK_CONNECTOR = "BOOKSTACK_CONNECTOR"
    CIRCLEBACK_CONNECTOR = "CIRCLEBACK_CONNECTOR"
    OBSIDIAN_CONNECTOR = (
        "OBSIDIAN_CONNECTOR"  # Self-hosted only - Local Obsidian vault indexing
    )
    MCP_CONNECTOR = "MCP_CONNECTOR"  # Model Context Protocol - User-defined API tools
    EXA_MCP_CONNECTOR = "EXA_MCP_CONNECTOR"  # Exa AI search MCP server
    DROPBOX_CONNECTOR = "DROPBOX_CONNECTOR"
    COMPOSIO_GOOGLE_DRIVE_CONNECTOR = "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
    COMPOSIO_GMAIL_CONNECTOR = "COMPOSIO_GMAIL_CONNECTOR"
    COMPOSIO_GOOGLE_CALENDAR_CONNECTOR = "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"
    RSS_FEED = "RSS_FEED"


class VideoPresentationStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class DocumentStatus:
    """
    Helper class for document processing status (stored as JSONB).

    Status values:
    - {"state": "ready"} - Document is fully processed and searchable
    - {"state": "pending"} - Document is queued, waiting to be processed
    - {"state": "processing"} - Document is currently being processed (only 1 at a time)
    - {"state": "failed", "reason": "..."} - Processing failed with reason

    Usage:
        document.status = DocumentStatus.pending()
        document.status = DocumentStatus.processing()
        document.status = DocumentStatus.ready()
        document.status = DocumentStatus.failed("LLM rate limit exceeded")
    """

    # State constants
    READY = "ready"
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"

    @staticmethod
    def ready() -> dict:
        """Return status dict for a ready/searchable document."""
        return {"state": DocumentStatus.READY}

    @staticmethod
    def pending() -> dict:
        """Return status dict for a document waiting to be processed."""
        return {"state": DocumentStatus.PENDING}

    @staticmethod
    def processing() -> dict:
        """Return status dict for a document being processed."""
        return {"state": DocumentStatus.PROCESSING}

    @staticmethod
    def failed(reason: str, **extra_details) -> dict:
        """
        Return status dict for a failed document.

        Args:
            reason: Human-readable failure reason
            **extra_details: Optional additional details (duplicate_of, error_code, etc.)
        """
        status = {
            "state": DocumentStatus.FAILED,
            "reason": reason[:500],
        }  # Truncate long reasons
        if extra_details:
            status.update(extra_details)
        return status

    @staticmethod
    def get_state(status: dict | None) -> str | None:
        """Extract state from status dict, returns None if invalid."""
        if status is None:
            return None
        return status.get("state") if isinstance(status, dict) else None

    @staticmethod
    def is_state(status: dict | None, state: str) -> bool:
        """Check if status matches a given state."""
        return DocumentStatus.get_state(status) == state

    @staticmethod
    def get_failure_reason(status: dict | None) -> str | None:
        """Extract failure reason from status dict."""
        if status is None or not isinstance(status, dict):
            return None
        if status.get("state") == DocumentStatus.FAILED:
            return status.get("reason")
        return None


class DocumentRetentionAction(StrEnum):
    ARCHIVE = "archive"
    DELETE = "delete"


class ConnectionScope(StrEnum):
    GLOBAL = "GLOBAL"
    SEARCH_SPACE = "SEARCH_SPACE"
    USER = "USER"


class ModelSource(StrEnum):
    DISCOVERED = "DISCOVERED"
    MANUAL = "MANUAL"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class IncentiveTaskType(StrEnum):
    """
    Enum for incentive task types that users can complete to earn free pages.
    Each task can only be completed once per user.

    When adding new tasks:
    1. Add a new enum value here
    2. Add the task configuration to INCENTIVE_TASKS_CONFIG below
    3. Create an Alembic migration to add the enum value to PostgreSQL
    """

    GITHUB_STAR = "GITHUB_STAR"
    REDDIT_FOLLOW = "REDDIT_FOLLOW"
    DISCORD_JOIN = "DISCORD_JOIN"
    # Future tasks can be added here:
    # GITHUB_ISSUE = "GITHUB_ISSUE"
    # SOCIAL_SHARE = "SOCIAL_SHARE"
    # REFER_FRIEND = "REFER_FRIEND"


class PagePurchaseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class CreditPurchaseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# Centralized configuration for incentive tasks
# This makes it easy to add new tasks without changing code in multiple places
INCENTIVE_TASKS_CONFIG = {
    IncentiveTaskType.GITHUB_STAR: {
        "title": "Star our GitHub repository",
        "description": "Show your support by starring Nowing on GitHub",
        # Credit reward in USD micro-units (1_000_000 == $1.00). $0.03.
        "credit_micros_reward": 30000,
        "action_url": "https://github.com/nowing/Nowing",
    },
    IncentiveTaskType.REDDIT_FOLLOW: {
        "title": "Join our Subreddit",
        "description": "Join the Nowing community on Reddit",
        "credit_micros_reward": 30000,
        "action_url": "https://www.reddit.com/r/Nowing/",
    },
    IncentiveTaskType.DISCORD_JOIN: {
        "title": "Join our Discord",
        "description": "Join the Nowing community on Discord",
        "credit_micros_reward": 40000,
        "action_url": "https://discord.gg/ejRNvftDp9",
    },
    # Future tasks can be configured here:
    # IncentiveTaskType.GITHUB_ISSUE: {
    #     "title": "Create an issue",
    #     "description": "Help improve Nowing by reporting bugs or suggesting features",
    #     "credit_micros_reward": 50000,
    #     "action_url": "https://github.com/nowing/Nowing/issues/new/choose",
    # },
}


class Permission(StrEnum):
    """
    Granular permissions for workspace resources.
    Use '*' (FULL_ACCESS) to grant all permissions.
    """

    # Documents
    DOCUMENTS_CREATE = "documents:create"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_UPDATE = "documents:update"
    DOCUMENTS_DELETE = "documents:delete"

    # Chats
    CHATS_CREATE = "chats:create"
    CHATS_READ = "chats:read"
    CHATS_UPDATE = "chats:update"
    CHATS_DELETE = "chats:delete"

    # Comments
    COMMENTS_CREATE = "comments:create"
    COMMENTS_READ = "comments:read"
    COMMENTS_DELETE = "comments:delete"

    # LLM Configs
    LLM_CONFIGS_CREATE = "llm_configs:create"
    LLM_CONFIGS_READ = "llm_configs:read"
    LLM_CONFIGS_UPDATE = "llm_configs:update"
    LLM_CONFIGS_DELETE = "llm_configs:delete"

    # Podcasts
    PODCASTS_CREATE = "podcasts:create"
    PODCASTS_READ = "podcasts:read"
    PODCASTS_UPDATE = "podcasts:update"
    PODCASTS_DELETE = "podcasts:delete"

    # Video Presentations
    VIDEO_PRESENTATIONS_CREATE = "video_presentations:create"
    VIDEO_PRESENTATIONS_READ = "video_presentations:read"
    VIDEO_PRESENTATIONS_UPDATE = "video_presentations:update"
    VIDEO_PRESENTATIONS_DELETE = "video_presentations:delete"

    # Image Generations
    IMAGE_GENERATIONS_CREATE = "image_generations:create"
    IMAGE_GENERATIONS_READ = "image_generations:read"
    IMAGE_GENERATIONS_DELETE = "image_generations:delete"

    # Vision LLM Configs
    VISION_CONFIGS_CREATE = "vision_configs:create"
    VISION_CONFIGS_READ = "vision_configs:read"
    VISION_CONFIGS_DELETE = "vision_configs:delete"

    # Connectors
    CONNECTORS_CREATE = "connectors:create"
    CONNECTORS_READ = "connectors:read"
    CONNECTORS_UPDATE = "connectors:update"
    CONNECTORS_DELETE = "connectors:delete"

    # Logs
    LOGS_READ = "logs:read"
    LOGS_DELETE = "logs:delete"

    # Members
    MEMBERS_INVITE = "members:invite"
    MEMBERS_VIEW = "members:view"
    MEMBERS_REMOVE = "members:remove"
    MEMBERS_MANAGE_ROLES = "members:manage_roles"

    # Roles
    ROLES_CREATE = "roles:create"
    ROLES_READ = "roles:read"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # Workspace Settings
    SETTINGS_VIEW = "settings:view"
    SETTINGS_UPDATE = "settings:update"
    SETTINGS_DELETE = "settings:delete"  # Delete the entire workspace

    # API Access
    API_ACCESS_MANAGE = "api_access:manage"

    # Public Sharing
    PUBLIC_SHARING_VIEW = "public_sharing:view"
    PUBLIC_SHARING_CREATE = "public_sharing:create"
    PUBLIC_SHARING_DELETE = "public_sharing:delete"

    # Automations
    AUTOMATIONS_CREATE = "automations:create"
    AUTOMATIONS_READ = "automations:read"
    AUTOMATIONS_UPDATE = "automations:update"
    AUTOMATIONS_DELETE = "automations:delete"
    AUTOMATIONS_EXECUTE = "automations:execute"

    # Memory
    MEMORY_CREATE = "memory:create"
    MEMORY_READ = "memory:read"
    MEMORY_UPDATE = "memory:update"
    MEMORY_DELETE = "memory:delete"

    # Leads / lead scoring (Story 21.2)
    LEADS_READ = "leads:read"
    LEADS_WRITE = "leads:write"
    LEADS_SCORE = "leads:score"

    # Lead contact enrichment (Story 21.3)
    LEADS_ENRICH = "leads:enrich"
    CONTACTS_READ = "contacts:read"

    # CRM (Story 21.5)
    CRM_CONNECT = "crm:connect"
    CRM_READ = "crm:read"
    CRM_WRITE = "crm:write"
    CRM_SYNC = "crm:sync"
    CRM_DISCONNECT = "crm:disconnect"
    # Signal detection (Story 21.1)
    SIGNALS_READ = "signals:read"
    SIGNALS_DETECT = "signals:detect"

    # Canonical entities (merge history, conflict resolution, revert)
    CANONICAL_ENTITIES_READ = "canonical_entities:read"
    CANONICAL_ENTITIES_WRITE = "canonical_entities:write"

    # Full access wildcard
    FULL_ACCESS = "*"


# Predefined role permission sets for convenience
# Note: Only Owner, Editor, and Viewer roles are supported.
# Owner has full access (*), Editor can do everything except delete, Viewer has read-only access.
DEFAULT_ROLE_PERMISSIONS = {
    "Owner": [Permission.FULL_ACCESS.value],
    "Editor": [
        # Documents (no delete)
        Permission.DOCUMENTS_CREATE.value,
        Permission.DOCUMENTS_READ.value,
        Permission.DOCUMENTS_UPDATE.value,
        # Chats (no delete)
        Permission.CHATS_CREATE.value,
        Permission.CHATS_READ.value,
        Permission.CHATS_UPDATE.value,
        # Comments (no delete)
        Permission.COMMENTS_CREATE.value,
        Permission.COMMENTS_READ.value,
        # LLM Configs (no delete)
        Permission.LLM_CONFIGS_CREATE.value,
        Permission.LLM_CONFIGS_READ.value,
        Permission.LLM_CONFIGS_UPDATE.value,
        # Podcasts (no delete)
        Permission.PODCASTS_CREATE.value,
        Permission.PODCASTS_READ.value,
        Permission.PODCASTS_UPDATE.value,
        # Video Presentations (no delete)
        Permission.VIDEO_PRESENTATIONS_CREATE.value,
        Permission.VIDEO_PRESENTATIONS_READ.value,
        Permission.VIDEO_PRESENTATIONS_UPDATE.value,
        # Image Generations (create and read, no delete)
        Permission.IMAGE_GENERATIONS_CREATE.value,
        Permission.IMAGE_GENERATIONS_READ.value,
        # Vision Configs (create and read, no delete)
        Permission.VISION_CONFIGS_CREATE.value,
        Permission.VISION_CONFIGS_READ.value,
        # Connectors (no delete)
        Permission.CONNECTORS_CREATE.value,
        Permission.CONNECTORS_READ.value,
        Permission.CONNECTORS_UPDATE.value,
        # Logs (read only)
        Permission.LOGS_READ.value,
        # Members (can invite and view only, cannot manage roles or remove)
        Permission.MEMBERS_INVITE.value,
        Permission.MEMBERS_VIEW.value,
        # Roles (read only - cannot create, update, or delete)
        Permission.ROLES_READ.value,
        # Settings (view only, no update or delete)
        Permission.SETTINGS_VIEW.value,
        # Public Sharing (can create and view, no delete)
        Permission.PUBLIC_SHARING_VIEW.value,
        Permission.PUBLIC_SHARING_CREATE.value,
        # Automations (no delete)
        Permission.AUTOMATIONS_CREATE.value,
        Permission.AUTOMATIONS_READ.value,
        Permission.AUTOMATIONS_UPDATE.value,
        Permission.AUTOMATIONS_EXECUTE.value,
        # Memory (no delete)
        Permission.MEMORY_CREATE.value,
        Permission.MEMORY_READ.value,
        Permission.MEMORY_UPDATE.value,
        # Canonical entities (no delete)
        Permission.CANONICAL_ENTITIES_READ.value,
        Permission.CANONICAL_ENTITIES_WRITE.value,
    ],
    "Viewer": [
        # Documents (read only)
        Permission.DOCUMENTS_READ.value,
        # Chats (read only)
        Permission.CHATS_READ.value,
        # Comments (can create and read, but not delete)
        Permission.COMMENTS_CREATE.value,
        Permission.COMMENTS_READ.value,
        # LLM Configs (read only)
        Permission.LLM_CONFIGS_READ.value,
        # Podcasts (read only)
        Permission.PODCASTS_READ.value,
        # Video Presentations (read only)
        Permission.VIDEO_PRESENTATIONS_READ.value,
        # Image Generations (read only)
        Permission.IMAGE_GENERATIONS_READ.value,
        # Vision Configs (read only)
        Permission.VISION_CONFIGS_READ.value,
        # Connectors (read only)
        Permission.CONNECTORS_READ.value,
        # Logs (read only)
        Permission.LOGS_READ.value,
        # Members (view only)
        Permission.MEMBERS_VIEW.value,
        # Roles (read only)
        Permission.ROLES_READ.value,
        # Settings (view only)
        Permission.SETTINGS_VIEW.value,
        # Public Sharing (view only)
        Permission.PUBLIC_SHARING_VIEW.value,
        # Automations (read only)
        Permission.AUTOMATIONS_READ.value,
        # Memory (read only)
        Permission.MEMORY_READ.value,
        # Canonical entities (read only)
        Permission.CANONICAL_ENTITIES_READ.value,
    ],
}


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    @declared_attr
    def created_at(cls):  # noqa: N805
        return Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
            server_default=text("now()"),
            index=True,
        )


class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)


class NewChatMessageRole(StrEnum):
    """Role enum for new chat messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatVisibility(StrEnum):
    """
    Visibility/sharing level for chat threads.

    PRIVATE: Only the creator can see/access the chat (default)
    SEARCH_SPACE: All members of the workspace can see/access the chat
    PUBLIC: (Future) Anyone with the link can access the chat
    """

    PRIVATE = "PRIVATE"
    SEARCH_SPACE = "SEARCH_SPACE"
    # PUBLIC = "PUBLIC"  # Reserved for future implementation


class ExternalChatPlatform(StrEnum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    DISCORD = "discord"
    SIGNAL = "signal"


class ExternalChatAccountMode(StrEnum):
    CLOUD_SHARED = "cloud_shared"
    SELF_HOST_BYO = "self_host_byo"


class MemoryType(StrEnum):
    """Kind of long-term memory being stored."""

    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class MemorySourceType(StrEnum):
    """Origin of a memory fact."""

    DOCUMENT = "document"
    CHAT_MESSAGE = "chat_message"
    SCRAPER_RUN = "scraper_run"
    MANUAL = "manual"
    UNKNOWN = "unknown"
    SIGNAL = "signal"
    LEAD = "lead"
    LEAD_SCORE = "lead_score"
    ENRICHMENT = "enrichment"
    CRM_CONNECTION = "crm_connection"
    CRM_SYNC = "crm_sync"
    SEQUENCE_EVENT = "sequence_event"
    OUTCOME_EVENT = "outcome_event"


class MemoryRelationType(StrEnum):
    """Relationship between a memory and another entity."""

    RELATED = "related"
    DERIVED_FROM = "derived_from"
    CORRECTS = "corrects"
    SOURCE_DOCUMENT = "source_document"
    SOURCE_CHAT = "source_chat"
    SOURCE_RUN = "source_run"


class ExternalChatHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    OK = "ok"
    FAILING = "failing"


class ExternalChatBindingState(StrEnum):
    PENDING = "pending"
    BOUND = "bound"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class ExternalChatPeerKind(StrEnum):
    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"
    UNKNOWN = "unknown"


class ExternalChatEventKind(StrEnum):
    MESSAGE = "message"
    EDITED_MESSAGE = "edited_message"
    CALLBACK_QUERY = "callback_query"
    OTHER = "other"


class ExternalChatEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


def _enum_values(enum_cls):
    return [item.value for item in enum_cls]


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


class ScraperPlatformAccount(Base, TimestampMixin):
    """Admin-managed credentials for a proprietary scraper platform."""

    __tablename__ = "scraper_platform_accounts"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(64), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    encrypted_credentials = Column(Text, nullable=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    usage_state = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        Index(
            "uq_scraper_platform_accounts_default",
            "platform",
            unique=True,
            postgresql_where=text("is_default = true"),
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


class TokenUsage(BaseModel, TimestampMixin):
    """
    Tracks LLM token consumption per assistant turn.

    One row per usage event. For chat, linked to a specific message via message_id.
    The usage_type column enables future extension to track non-chat usage
    (indexing, image generation, podcasts, etc.) without schema changes.
    """

    __tablename__ = "token_usage"

    # Partial unique index on (message_id) where message_id IS NOT NULL.
    # Mirrors alembic migration 142. Lets the streaming agent's
    # ``finalize_assistant_turn`` and the legacy frontend ``append_message``
    # recovery branch both use ``INSERT ... ON CONFLICT DO NOTHING`` without
    # racing on a SELECT-then-INSERT window. Partial so non-chat usage rows
    # (indexing, image generation, podcasts) — which keep ``message_id`` NULL
    # because there is no per-message anchor — are unaffected.
    __table_args__ = (
        Index(
            "uq_token_usage_message_id",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        Index(
            "ix_token_usage_deep_research_resolved_mode_created_at",
            "usage_type",
            "resolved_mode",
            "created_at",
            postgresql_where=text(
                "usage_type = 'deep_research' AND resolved_mode IS NOT NULL"
            ),
        ),
        # AC-18.7: daily cost rollups by workspace + client.
        Index(
            "ix_token_usage_workspace_client_created_at",
            "workspace_id",
            "client_id",
            "created_at",
        ),
    )

    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    model_breakdown = Column(JSONB, nullable=True)
    call_details = Column(JSONB, nullable=True)
    resolved_mode = Column(String(50), nullable=True)
    mode_requested = Column(String(50), nullable=True)
    e2e_ms = Column(Integer, nullable=True)
    ttfb_ms = Column(Integer, nullable=True)

    usage_type = Column(String(50), nullable=False, default="chat", index=True)

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("new_chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    external_metadata = Column(JSONB, nullable=True, default=dict)
    run_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Relationships
    thread = relationship("NewChatThread", back_populates="token_usages")
    message = relationship("NewChatMessage", back_populates="token_usage")
    workspace = relationship("Workspace")
    user = relationship("User")


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


class VideoPresentation(BaseModel, TimestampMixin):
    """Video presentation model for storing AI-generated video presentations.

    The slides JSONB stores per-slide data including Remotion component code,
    audio file paths, and durations. The frontend compiles the code and renders
    the video using Remotion Player.
    """

    __tablename__ = "video_presentations"

    title = Column(String(500), nullable=False)
    slides = Column(JSONB, nullable=True)
    scene_codes = Column(JSONB, nullable=True)
    status = Column(
        SQLAlchemyEnum(
            VideoPresentationStatus,
            name="video_presentation_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VideoPresentationStatus.READY,
        server_default="ready",
        index=True,
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="video_presentations")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")


class Report(BaseModel, TimestampMixin):
    """Report model for storing generated reports (Markdown or Typst)."""

    __tablename__ = "reports"

    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(20), nullable=False, server_default="markdown")
    report_metadata = Column(JSONB, nullable=True)  # section headings, word count, etc.
    report_style = Column(
        String(100), nullable=True
    )  # e.g. "executive_summary", "deep_research"

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="reports")

    # Versioning: reports sharing the same report_group_id are versions of the same report.
    # For v1, report_group_id = the report's own id (set after insert).
    report_group_id = Column(Integer, nullable=True, index=True)

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")


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


class Workspace(BaseModel, TimestampMixin):
    __tablename__ = "workspaces"

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

    citations_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Enable/disable citations
    api_access_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
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

    memory_auto_extract_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Epic 21 lead scoring ICP criteria (Story 21.2).
    icp_criteria = Column(JSONB, nullable=True)

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
    leads = relationship(
        "Lead",
        back_populates="workspace",
        order_by="Lead.created_at.desc()",
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
    run_period_hours = Column(
        Integer,
        nullable=False,
        default=720,
        server_default="720",
    )

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


class UserIncentiveTask(BaseModel, TimestampMixin):
    """
    Tracks completed incentive tasks for users.
    Each user can only complete each task type once.
    When a task is completed, the user's credit_micros_balance is increased.
    """

    __tablename__ = "user_incentive_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_type",
            name="uq_user_incentive_task",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type = Column(SQLAlchemyEnum(IncentiveTaskType), nullable=False, index=True)
    # Credit reward granted in USD micro-units (1_000_000 == $1.00).
    credit_micros_awarded = Column(BigInteger, nullable=False)
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", back_populates="incentive_tasks")


class PagePurchase(Base, TimestampMixin):
    """Tracks Stripe checkout sessions used to grant additional page credits."""

    __tablename__ = "page_purchases"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_checkout_session_id = Column(
        String(255), nullable=False, unique=True, index=True
    )
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    pages_granted = Column(Integer, nullable=False)
    amount_total = Column(Integer, nullable=True)
    currency = Column(String(10), nullable=True)
    status = Column(
        SQLAlchemyEnum(PagePurchaseStatus),
        nullable=False,
        default=PagePurchaseStatus.PENDING,
        server_default=text("'PENDING'::pagepurchasestatus"),
        index=True,
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User", back_populates="page_purchases")


class CreditPurchase(Base, TimestampMixin):
    """Tracks Stripe checkout sessions used to grant credit (USD micro-units).

    Renamed from ``premium_token_purchases`` in migration 156 as part of the
    unified-credits wallet. ``credit_micros_granted`` stores the USD-micro
    amount added to ``user.credit_micros_balance`` on fulfillment.

    ``source`` distinguishes a user-initiated checkout from an automatic
    off-session top-up (auto-reload), added in the auto-reload migration.
    """

    __tablename__ = "credit_purchases"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_checkout_session_id = Column(
        String(255), nullable=False, unique=True, index=True
    )
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    credit_micros_granted = Column(BigInteger, nullable=False)
    amount_total = Column(Integer, nullable=True)
    currency = Column(String(10), nullable=True)
    source = Column(
        String(20), nullable=False, default="checkout", server_default="checkout"
    )
    status = Column(
        SQLAlchemyEnum(CreditPurchaseStatus),
        nullable=False,
        default=CreditPurchaseStatus.PENDING,
        index=True,
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User", back_populates="credit_purchases")


class WorkspaceRole(BaseModel, TimestampMixin):
    """
    Custom roles that can be defined per workspace.
    Each workspace can have multiple roles with different permission sets.
    """

    __tablename__ = "workspace_roles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_workspace_role_name",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    # List of Permission enum values (e.g., ["documents:read", "chats:create"])
    permissions = Column(ARRAY(String), nullable=False, default=[])
    # Whether this role is assigned to new members by default when they join via invite
    is_default = Column(Boolean, nullable=False, default=False)
    # System roles (Owner, Editor, Viewer) cannot be deleted
    is_system_role = Column(Boolean, nullable=False, default=False)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="roles")

    memberships = relationship(
        "WorkspaceMembership", back_populates="role", passive_deletes=True
    )
    invites = relationship(
        "WorkspaceInvite", back_populates="role", passive_deletes=True
    )


class WorkspaceMembership(BaseModel, TimestampMixin):
    """
    Tracks user membership in workspaces with their assigned role.
    Each user can be a member of multiple workspaces with different roles.
    """

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            name="uq_user_workspace_membership",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        Integer,
        ForeignKey("workspace_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Indicates if this user is the original creator/owner of the workspace
    is_owner = Column(Boolean, nullable=False, default=False)
    # Timestamp when the user joined (via invite or as creator)
    joined_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Reference to the invite used to join (null if owner/creator)
    invited_by_invite_id = Column(
        Integer,
        ForeignKey("workspace_invites.id", ondelete="SET NULL"),
        nullable=True,
    )

    user = relationship("User", back_populates="workspace_memberships")
    workspace = relationship("Workspace", back_populates="memberships")
    role = relationship("WorkspaceRole", back_populates="memberships")
    invited_by_invite = relationship(
        "WorkspaceInvite", back_populates="used_by_memberships"
    )


class WorkspaceInvite(BaseModel, TimestampMixin):
    """
    Invite links for workspaces.
    Users can create invite links with specific roles that others can use to join.
    """

    __tablename__ = "workspace_invites"

    # Unique invite code (used in invite URLs)
    invite_code = Column(String(64), nullable=False, unique=True, index=True)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Role to assign when invite is used (null means use default role)
    role_id = Column(
        Integer,
        ForeignKey("workspace_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # User who created this invite
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Expiration timestamp (null means never expires)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Maximum number of times this invite can be used (null means unlimited)
    max_uses = Column(Integer, nullable=True)
    # Number of times this invite has been used
    uses_count = Column(Integer, nullable=False, default=0)
    # Whether this invite is currently active
    is_active = Column(Boolean, nullable=False, default=True)
    # Optional custom name/label for the invite
    name = Column(String(100), nullable=True)

    workspace = relationship("Workspace", back_populates="invites")
    role = relationship("WorkspaceRole", back_populates="invites")
    created_by = relationship("User", back_populates="created_invites")
    used_by_memberships = relationship(
        "WorkspaceMembership",
        back_populates="invited_by_invite",
        passive_deletes=True,
    )


class PromptMode(StrEnum):
    transform = "transform"
    explore = "explore"


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


if config.AUTH_TYPE == "GOOGLE":

    class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
        pass

    class User(SQLAlchemyBaseUserTableUUID, Base):
        oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
            "OAuthAccount", lazy="joined"
        )
        workspaces = relationship("Workspace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        workspace_memberships = relationship(
            "WorkspaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "WorkspaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Folders created by this user
        folders = relationship(
            "Folder",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Image generations created by this user
        image_generations = relationship(
            "ImageGeneration",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Connectors created by this user
        search_source_connectors = relationship(
            "SearchSourceConnector",
            back_populates="user",
            passive_deletes=True,
        )

        connections = relationship(
            "Connection",
            back_populates="user",
            passive_deletes=True,
        )

        # Automations created by this user
        automations = relationship(
            "Automation",
            back_populates="created_by",
            passive_deletes=True,
        )

        playbooks = relationship(
            "Playbook",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        page_purchases = relationship(
            "PagePurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        credit_purchases = relationship(
            "CreditPurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Unified credit wallet (USD micro-units, 1_000_000 == $1.00).
        # Decreases on use (ETL pages + premium model calls), increases on
        # purchase / incentive grant / auto-reload. May dip slightly negative
        # when an actual cost exceeds its pre-charge estimate; UI clamps at $0.
        credit_micros_balance = Column(
            BigInteger,
            nullable=False,
            default=config.DEFAULT_CREDIT_MICROS_BALANCE,
            server_default=str(config.DEFAULT_CREDIT_MICROS_BALANCE),
        )
        # In-flight reservation holds (released/settled at finalize).
        credit_micros_reserved = Column(
            BigInteger, nullable=False, default=0, server_default="0"
        )

        # Auto-reload (off-session Stripe top-up), behind AUTO_RELOAD_ENABLED.
        # ``stripe_customer_id`` + ``auto_reload_payment_method_id`` are the
        # saved-card plumbing; thresholds are micro-USD. ``auto_reload_failed_at``
        # is set (and ``auto_reload_enabled`` flipped off) when an off-session
        # charge is declined so the UI can prompt the user to fix their card.
        stripe_customer_id = Column(String, nullable=True)
        auto_reload_enabled = Column(
            Boolean, nullable=False, default=False, server_default="false"
        )
        auto_reload_threshold_micros = Column(BigInteger, nullable=True)
        auto_reload_amount_micros = Column(BigInteger, nullable=True)
        auto_reload_payment_method_id = Column(String, nullable=True)
        auto_reload_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)

        # User profile from OAuth
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)

        last_login = Column(TIMESTAMP(timezone=True), nullable=True)

        notification_preferences = Column(
            JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
        )

        # Refresh tokens for this user
        refresh_tokens = relationship(
            "RefreshToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        personal_access_tokens = relationship(
            "PersonalAccessToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        # Memory created by this user
        memories = relationship(
            "Memory",
            back_populates="created_by",
            passive_deletes=True,
        )
        memory_versions = relationship(
            "MemoryVersion",
            back_populates="corrected_by",
            passive_deletes=True,
        )
        research_threads = relationship(
            "ResearchThread",
            back_populates="created_by",
            passive_deletes=True,
        )

else:

    class User(SQLAlchemyBaseUserTableUUID, Base):
        workspaces = relationship("Workspace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        workspace_memberships = relationship(
            "WorkspaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "WorkspaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Folders created by this user
        folders = relationship(
            "Folder",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Image generations created by this user
        image_generations = relationship(
            "ImageGeneration",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Connectors created by this user
        search_source_connectors = relationship(
            "SearchSourceConnector",
            back_populates="user",
            passive_deletes=True,
        )

        connections = relationship(
            "Connection",
            back_populates="user",
            passive_deletes=True,
        )

        # Automations created by this user
        automations = relationship(
            "Automation",
            back_populates="created_by",
            passive_deletes=True,
        )

        playbooks = relationship(
            "Playbook",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        page_purchases = relationship(
            "PagePurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        credit_purchases = relationship(
            "CreditPurchase",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Unified credit wallet (USD micro-units, 1_000_000 == $1.00).
        # Decreases on use (ETL pages + premium model calls), increases on
        # purchase / incentive grant / auto-reload. May dip slightly negative
        # when an actual cost exceeds its pre-charge estimate; UI clamps at $0.
        credit_micros_balance = Column(
            BigInteger,
            nullable=False,
            default=config.DEFAULT_CREDIT_MICROS_BALANCE,
            server_default=str(config.DEFAULT_CREDIT_MICROS_BALANCE),
        )
        # In-flight reservation holds (released/settled at finalize).
        credit_micros_reserved = Column(
            BigInteger, nullable=False, default=0, server_default="0"
        )

        # Auto-reload (off-session Stripe top-up), behind AUTO_RELOAD_ENABLED.
        # ``stripe_customer_id`` + ``auto_reload_payment_method_id`` are the
        # saved-card plumbing; thresholds are micro-USD. ``auto_reload_failed_at``
        # is set (and ``auto_reload_enabled`` flipped off) when an off-session
        # charge is declined so the UI can prompt the user to fix their card.
        stripe_customer_id = Column(String, nullable=True)
        auto_reload_enabled = Column(
            Boolean, nullable=False, default=False, server_default="false"
        )
        auto_reload_threshold_micros = Column(BigInteger, nullable=True)
        auto_reload_amount_micros = Column(BigInteger, nullable=True)
        auto_reload_payment_method_id = Column(String, nullable=True)
        auto_reload_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)

        # User profile (can be set manually for non-OAuth users)
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)

        last_login = Column(TIMESTAMP(timezone=True), nullable=True)

        notification_preferences = Column(
            JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
        )

        # Refresh tokens for this user
        refresh_tokens = relationship(
            "RefreshToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        personal_access_tokens = relationship(
            "PersonalAccessToken",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        # Memory created by this user
        memories = relationship(
            "Memory",
            back_populates="created_by",
            passive_deletes=True,
        )
        memory_versions = relationship(
            "MemoryVersion",
            back_populates="corrected_by",
            passive_deletes=True,
        )
        research_threads = relationship(
            "ResearchThread",
            back_populates="created_by",
            passive_deletes=True,
        )


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


class RefreshToken(Base, TimestampMixin):
    """
    Stores refresh tokens for user session management.
    Each row represents one device/session.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user = relationship("User", back_populates="refresh_tokens")
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    absolute_expiry = Column(TIMESTAMP(timezone=True), nullable=True)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and self.revoked_at is None


class PersonalAccessToken(BaseModel, TimestampMixin):
    """
    Stores hashed Personal Access Tokens for programmatic API access.
    Plaintext tokens are shown once on creation and are never persisted.

    Scoped PATs (token_kind='agent_chat') bind to exactly one workspace
    and one vertical client. Client-supplied IDs are intersected with the
    token scope at runtime; the schema enforces a minimum scope for
    agent_chat tokens.
    """

    __tablename__ = "personal_access_tokens"

    __table_args__ = (
        CheckConstraint(
            "(token_kind != 'agent_chat') OR "
            "(workspace_id IS NOT NULL AND client_id IS NOT NULL AND scopes != '[]'::jsonb)",
            name="chk_pat_agent_chat_requires_scope",
        ),
        CheckConstraint(
            "(agent_id IS NULL) OR (client_id IS NOT NULL)",
            name="chk_pat_agent_id_requires_client_id",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user = relationship("User", back_populates="personal_access_tokens")
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    token_prefix = Column(String(16), nullable=False)
    label = Column(String, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # PAT scope fields (Epic 18)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    client_id = Column(Text, nullable=True, index=True)
    agent_id = Column(Text, nullable=True, index=True)
    scopes = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    token_kind = Column(
        Text,
        nullable=False,
        default="legacy",
        server_default="legacy",
    )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now(UTC) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired


class Run(Base, TimestampMixin):
    """One row per scraper-capability invocation, from either the agent door
    or the REST/API-key door.

    Backs the user-facing Scraper-API logs and the agent's tool-boundary
    truncation: the full output lives here while the model sees only a capped
    preview plus this row's id. ``output_text`` is stored as JSONL (one item
    per line, ``exclude_none``) so ``read_run``/``search_run`` can page and grep
    by line without parsing the whole payload. Retained ~30 days via opportunistic
    bounded cleanup on insert.

    ``cost_micros`` ships nullable and unpopulated in this pass; the planned
    per-verb pricing rework will fill it. ``thread_id`` is a free-form string
    (subagent ids look like ``"2099::task:call_x"``), so it is intentionally not
    a foreign key.
    """

    __tablename__ = "runs"
    __allow_unmapped__ = True

    __table_args__ = (
        Index("ix_runs_workspace_created", "workspace_id", "created_at"),
        # AC-18.7: vertical-client run attribution and daily rollups.
        Index(
            "ix_runs_workspace_client_created",
            "workspace_id",
            "client_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    thread_id = Column(String(255), nullable=True)
    capability = Column(String(100), nullable=False, index=True)
    origin = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    error = Column(Text, nullable=True)
    input = Column(JSONB, nullable=True)
    output_text = Column(Text, nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    char_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=True)
    cost_micros = Column(BigInteger, nullable=True)
    client_id = Column(Text, nullable=True, index=True)
    external_metadata = Column(JSONB, nullable=True, default=dict)
    # Coarse progress log (list of throttled events) captured during the run;
    # the live fine-grained stream is ephemeral (bus/SSE only).
    progress = Column(JSONB, nullable=True)
    # Durable memory-extraction state (Story 3.13, D6). Celery delivery is
    # at-least-once, so idempotency cannot rely on "did this run produce
    # memory rows" alone: a successful extraction that found ZERO qualifying
    # facts must also be terminal, or every redelivery re-calls (and re-pays
    # for) the LLM. ``pending`` is claimed via compare-and-set before the LLM
    # call so two concurrent workers resolve to exactly one LLM call.
    #   NULL      -> never enqueued/considered
    #   pending   -> claimed by a worker, LLM call in flight
    #   completed -> extraction ran to completion (with or without facts)
    #   skipped   -> policy/gate/missing-creator decision, terminal
    #   failed    -> retry budget exhausted, terminal
    memory_extraction_status = Column(String(16), nullable=True, index=True)
    memory_extraction_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Structured skip/failure reason, sharing Story 8.7/8.8's vocabulary
    # (``disabled``, ``anonymous_unbilled``, ``missing_creator``, ...).
    memory_extraction_skip_reason = Column(String(64), nullable=True)


class AntiBotEscalation(BaseModel, TimestampMixin):
    """Admin-escalation row for an anti-bot / CAPTCHA block.

    Tracks which workspace and capability hit a block, how many times the same
    (workspace, domain, capability) tripped while open, and the screenshot
    evidence. Open rows are grouped by (workspace_id, domain, capability) so
    repeated blocks increment ``detection_count`` rather than creating noise.
    """

    __tablename__ = "anti_bot_escalations"

    __table_args__ = (
        Index(
            "ix_anti_bot_escalations_grouping_open_unique",
            "workspace_id",
            "domain",
            "capability",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "ix_anti_bot_escalations_status_created_at",
            "status",
            "created_at",
        ),
    )

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capability = Column(String(100), nullable=False)
    domain = Column(String(500), nullable=False)
    block_type = Column(String(50), nullable=False)
    screenshot_url = Column(String(2048), nullable=True)
    status = Column(
        ENUM("open", "resolved", "retry", name="anti_bot_escalation_status"),
        nullable=False,
        default="open",
        server_default="open",
    )
    detection_count = Column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # ``metadata`` is a reserved name on ``Base``, so the Python attribute is
    # ``escalation_metadata`` while the database column keeps the requested
    # ``metadata`` name.
    escalation_metadata = Column("metadata", JSONB, nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    run = relationship("Run")
    workspace = relationship("Workspace")


class ToolOutputSpill(Base, TimestampMixin):
    """Internal scratch store for main-agent context-editing spills.

    Kept separate from ``runs`` so customer-facing scraper logs stay clean.
    The full ``ToolMessage`` content that context editing evicts is written here
    and the message body is replaced with a ``spill_{id}`` placeholder the agent
    can read back via ``read_run``/``search_run``. Retained ~7 days.
    """

    __tablename__ = "tool_output_spills"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    thread_id = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)


# Register model packages that live outside this file so their classes
# are present in Base.metadata before configure_mappers() resolves any
# string-based relationship() references.
from app.automations.persistence import (  # noqa: F401
    Automation,
    AutomationRun,
    AutomationTrigger,
    Playbook,
)
from app.etl_pipeline.cache.persistence.models import CachedParse  # noqa: F401
from app.file_storage.persistence import DocumentFile  # noqa: F401
from app.indexing_pipeline.cache.persistence.models import (  # noqa: F401
    CachedEmbeddingSet,
)
from app.notifications.persistence import Notification  # noqa: F401
from app.podcasts.persistence import (  # noqa: F401
    Podcast,
    PodcastStatus,
)


def _build_connect_args() -> dict:
    """Build driver connect_args, including a protective idle-in-transaction
    timeout for asyncpg connections.

    A single abandoned ``idle in transaction`` session can hold table/row locks
    indefinitely and wedge writes plus boot-time DDL (the classic "FastAPI
    stuck at application startup" failure). Setting
    ``idle_in_transaction_session_timeout`` server-side makes Postgres reap such
    sessions automatically. It never affects sessions that are actively running
    statements — only ones that opened a transaction and went idle.
    """
    connect_args: dict = {}
    idle_ms = config.DB_IDLE_IN_TX_TIMEOUT_MS
    # ``server_settings`` is asyncpg-specific; only apply it for that driver.
    if idle_ms and idle_ms > 0 and DATABASE_URL and "asyncpg" in DATABASE_URL:
        connect_args["server_settings"] = {
            "idle_in_transaction_session_timeout": str(idle_ms)
        }
    return connect_args


engine = create_async_engine(
    DATABASE_URL,
    pool_size=30,
    max_overflow=150,
    pool_recycle=1800,
    pool_pre_ping=True,
    pool_timeout=30,
    connect_args=_build_connect_args(),
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def shielded_async_session():
    """Cancellation-safe async session context manager.

    Starlette's BaseHTTPMiddleware cancels the task via an anyio cancel
    scope when a client disconnects.  A plain ``async with async_session_maker()``
    has its ``__aexit__`` (which awaits ``session.close()``) cancelled by the
    scope, orphaning the underlying database connection.

    This wrapper ensures ``session.close()`` always completes by running it
    inside ``anyio.CancelScope(shield=True)``.
    """
    session = async_session_maker()
    try:
        yield session
    finally:
        with anyio.CancelScope(shield=True):
            await session.close()


# (index_name, table, CREATE statement). Built with CONCURRENTLY so an index
# build only takes a non-blocking ShareUpdateExclusiveLock — ingestion
# INSERT/UPDATE on documents/chunks keep flowing while the index builds, and a
# slow build can never freeze the FastAPI lifespan or block writers.
_INDEX_DEFINITIONS: list[tuple[str, str, str]] = [
    (
        "document_vector_index",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS document_vector_index ON documents USING hnsw (embedding public.vector_cosine_ops)",
    ),
    (
        "document_search_index",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS document_search_index ON documents USING gin (to_tsvector('english', content))",
    ),
    (
        "chucks_vector_index",
        "chunks",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS chucks_vector_index ON chunks USING hnsw (embedding public.vector_cosine_ops)",
    ),
    (
        "chucks_search_index",
        "chunks",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS chucks_search_index ON chunks USING gin (to_tsvector('english', content))",
    ),
    # pg_trgm index for efficient ILIKE '%term%' searches on titles — critical
    # for the document mention picker (@mentions) to scale.
    (
        "idx_documents_title_trgm",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops)",
    ),
    (
        "idx_documents_workspace_id",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_workspace_id ON documents (workspace_id)",
    ),
    # Covering index for "recent documents" query — enables index-only scan.
    (
        "idx_documents_workspace_updated",
        "documents",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_workspace_updated ON documents (workspace_id, updated_at DESC NULLS LAST) INCLUDE (id, title, document_type)",
    ),
]


async def _drop_invalid_index(conn, name: str) -> None:
    """Drop a leftover *invalid* index so it can be rebuilt.

    A ``CREATE INDEX CONCURRENTLY`` that is interrupted (timeout, crash,
    cancellation) leaves behind an ``indisvalid = false`` index. Because the
    name now exists, a later ``CREATE INDEX CONCURRENTLY IF NOT EXISTS`` would
    skip it and the broken index would persist forever. Detect and drop it
    first.
    """
    result = await conn.execute(
        text("SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:n)"),
        {"n": name},
    )
    row = result.first()
    if row is not None and row[0] is False:
        logger.warning(
            "[startup] dropping invalid leftover index %s before rebuild", name
        )
        await conn.execute(text(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"'))


async def setup_indexes() -> None:
    """Ensure search/vector indexes exist without ever blocking startup.

    Each index is created with ``CONCURRENTLY`` (so it never takes a blocking
    SHARE lock on documents/chunks) under a short per-session ``lock_timeout``
    (so a contended boot fails fast instead of hanging the lifespan forever).
    Failures are logged and swallowed per-index — a missing index just gets
    retried on the next boot rather than crash-looping the API.
    """
    lock_timeout_ms = int(config.DB_DDL_LOCK_TIMEOUT_MS)
    # AUTOCOMMIT is mandatory: CREATE INDEX CONCURRENTLY cannot run inside a
    # transaction block.
    async with engine.connect() as base_conn:
        conn = await base_conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"SET lock_timeout = {lock_timeout_ms}"))
        for name, table, ddl in _INDEX_DEFINITIONS:
            try:
                await _drop_invalid_index(conn, name)
                await conn.execute(text(ddl))
            except Exception as exc:
                # Non-fatal by design: a missing index is retried next boot.
                logger.warning(
                    "[startup] index %s on %s not ready (%s: %s); "
                    "will retry on next boot",
                    name,
                    table,
                    exc.__class__.__name__,
                    exc,
                )


async def create_db_and_tables():
    if not config.DB_BOOTSTRAP_ON_STARTUP:
        logger.info(
            "[startup] DB bootstrap skipped (DB_BOOTSTRAP_ON_STARTUP=FALSE); "
            "schema/indexes are expected to be managed by migrations"
        )
        return

    lock_timeout_ms = int(config.DB_DDL_LOCK_TIMEOUT_MS)
    async with engine.begin() as conn:
        # Fail fast instead of hanging forever if another session holds a
        # conflicting lock on a table we need to touch.
        await conn.execute(text(f"SET LOCAL lock_timeout = {lock_timeout_ms}"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.warning(
                f"[startup] Base.metadata.create_all encountered error (managed by Alembic): {exc}"
            )
        from app.zero_publication import ensure_publication

        try:
            await conn.run_sync(ensure_publication)
        except Exception as exc:
            logger.warning(f"[startup] ensure_publication encountered error: {exc}")
    await setup_indexes()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


if config.AUTH_TYPE == "GOOGLE":

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

else:

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User)


def has_permission(user_permissions: list[str], required_permission: str) -> bool:
    """
    Check if the user has the required permission.
    Supports wildcard (*) for full access.

    Args:
        user_permissions: List of permission strings the user has
        required_permission: The permission string to check for

    Returns:
        True if user has the permission, False otherwise
    """
    if not user_permissions:
        return False

    # Full access wildcard grants all permissions
    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return required_permission in user_permissions


def has_any_permission(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """
    Check if the user has any of the required permissions.

    Args:
        user_permissions: List of permission strings the user has
        required_permissions: List of permission strings to check for (any match)

    Returns:
        True if user has at least one of the permissions, False otherwise
    """
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return any(perm in user_permissions for perm in required_permissions)


def has_all_permissions(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """
    Check if the user has all of the required permissions.

    Args:
        user_permissions: List of permission strings the user has
        required_permissions: List of permission strings to check for (all must match)

    Returns:
        True if user has all of the permissions, False otherwise
    """
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return all(perm in user_permissions for perm in required_permissions)


def get_default_roles_config() -> list[dict]:
    """
    Get the configuration for default system roles.
    These roles are created automatically when a workspace is created.

    Only 3 roles are supported:
    - Owner: Full access to everything (assigned to workspace creator)
    - Editor: Can create/update content but cannot delete, manage roles, or change settings
    - Viewer: Read-only access to resources (can add comments)

    Returns:
        List of role configurations with name, description, permissions, and flags
    """
    return [
        {
            "name": "Owner",
            "description": "Full access to all workspace resources and settings",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Owner"],
            "is_default": False,
            "is_system_role": True,
        },
        {
            "name": "Editor",
            "description": "Can create and update content (no delete, role management, or settings access)",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Editor"],
            "is_default": True,  # Default role for new members via invite
            "is_system_role": True,
        },
        {
            "name": "Viewer",
            "description": "Read-only access to workspace resources",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Viewer"],
            "is_default": False,
            "is_system_role": True,
        },
    ]


# ============================================================================
# Canonical entity persistence (Story 13.1)
# ============================================================================


class EmbeddingStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class PersistOutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    DONE = "done"


class CanonicalEntity(Base, TimestampMixin):
    """Merged, tenant-scoped canonical entity with provenance and embedding."""

    __tablename__ = "canonical_entities"
    __allow_unmapped__ = True

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "entity_type",
            "fingerprint",
            name="uq_canonical_entities_workspace_type_fingerprint",
        ),
        Index(
            "ix_canonical_entities_workspace_type_last_seen",
            "workspace_id",
            "entity_type",
            "last_seen_at",
            postgresql_using="btree",
        ),
        Index(
            "ix_canonical_entities_search_text",
            text("to_tsvector('simple', search_text)"),
            postgresql_using="gin",
        ),
        Index(
            "ix_canonical_entities_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("embedding IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = Column(String(64), nullable=False)
    canonical_title = Column(String(500), nullable=True)
    canonical_data = Column(JSONB, nullable=False, default=dict)
    fingerprint = Column(String(255), nullable=False)
    search_text = Column(Text, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    confidence_score = Column(Float, nullable=False, default=0.0)
    conflict_flags = Column(JSONB, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_seen_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    embedding = Column(Vector(config.embedding_model_instance.dimension), nullable=True)
    embedding_model_name = Column(String(255), nullable=True)
    embedding_content_hash = Column(String(64), nullable=True)
    embedding_status = Column(
        String(16),
        nullable=False,
        default=EmbeddingStatus.PENDING.value,
        server_default=EmbeddingStatus.PENDING.value,
    )

    sources = relationship(
        "CanonicalEntitySource",
        back_populates="canonical_entity",
        cascade="all, delete-orphan",
        order_by="CanonicalEntitySource.last_seen_at.desc()",
    )
    merge_history = relationship(
        "CanonicalMergeHistory",
        back_populates="canonical_entity",
        cascade="all, delete-orphan",
        order_by="CanonicalMergeHistory.created_at.desc()",
    )


class CanonicalEntitySource(Base, TimestampMixin):
    """One source record contributing to a canonical entity."""

    __tablename__ = "canonical_entity_sources"
    __allow_unmapped__ = True

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "entity_type",
            "source_name",
            "source_record_id",
            name="uq_canonical_entity_sources_workspace_type_source_record",
        ),
        Index(
            "ix_canonical_entity_sources_canonical_entity_id",
            "canonical_entity_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = Column(String(64), nullable=False)
    source_name = Column(String(64), nullable=False)
    source_record_id = Column(String(255), nullable=False)
    source_snapshot = Column(JSONB, nullable=False, default=dict)
    source_url = Column(Text, nullable=True)
    source_fingerprint = Column(String(255), nullable=True)
    first_seen_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_seen_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    canonical_entity = relationship("CanonicalEntity", back_populates="sources")


class CanonicalMergeHistory(Base):
    """Audit trail of canonical entity merges and reverts."""

    __tablename__ = "canonical_merge_history"
    __allow_unmapped__ = True

    __table_args__ = (
        Index(
            "ix_canonical_merge_history_entity_created",
            "canonical_entity_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = Column(String(64), nullable=False)
    previous_version = Column(Integer, nullable=False)
    new_version = Column(Integer, nullable=False)
    previous_data = Column(JSONB, nullable=False, default=dict)
    new_data = Column(JSONB, nullable=False, default=dict)
    previous_source_ids = Column(JSONB, nullable=False, default=list)
    new_source_ids = Column(JSONB, nullable=False, default=list)
    operation = Column(String(64), nullable=False)
    actor = Column(String(255), nullable=True)
    conflicts = Column(JSONB, nullable=False, default=list)
    method = Column(String(64), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    canonical_entity = relationship("CanonicalEntity", back_populates="merge_history")


class CanonicalPersistOutbox(Base):
    """Durable outbox for canonical persistence retries."""

    __tablename__ = "canonical_persist_outbox"
    __allow_unmapped__ = True

    __table_args__ = (
        Index(
            "ix_canonical_persist_outbox_status_next_attempt",
            "status",
            "next_attempt_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(
        String(16),
        nullable=False,
        default=PersistOutboxStatus.PENDING.value,
        server_default=PersistOutboxStatus.PENDING.value,
    )
    retry_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
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


class BillingEvent(Base, TimestampMixin):
    """Canonical ledger for non-LLM business events (e.g. signal scans)."""

    __tablename__ = "billing_events"

    __table_args__ = (
        Index(
            "ix_billing_events_event_lookup",
            "event_entity_type",
            "event_type",
            "event_id",
        ),
        Index(
            "ix_billing_events_outcome_unique",
            "event_id",
            unique=True,
            postgresql_where=text(
                "event_entity_type = 'outcome_event' AND event_type = 'outcome'"
            ),
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
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_entity_type = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), nullable=False)
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    cost_basis = Column(
        String(20), nullable=False, default="estimated", server_default="estimated"
    )

    workspace = relationship("Workspace")
    user = relationship("User")


class Lead(Base, TimestampMixin):
    """A lead record imported or created for outbound prospecting (Story 21.2)."""

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
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
    status = Column(String(50), nullable=False, default="new", server_default="new")
    enriched = Column(Boolean, nullable=False, default=False, server_default="false")
    consent_status = Column(String(50), nullable=True)
    legal_basis = Column(String(50), nullable=True)

    workspace = relationship("Workspace", back_populates="leads")
    lead_scores = relationship(
        "LeadScore",
        back_populates="lead",
        order_by="LeadScore.computed_at.desc()",
        cascade="all, delete-orphan",
    )
    enrichment_requests = relationship(
        "EnrichmentRequest",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    verified_contacts = relationship(
        "VerifiedContact",
        back_populates="lead",
        cascade="all, delete-orphan",
    )


class LeadScore(Base, TimestampMixin):
    """Composite lead score snapshot (Story 21.2)."""

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
        ForeignKey("leads.id", ondelete="CASCADE"),
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
    lead = relationship("Lead", back_populates="lead_scores")
    previous_score = relationship(
        "LeadScore",
        remote_side=[id],
        uselist=False,
    )


class EnrichmentRequest(Base, TimestampMixin):
    """A contact-enrichment request and its lifecycle (Story 21.3, AC-3).

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
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    provider_results = Column(
        JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    cost_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    contact_count = Column(Integer, nullable=False, default=0, server_default="0")
    requested_count = Column(
        Integer, nullable=False, default=5, server_default="5"
    )

    workspace = relationship("Workspace", back_populates="enrichment_requests")
    lead = relationship("Lead", back_populates="enrichment_requests")
    contacts = relationship(
        "VerifiedContact",
        back_populates="enrichment_request",
        cascade="all, delete-orphan",
    )


class VerifiedContact(Base, TimestampMixin):
    """A verified contact discovered by enrichment (Story 21.3, AC-3).

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
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrichment_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enrichment_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=True)
    title = Column(String(200), nullable=True)
    email = Column(CITEXT, nullable=False, index=True)
    phone = Column(String(200), nullable=True)
    verification_status = Column(
        String(20), nullable=False, default="unverified", server_default="unverified"
    )
    confidence = Column(Float, nullable=False, default=0.0, server_default="0")
    source_provider = Column(
        String(20), nullable=False, default="fallback", server_default="fallback"
    )
    consent = Column(Boolean, nullable=False, default=False, server_default="false")
    consent_status = Column(String(50), nullable=True)
    legal_basis = Column(String(50), nullable=True)

    workspace = relationship("Workspace", back_populates="verified_contacts")
    lead = relationship("Lead", back_populates="verified_contacts")
    enrichment_request = relationship(
        "EnrichmentRequest", back_populates="contacts"
    )


# Ensure alert persistence models are registered on Base.metadata.
# ruff: noqa: I001,E402
from app.alerts.persistence.models.alert_rule import AlertRule  # noqa: F401
from app.alerts.persistence.models.alert_snapshot import AlertSnapshot  # noqa: F401
from app.alerts.persistence.models.alert_subscription import AlertSubscription  # noqa: F401
from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone  # noqa: F401



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
    platform = Column(String(50), nullable=False)  # 'facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'
    target_id = Column(String(255), nullable=False)
    target_name = Column(Text, nullable=False)
    target_url = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="general", server_default=text("'general'"))
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    realtime_stream = Column(Boolean, nullable=False, default=False, server_default="false")
    # scrape_interval_minutes is the canonical scrape/poll cadence. The legacy
    # poll_interval_seconds concept maps to scrape_interval_minutes * 60.
    scrape_interval_minutes = Column(Integer, nullable=False, default=15, server_default="15")
    status = Column(String(50), nullable=False, default="active", server_default=text("'active'"))
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
        Index("idx_social_posts_platform_intent_published", "platform", "intent_tag", "published_at"),
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
    intent_tag = Column(String(50), nullable=True)  # 'sell', 'buy', 'hiring', 'seeking', 'news', 'other'
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



