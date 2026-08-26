"""Schemas for In-App Broadcast Announcements (Story 25.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

BannerType = Literal["info", "warning", "maintenance", "promo"]
BroadcastStatus = Literal["active", "scheduled", "expired", "inactive"]


class BroadcastCreate(BaseModel):
    """Payload to create a new broadcast announcement."""

    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)
    banner_type: BannerType = Field(default="info")
    target_all: bool = Field(default=True)
    target_workspace_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list, max_length=100
    )
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    dismissible: bool = Field(default=True)
    is_active: bool = Field(default=True)


class BroadcastUpdate(BaseModel):
    """Payload to update an existing broadcast announcement."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    message: str | None = Field(default=None, min_length=1, max_length=5000)
    banner_type: BannerType | None = None
    target_all: bool | None = None
    target_workspace_ids: list[Annotated[int, Field(gt=0)]] | None = Field(
        default=None, max_length=100
    )
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    dismissible: bool | None = None
    is_active: bool | None = None


class BroadcastRead(BaseModel):
    """Admin representation of a broadcast announcement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    message: str
    banner_type: str
    target_all: bool
    target_workspace_ids: list[int]
    starts_at: datetime
    expires_at: datetime | None = None
    dismissible: bool
    is_active: bool
    status: BroadcastStatus
    created_by_user_id: uuid.UUID | None = None
    updated_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class BroadcastListResponse(BaseModel):
    """List response for broadcast announcements."""

    items: list[BroadcastRead]
    total: int


class BroadcastActiveRead(BaseModel):
    """Public read representation for active broadcast banners mounted in UI."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    message: str
    banner_type: str
    dismissible: bool
