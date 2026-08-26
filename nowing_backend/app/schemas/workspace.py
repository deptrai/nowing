import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .base import IDModel, TimestampModel
from .model_connections import LlmSetupStatusRead

WorkspaceVertical = Literal["general", "real_estate", "auto", "b2b_equipment"]


class WorkspaceBase(BaseModel):
    name: str
    description: str | None = None
    vertical: WorkspaceVertical = "general"


class WorkspaceCreate(WorkspaceBase):
    citations_enabled: bool = True
    qna_custom_instructions: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    vertical: WorkspaceVertical | None = None
    citations_enabled: bool | None = None
    qna_custom_instructions: str | None = None
    document_retention_days: int | None = None
    auto_archive_enabled: bool | None = None
    document_retention_action: Literal["archive", "delete"] | None = None
    memory_retention_days: int | None = None
    memory_auto_archive_enabled: bool | None = None
    memory_retention_action: Literal["archive", "delete"] | None = None
    memory_auto_extract_enabled: bool | None = None
    auto_reply_enabled: bool | None = None
    auto_reply_collections: list[int] | None = None
    auto_reply_fallback: str | None = None
    auto_reply_recipient_chat_id: str | None = None


class WorkspaceApiAccessUpdate(BaseModel):
    api_access_enabled: bool


class WorkspaceRead(WorkspaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID
    citations_enabled: bool
    api_access_enabled: bool = False
    qna_custom_instructions: str | None = None
    document_retention_days: int | None = None
    auto_archive_enabled: bool = False
    document_retention_action: str = "archive"
    memory_retention_days: int | None = None
    memory_auto_archive_enabled: bool = False
    memory_retention_action: str = "archive"
    memory_auto_extract_enabled: bool = True
    auto_reply_enabled: bool = False
    auto_reply_collections: list[int] = []
    auto_reply_fallback: str | None = None
    auto_reply_recipient_chat_id: str | None = None
    is_owner: bool = False
    # Populated only by create_workspace so the client can route straight to
    # onboarding vs. new-chat on the first hop. Null everywhere else.
    llm_setup: LlmSetupStatusRead | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkspaceWithStats(WorkspaceRead):
    """Extended workspace info with member count and ownership status."""

    member_count: int = 1
    is_owner: bool = False


class WorkspaceMcpToolRead(BaseModel):
    name: str
    enabled: bool
    is_system: bool
    group: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMcpToolUpdate(BaseModel):
    enabled: StrictBool


class WorkspaceLimitUsage(BaseModel):
    documents: int
    members: int
    runs: int
    storage_bytes: int
    memory_count: int = 0
    memory_bytes: int = 0


class AutoExtractUsage(BaseModel):
    period_spend_micros: int
    period_count: int
    period_window_hours: int


class WorkspaceLimitsResponse(BaseModel):
    """Effective limits and current usage for a workspace."""

    plan_tier: str | None
    max_documents: int | None
    max_members: int | None
    max_runs: int | None
    max_storage_bytes: int | None
    max_memory_count: int | None = None
    max_memory_bytes: int | None = None
    run_period_hours: int
    # Story 8.14: auto-extract budget caps.
    auto_extract_item_cap: int | None = None
    auto_extract_spend_cap_micros: int | None = None
    auto_extract_wallet_pre_check: bool | None = None
    # Story 14.2a: news entity extraction caps.
    news_entity_extraction_item_cap: int | None = None
    news_entity_extraction_spend_cap_micros: int | None = None
    news_entity_extraction_wallet_pre_check: bool | None = None
    auto_extract_usage: AutoExtractUsage
    usage: WorkspaceLimitUsage


class WorkspaceLimitUpdate(BaseModel):
    """Owner-editable workspace limit overrides."""

    max_memory_count: int | None = Field(default=None, ge=0)
    max_memory_bytes: int | None = Field(default=None, ge=0)
    auto_extract_item_cap: int | None = Field(default=None, ge=0)
    auto_extract_spend_cap_micros: int | None = Field(default=None, ge=0)
    auto_extract_wallet_pre_check: bool | None = None
    news_entity_extraction_item_cap: int | None = Field(default=None, ge=0)
    news_entity_extraction_spend_cap_micros: int | None = Field(default=None, ge=0)
    news_entity_extraction_wallet_pre_check: bool | None = None
