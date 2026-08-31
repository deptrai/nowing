"""Enums, status helpers, and shared constants used across the ORM models.

These were originally part of ``app/db.py`` and are kept in one place so that
models in ``app.models.*`` can import them without pulling in the full SQLAlchemy
model graph.
"""

from __future__ import annotations

from enum import StrEnum

NATIVE_TO_LEGACY_DOCTYPE: dict[str, str] = {
    "GOOGLE_DRIVE_FILE": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "COMPOSIO_GMAIL_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}


def _enum_values(enum_cls):
    """Return enum values as a list for SQLAlchemy ENUM values_callable."""
    return [item.value for item in enum_cls]
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


class InboundEmailEventStatus(StrEnum):
    """Lifecycle of an inbound email received through the gateway."""

    RECEIVED = "received"
    PARSED = "parsed"
    MISSION_CREATED = "mission_created"
    REPLIED = "replied"
    REPLIED_FAILED = "replied_failed"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    MANUAL_REVIEW = "manual_review"


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


class PagePurchaseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class CreditPurchaseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


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


class PromptMode(StrEnum):
    transform = "transform"
    explore = "explore"


class DshMissionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    DLQ = "dlq"