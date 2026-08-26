"""Schemas for Superadmin Security Audit Trail Logs (Story 25.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditActionEnum(StrEnum):
    """Known audit log actions (permissive string enum)."""

    USER_IMPERSONATE_START = "user.impersonate_start"
    USER_IMPERSONATE_EXIT = "user.impersonate_exit"
    SCRAPER_RULE_CREATE = "scraper_rule.create"
    SCRAPER_RULE_UPDATE = "scraper_rule.update"
    SCRAPER_RULE_ACTIVATE = "scraper_rule.activate"
    SCRAPER_RULE_DELETE = "scraper_rule.delete"
    SCRAPER_RULE_TRIP = "scraper_rule.trip"
    SCRAPER_RULE_RESET = "scraper_rule.reset"
    MANUAL_CREDIT_QUOTA_EXCEEDED = "manual_credit_quota_exceeded"
    GLOBAL_DNC_ADD = "global_dnc.add"
    GLOBAL_DNC_UPDATE = "global_dnc.update"
    GLOBAL_DNC_REMOVE = "global_dnc.remove"
    BROADCAST_CREATE = "broadcast.create"
    BROADCAST_UPDATE = "broadcast.update"
    BROADCAST_DELETE = "broadcast.delete"
    BROADCAST_EXPIRE = "broadcast.expire"
    AUDIT_LOG_VIEW = "audit_log.view"


class AuditEventRead(BaseModel):
    """Read representation of an audit event with resolved user emails."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    actor_email: str | None = None
    subject_email: str | None = None
    ticket_ref: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    diff_payload: dict[str, Any] | None = None
    created_at: datetime
    endpoint: str | None = None


class AuditEventListResponse(BaseModel):
    """Paginated list response for audit logs."""

    items: list[AuditEventRead]
    total: int
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
