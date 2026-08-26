"""Schemas for Superadmin Global DNC Blacklist Management (Story 25.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GlobalDncRecordCreate(BaseModel):
    """Payload to add a single global DNC entry."""

    record_type: Literal["phone", "domain", "email", "tax_id"]
    value: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(default="Opt-out requested", max_length=255)
    source: str = Field(default="admin_manual", max_length=50)


class GlobalDncRecordRead(BaseModel):
    """Read representation of a global DNC blacklist entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_type: str
    value: str | None = None
    value_hmac: str
    reason: str | None = None
    source: str
    created_at: datetime

    @field_validator("value", mode="before")
    @classmethod
    def _mask_domain_value(cls, v: str | None, info) -> str | None:
        if v and info.data.get("record_type") == "domain" and "." in v:
            parts = v.split(".")
            # Mask the last label of the public suffix: e.g. example.com -> example.***
            if len(parts) > 1:
                parts[-1] = "***"
            return ".".join(parts)
        return v


class GlobalDncRecordListResponse(BaseModel):
    """Paginated list of global DNC records."""

    items: list[GlobalDncRecordRead]
    total: int
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class GlobalDncCsvImportResponse(BaseModel):
    """Summary of bulk CSV import operation."""

    imported_count: int
    skipped_count: int
    failed_count: int
    errors: list[str] = Field(default_factory=list)
