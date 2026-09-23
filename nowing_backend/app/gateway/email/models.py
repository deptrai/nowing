"""Pydantic models for the inbound email gateway."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EmailAttachment(BaseModel):
    """Normalized attachment metadata from an inbound email."""

    filename: str
    mime_type: str
    size: int = 0
    content: bytes | None = None
    document_id: int | None = None


class InboundEmail(BaseModel):
    """Provider-agnostic parsed inbound email."""

    provider: str
    message_id: str | None = None
    from_address: str
    to_address: str
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    attachments: list[EmailAttachment] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class EmailReply(BaseModel):
    """Outbound email reply metadata."""

    to_email: str
    from_email: str
    reply_to: str | None = None
    subject: str
    body: str
    headers: dict[str, str] = Field(default_factory=dict)
