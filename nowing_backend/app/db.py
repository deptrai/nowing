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
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, JSONB, TSVECTOR, UUID
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


class MeetingMinutesStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DEGRADED = "degraded"
    VALIDATION_FAILED = "validation_failed"


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

    # DSH missions (Story 26.2)
    DSH_MISSIONS_READ = "dsh_missions:read"
    DSH_MISSIONS_WRITE = "dsh_missions:write"

    # Full access wildcard
    FULL_ACCESS = "*"

    # Web Builder (Story 27.1a)
    WEB_BUILDER_CREATE = "web_builder:create"


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
        # Web Builder (Story 27.1a)
        Permission.WEB_BUILDER_CREATE.value,
        # Memory (no delete)
        Permission.MEMORY_CREATE.value,
        Permission.MEMORY_READ.value,
        Permission.MEMORY_UPDATE.value,
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


class ScraperRule(Base, TimestampMixin):
    """Versioned, admin-managed rule schema for a scraper platform."""

    __tablename__ = "scraper_rules"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    rule_schema = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "platform", "version", name="uq_scraper_rules_platform_version"
        ),
        Index(
            "uq_scraper_rules_active_per_platform",
            "platform",
            unique=True,
            postgresql_where=text("is_active = true"),
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


class MeetingMinutes(BaseModel, TimestampMixin):
    """Meeting minutes model for storing AI-generated meeting minutes."""

    __tablename__ = "meeting_minutes"

    title = Column(String(500), nullable=True)
    status = Column(
        SQLAlchemyEnum(
            MeetingMinutesStatus,
            name="meeting_minutes_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MeetingMinutesStatus.PENDING,
        server_default="pending",
        index=True,
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace = relationship("Workspace", back_populates="meeting_minutes")

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    user = relationship("User")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document = relationship("Document")

    audio_source_url = Column(Text, nullable=True)
    processing_task_id = Column(String(255), nullable=True, index=True)

    transcript = Column(JSONB, nullable=True, default=list)
    action_items = Column(JSONB, nullable=True, default=list)
    summary = Column(Text, nullable=True)
    raw_transcript = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    meeting_metadata = Column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )


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
    __table_args__ = (
        Index(
            "ix_credit_purchases_status_completed_at",
            "status",
            "completed_at",
        ),
    )

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

    # Monthly spend cap and lead distribution settings (Story 24.3 / INV-24.4)
    monthly_spend_cap_micros = Column(BigInteger, nullable=True)
    monthly_spent_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    is_accepting_leads = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    lead_capacity = Column(Integer, nullable=False, default=50, server_default="50")
    status = Column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
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


class DshMissionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    DLQ = "dlq"


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
            postgresql_where=text("event_entity_type = 'outcome_event'"),
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


OutboundMessage = ZaloMessageLog


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


class PricingPlan(Base, TimestampMixin):
    """Workspace pricing plan configuration (seat, outcome, hybrid) (Story 21.7 / AD-42)."""

    __tablename__ = "pricing_plans"

    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_pricing_plans_workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(CITEXT, nullable=True, index=True)
    plan_type = Column(
        String(50), nullable=False, default="outcome", server_default="outcome"
    )  # seat | outcome | hybrid
    seat_price = Column(BigInteger, nullable=True)  # micros per seat
    outcome_rates_json = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    billing_period = Column(
        String(20), nullable=True, default="monthly", server_default="monthly"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    workspace = relationship("Workspace")


class PromoCode(Base, TimestampMixin):
    """Gift / promotional codes that grant credits to user wallets (Story 21.7 / AC-5)."""

    __tablename__ = "promo_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    credit_micros_granted = Column(BigInteger, nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, nullable=False, default=0, server_default="0")
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )


class PromoCodeRedemption(Base, TimestampMixin):
    """Tracks which users have redeemed which promo codes (Story 21.7 / AC-5)."""

    __tablename__ = "promo_code_redemptions"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "promo_code_id", name="uq_promo_code_redemption_user_code"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    promo_code_id = Column(
        UUID(as_uuid=True),
        ForeignKey("promo_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credit_micros_granted = Column(BigInteger, nullable=False)
    redeemed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    user = relationship("User")
    promo_code = relationship("PromoCode")


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


class AffiliatePartner(Base, TimestampMixin):
    """Affiliate Partner account for Nowing referral program (Story 21.18 / Story 23.3 / AD-44)."""

    __tablename__ = "affiliate_partners"
    __table_args__ = (
        UniqueConstraint("referral_code", name="uq_affiliate_partners_referral_code"),
        Index("ix_affiliate_partners_user_id", "user_id"),
        Index("ix_affiliate_partners_referral_code", "referral_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    referral_code = Column(CITEXT, nullable=False)
    partner_type = Column(
        String(50), nullable=False, default="agency", server_default=text("'agency'")
    )
    status = Column(
        String(30), nullable=False, default="active", server_default=text("'active'")
    )
    commission_rate = Column(Float, nullable=False, default=0.15, server_default="0.15")
    balance_micros = Column(BigInteger, nullable=False, default=0, server_default="0")
    hold_balance_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_earned_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    total_paid_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    payout_method = Column(
        String(30), nullable=False, default="vietqr", server_default=text("'vietqr'")
    )
    payout_details = Column(
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

    user = relationship("User")
    referrals = relationship(
        "PartnerReferral", back_populates="partner", cascade="all, delete-orphan"
    )
    commissions = relationship(
        "PartnerCommission", back_populates="partner", cascade="all, delete-orphan"
    )
    payouts = relationship(
        "PartnerPayout", back_populates="partner", cascade="all, delete-orphan"
    )

    @property
    def available_balance_micros(self) -> int:
        return self.balance_micros

    @available_balance_micros.setter
    def available_balance_micros(self, value: int) -> None:
        self.balance_micros = value


class PartnerReferral(Base, TimestampMixin):
    """Referred user attribution (Story 21.18)."""

    __tablename__ = "partner_referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_partner_referrals_referred_user"),
        Index("ix_partner_referrals_partner_id", "partner_id"),
        Index("ix_partner_referrals_referred_user_id", "referred_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    referred_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    attribution_source = Column(
        String(100),
        nullable=True,
        default="direct_ref",
        server_default=text("'direct_ref'"),
    )
    landing_page = Column(String(255), nullable=True)
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

    partner = relationship("AffiliatePartner", back_populates="referrals")
    referred_user = relationship("User")
    commissions = relationship(
        "PartnerCommission", back_populates="referral", cascade="all, delete-orphan"
    )


class PartnerCommission(Base, TimestampMixin):
    """Commission payout ledger event from user credit purchase (Story 21.18)."""

    __tablename__ = "partner_commissions"
    __table_args__ = (
        Index("ix_partner_commissions_partner_id", "partner_id"),
        Index("ix_partner_commissions_referral_id", "referral_id"),
        Index("ix_partner_commissions_credit_purchase_id", "credit_purchase_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    referral_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partner_referrals.id", ondelete="CASCADE"),
        nullable=False,
    )
    credit_purchase_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credit_purchases.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_amount_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    commission_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    commission_rate = Column(Float, nullable=False, default=0.15, server_default="0.15")
    currency = Column(
        String(10), nullable=False, default="USD", server_default=text("'USD'")
    )
    status = Column(
        String(20), nullable=False, default="settled", server_default=text("'settled'")
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

    partner = relationship("AffiliatePartner", back_populates="commissions")
    referral = relationship("PartnerReferral", back_populates="commissions")


class PartnerPayout(Base, TimestampMixin):
    """Partner payout request / transaction record (Story 21.18)."""

    __tablename__ = "partner_payouts"
    __table_args__ = (
        Index("ix_partner_payouts_partner_id", "partner_id"),
        Index("ix_partner_payouts_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_micros = Column(BigInteger, nullable=False)
    amount_vnd = Column(BigInteger, nullable=False, default=0, server_default="0")
    tax_deducted_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    net_amount_micros = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    tax_code = Column(String(50), nullable=True)
    payout_method = Column(
        String(30), nullable=False, default="vietqr", server_default=text("'vietqr'")
    )
    payout_details = Column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status = Column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    tx_reference = Column(String(100), nullable=True)
    napas_ref = Column(String(100), nullable=True)
    hmac_audit_hash = Column(String(128), nullable=True)
    requested_at = Column(TIMESTAMP(timezone=True), nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
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

    partner = relationship("AffiliatePartner", back_populates="payouts")


class AuditEvent(BaseModel, TimestampMixin):
    """Immutable dual-principal audit logging in audit_events."""

    __tablename__ = "audit_events"

    action = Column(String(100), nullable=False, index=True)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticket_ref = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    diff_payload = Column(JSONB, nullable=True)


class CreditTransaction(Base, TimestampMixin):
    """Immutable ledger for manual workspace credit adjustments."""

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    direction = Column(String(10), nullable=False)
    amount_micros = Column(BigInteger, nullable=False)
    reason = Column(Text, nullable=False)
    ticket_ref = Column(Text, nullable=False)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)


# ============================================================================
# Story 24.1: Sequence Bounded Context (AD-39, AD-41, AD-42, AD-43, AD-45)
# ============================================================================


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


class SlidePresentation(Base):
    """Generated PPTX or Marp Markdown slide deck for a workspace (Story 27.2a)."""

    __tablename__ = "slide_presentations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", name="uq_slide_presentations_workspace_slug"
        ),
        Index("ix_slide_presentations_workspace_status", "workspace_id", "status"),
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
    title = Column(String(255), nullable=False)
    slug = Column(String(63), nullable=False, index=True)
    format = Column(String(10), nullable=False, default="pptx")
    status = Column(
        String(50),
        nullable=False,
        default="generating",
        server_default=text("'generating'"),
    )  # generating, ready, failed, degraded, validation_failed
    file_path = Column(String(512), nullable=True)
    preview_url = Column(String(512), nullable=True)
    slide_count = Column(Integer, nullable=True)
    degradation_reason = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
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

    @property
    def download_url(self) -> str | None:
        """Public download URL for the generated deck."""
        if not self.file_path:
            return None
        return (
            f"{config.BACKEND_URL.rstrip('/')}/api/v1/presentations/{self.id}"
            f"/download?workspace_id={self.workspace_id}"
        )

    workspace = relationship("Workspace", backref="slide_presentations")
    user = relationship("User", backref="slide_presentations")


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
