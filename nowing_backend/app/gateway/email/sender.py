"""Outbound email reply sender for the inbound mail gateway."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any

from app.alerts.engine.notify import _send_email_smtp
from app.config import config

logger = logging.getLogger(__name__)


def audit(*, action: str, **kwargs: Any) -> None:
    """Emit a structured audit log entry."""
    extra = {"action": action, **kwargs}
    logger.info("email_gateway.audit", extra=extra)


def _is_valid_email(address: str) -> bool:
    """Loose RFC 5322 email validation."""
    return bool(
        re.match(r"^[\w.+-]+@[\w.-]+\.[\w]{2,}$", address, flags=re.IGNORECASE)
    )


def _truncate_reply_body(body: str, max_bytes: int | None = None) -> str:
    """Ensure a reply body is under the configured byte limit."""
    if max_bytes is None:
        max_bytes = config.GATEWAY_EMAIL_MAX_REPLY_BODY_BYTES

    encoded = body.encode("utf-8")
    if len(encoded) <= max_bytes:
        return body

    # Binary-search a safe UTF-8 truncation point.
    low, high = 0, len(body)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = body[:mid]
        if len(candidate.encode("utf-8")) <= max_bytes:
            low = mid
        else:
            high = mid - 1

    truncated = body[:low].rstrip()
    return f"{truncated}\n\n[Reply truncated]"


def build_reply_body(
    summary: str,
    deliverable_link: str,
    degradation_reasons: list[str] | None = None,
) -> str:
    """Build a plain-text reply body from summary, link and optional reasons."""
    lines = [summary, "", f"Link: {deliverable_link}"]

    reasons = degradation_reasons or []
    if reasons:
        lines.append("")
        lines.append("Degradation reasons:")
        for reason in reasons:
            lines.append(f"- {reason}")

    body = "\n".join(lines)
    return _truncate_reply_body(body)


def _send_email_smtp(
    to_email: str,
    subject: str,
    body: str,
    *,
    from_email: str | None = None,
    reply_to: str | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Send an email with custom From/Reply-To headers.

    Falls back to the alert-engine helper when no extra headers are needed.
    """
    from_addr = from_email or (config.SMTP_FROM or "noreply@nowing.net")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Reply-To"] = reply_to or from_addr
    if headers:
        for key, value in headers.items():
            msg[key] = value
    msg.set_content(body)

    smtp_host = config.SMTP_HOST
    if not smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")

    timeout = getattr(config, "SMTP_TIMEOUT_SECONDS", 30.0)
    server = smtplib.SMTP(smtp_host, config.SMTP_PORT, timeout=timeout)
    try:
        if config.SMTP_TLS:
            server.starttls()
        if config.SMTP_USER and config.SMTP_PASSWORD:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        server.quit()


def send_email_reply(
    original_from: str,
    original_subject: str,
    original_message_id: str | None,
    workspace_id: int,
    body: str,
    degradation_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Send a reply email and return a result summary.

    Returns ``{"status": "replied"}`` on success or
    ``{"status": "replied_failed"}`` / ``{"attempted": False}`` on failure.
    """
    if not _is_valid_email(original_from):
        logger.warning("Invalid From address %r; skipping reply", original_from)
        return {"attempted": False}

    if not config.SMTP_HOST:
        logger.warning(
            "SMTP_HOST not configured; cannot send email reply for workspace %s",
            workspace_id,
        )

    subject = f"Re: {original_subject}" if original_subject else "Re: your request"
    reply_to = f"task+{workspace_id}@{config.GATEWAY_EMAIL_DOMAIN}"
    headers = {}
    if original_message_id:
        headers["In-Reply-To"] = original_message_id

    from_email = config.SMTP_FROM or f"task@{config.GATEWAY_EMAIL_DOMAIN}"

    try:
        _send_email_smtp(
            to_email=original_from,
            subject=subject,
            body=body,
            from_email=from_email,
            reply_to=reply_to,
            headers=headers,
        )
    except Exception as exc:
        logger.exception("Failed to send email reply to %s", original_from)
        audit(
            action="email_reply_failed",
            error_code=type(exc).__name__,
            to_address=original_from,
            workspace_id=workspace_id,
        )
        return {"status": "replied_failed"}

    return {"status": "replied"}
