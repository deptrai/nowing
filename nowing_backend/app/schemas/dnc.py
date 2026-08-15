"""Pydantic schemas for DNC & Compliance Engine (Story 21.14)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DncRecordType = Literal["phone", "email", "domain", "tax_id"]


class DncRecordCreate(BaseModel):
    """Payload to add a single contact identifier to the DNC blacklist."""

    record_type: DncRecordType = Field(..., description="Type of contact identifier")
    value: str = Field(
        ..., min_length=1, max_length=255, description="Phone, email, domain or tax ID"
    )
    reason: str | None = Field(
        default="Opt-out requested", max_length=255, description="Reason for exclusion"
    )


class DncRecordRead(BaseModel):
    """Schema for returning a DNC record to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    record_type: str
    value: str | None
    value_hmac: str
    reason: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class DncListResponse(BaseModel):
    """Paginated list of DNC records."""

    records: list[DncRecordRead] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 50


class DncCsvImportResponse(BaseModel):
    """Response returned upon bulk CSV upload."""

    imported_count: int
    skipped_count: int = 0
    failed_count: int = 0
    errors: list[str] = Field(default_factory=list)


class PiiPurgeResponse(BaseModel):
    """Response after executing GDPR / Decree 13 PII hard purge."""

    status: str = "purged"
    lead_id: UUID
    purged_at: datetime
    dnc_appended: bool = True
