"""Inbound email gateway bundle (SendGrid / Mailgun)."""

from __future__ import annotations

from app.gateway.email.adapter import EmailAdapter
from app.gateway.email.auth import (
    compute_dedupe_key,
    compute_fallback_dedupe_key,
    verify_mailgun_signature,
    verify_sendgrid_signature,
)
from app.gateway.email.models import EmailAttachment, EmailReply, InboundEmail
from app.gateway.email.sender import build_reply_body, send_email_reply

__all__ = [
    "EmailAdapter",
    "EmailAttachment",
    "EmailReply",
    "InboundEmail",
    "build_reply_body",
    "compute_dedupe_key",
    "compute_fallback_dedupe_key",
    "send_email_reply",
    "verify_mailgun_signature",
    "verify_sendgrid_signature",
]
