"""Database public API.

This package is the canonical source for ``Base``, ``BaseModel``,
``TimestampMixin``, session helpers, and all SQLAlchemy ORM models.

For backwards compatibility, ``from app.db import X`` continues to work, where
``X`` is any public class previously exported from ``app/db.py``.
"""

from __future__ import annotations

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db.base import (
    DATABASE_URL,
    Base,
    BaseModel,
    TimestampMixin,
    async_session_maker,
    create_db_and_tables,
    engine,
    get_async_session,
    setup_indexes,
    shielded_async_session,
)

# Enums and shared constants
from app.db.enums import (
    DEFAULT_ROLE_PERMISSIONS,
    INCENTIVE_TASKS_CONFIG,
    NATIVE_TO_LEGACY_DOCTYPE,
    ChatVisibility,
    ConnectionScope,
    CreditPurchaseStatus,
    DocumentRetentionAction,
    DocumentStatus,
    DocumentType,
    DshMissionStatus,
    ExternalChatAccountMode,
    ExternalChatBindingState,
    ExternalChatEventKind,
    ExternalChatEventStatus,
    ExternalChatHealthStatus,
    ExternalChatPeerKind,
    ExternalChatPlatform,
    IncentiveTaskType,
    LogLevel,
    LogStatus,
    MeetingMinutesStatus,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    ModelSource,
    NewChatMessageRole,
    PagePurchaseStatus,
    Permission,
    PromptMode,
    SearchSourceConnectorType,
    VideoPresentationStatus,
    _enum_values,
)

# User database helper (conditional on AUTH_TYPE)
if config.AUTH_TYPE == "GOOGLE":

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

else:

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User)


# Permissions helpers
from app.db.permissions import (
    get_default_roles_config,
    has_all_permissions,
    has_any_permission,
    has_permission,
)

# Domain models (re-exported for backwards compatibility)
from app.models.billing import (
    AffiliatePartner,
    AuditEvent,
    BillingEvent,
    CreditPurchase,
    CreditTransaction,
    PagePurchase,
    PartnerCommission,
    PartnerPayout,
    PartnerReferral,
    PricingPlan,
    PromoCode,
    PromoCodeRedemption,
    TokenUsage,
    UserIncentiveTask,
)
from app.models.chat import (
    ChatComment,
    ChatCommentMention,
    ChatSessionState,
    ExternalChatAccount,
    ExternalChatBinding,
    ExternalChatInboundEvent,
    NewChatMessage,
    NewChatThread,
    PublicChatSnapshot,
)
from app.models.connectors import Connection, Log, SearchSourceConnector
from app.models.documents import (
    ChainLensChunk,
    Chunk,
    Document,
    DocumentRevision,
    DocumentVersion,
    Folder,
    FolderRevision,
)
from app.models.leads import (
    ChainLensIngestJob,
    CompanyDecisionMaker,
    CrmConnection,
    CrmSyncLog,
    DshMission,
    EnrichmentRequest,
    ExportJob,
    Lead,
    LeadActivityLog,
    LeadAssignment,
    LeadPipelineStage,
    LeadScore,
    LinkedinCompany,
    LinkedinJob,
    OutcomeEvent,
    PhoneWaterfallLog,
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceRun,
    SequenceStep,
    SignalEvent,
    SignalSubscription,
    SocialMonitoredTarget,
    SocialPost,
    TelegramCheckpointMessage,
    VerifiedContact,
    ZaloConnection,
    ZaloMessageLog,
)
from app.models.memory import (
    AgentActionLog,
    AgentConfig,
    AgentPermissionRule,
    ImageGeneration,
    Memory,
    MemoryRelation,
    MemoryVersion,
    Model,
    Prompt,
)
from app.models.presentations import (
    MeetingMinutes,
    Report,
    SlidePresentation,
    VideoPresentation,
)
from app.models.scraper import (
    AntiBotEscalation,
    Run,
    ScraperPlatformAccount,
    ScraperRule,
    ToolOutputSpill,
)

# Users / RBAC (conditional OAuthAccount + User)
if config.AUTH_TYPE == "GOOGLE":
    from app.models.users import (
        OAuthAccount,
        PersonalAccessToken,
        RefreshToken,
        User,
        WorkspaceInvite,
        WorkspaceMembership,
        WorkspaceRole,
    )
else:
    from app.models.users import (
        PersonalAccessToken,
        RefreshToken,
        User,
        WorkspaceInvite,
        WorkspaceMembership,
        WorkspaceRole,
    )
# External persistence models (registered directly to Base.metadata without
# passing through app.models to avoid circular imports).
from app.alerts.persistence.models import AlertRule, AlertSnapshot, AlertSubscription
from app.automations.persistence import (
    Automation,
    AutomationRun,
    AutomationTrigger,
    Playbook,
)
from app.etl_pipeline.cache.persistence.models import CachedParse
from app.file_storage.persistence import DocumentFile
from app.indexing_pipeline.cache.persistence.models import CachedEmbeddingSet
from app.models.workspaces import (
    BroadcastAnnouncement,
    GlobalDncRecord,
    ResearchThread,
    VerticalClient,
    Workspace,
    WorkspaceApp,
    WorkspaceDncRecord,
    WorkspaceLimit,
    WorkspaceMcpToolSetting,
    WorkspaceTable,
)
from app.notifications.persistence import Notification
from app.podcasts.persistence import Podcast, PodcastStatus
from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone

__all__ = [
    "DATABASE_URL",
    # enums
    "DEFAULT_ROLE_PERMISSIONS",
    "INCENTIVE_TASKS_CONFIG",
    "NATIVE_TO_LEGACY_DOCTYPE",
    "AffiliatePartner",
    "AgentActionLog",
    "AgentConfig",
    "AgentPermissionRule",
    "AlertRule",
    "AlertSnapshot",
    "AlertSubscription",
    "AntiBotEscalation",
    "AuditEvent",
    "Automation",
    "AutomationRun",
    "AutomationTrigger",
    # base
    "Base",
    "BaseModel",
    "BillingEvent",
    "BroadcastAnnouncement",
    "CachedEmbeddingSet",
    "CachedParse",
    "ChainLensChunk",
    "ChainLensIngestJob",
    "ChatComment",
    "ChatCommentMention",
    "ChatSessionState",
    "ChatVisibility",
    "Chunk",
    "CompanyDecisionMaker",
    "Connection",
    "ConnectionScope",
    "CreditPurchase",
    "CreditPurchaseStatus",
    "CreditTransaction",
    "CrmConnection",
    "CrmSyncLog",
    "Document",
    "DocumentFile",
    "DocumentRetentionAction",
    "DocumentRevision",
    "DocumentStatus",
    "DocumentType",
    "DocumentVersion",
    "DshMission",
    "DshMissionStatus",
    "EnrichmentRequest",
    "ExportJob",
    "ExternalChatAccount",
    "ExternalChatAccountMode",
    "ExternalChatBinding",
    "ExternalChatBindingState",
    "ExternalChatEventKind",
    "ExternalChatEventStatus",
    "ExternalChatHealthStatus",
    "ExternalChatInboundEvent",
    "ExternalChatPeerKind",
    "ExternalChatPlatform",
    "Folder",
    "FolderRevision",
    "GlobalDncRecord",
    "ImageGeneration",
    "IncentiveTaskType",
    "Lead",
    "LeadActivityLog",
    "LeadAssignment",
    "LeadPipelineStage",
    "LeadScore",
    "LinkedinCompany",
    "LinkedinJob",
    "Log",
    "LogLevel",
    "LogStatus",
    "MeetingMinutes",
    "MeetingMinutesStatus",
    "Memory",
    "MemoryRelation",
    "MemoryRelationType",
    "MemorySourceType",
    "MemoryType",
    "MemoryVersion",
    "Model",
    "ModelSource",
    "NewChatMessage",
    "NewChatMessageRole",
    "NewChatThread",
    "Notification",
    "OAuthAccount",
    "OutcomeEvent",
    "PagePurchase",
    "PagePurchaseStatus",
    "PartnerCommission",
    "PartnerPayout",
    "PartnerReferral",
    "Permission",
    "PersonalAccessToken",
    "PhoneWaterfallLog",
    "Playbook",
    "Podcast",
    "PodcastStatus",
    "PricingPlan",
    "PromoCode",
    "PromoCodeRedemption",
    "Prompt",
    "PromptMode",
    "PublicChatSnapshot",
    "RefreshToken",
    "Report",
    "ResearchThread",
    "Run",
    "ScraperPlatformAccount",
    "ScraperRule",
    "SearchSourceConnector",
    "SearchSourceConnectorType",
    "Sequence",
    "SequenceEnrollment",
    "SequenceEvent",
    "SequenceRun",
    "SequenceStep",
    "SignalEvent",
    "SignalSubscription",
    "SlidePresentation",
    "SocialMonitoredTarget",
    "SocialPost",
    "SpatialPlanningZone",
    "TelegramCheckpointMessage",
    "TimestampMixin",
    "TokenUsage",
    "ToolOutputSpill",
    "User",
    "UserIncentiveTask",
    "VerifiedContact",
    "VerticalClient",
    "VideoPresentation",
    "VideoPresentationStatus",
    "Workspace",
    "WorkspaceApp",
    "WorkspaceDncRecord",
    "WorkspaceInvite",
    "WorkspaceLimit",
    "WorkspaceMcpToolSetting",
    "WorkspaceMembership",
    "WorkspaceRole",
    "WorkspaceTable",
    "ZaloConnection",
    "ZaloMessageLog",
    "_enum_values",
    "async_session_maker",
    "create_db_and_tables",
    "engine",
    "get_async_session",
    "get_default_roles_config",
    "has_all_permissions",
    "has_any_permission",
    "has_permission",
    "setup_indexes",
    "shielded_async_session",
]
