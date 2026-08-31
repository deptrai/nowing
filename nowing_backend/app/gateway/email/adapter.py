"""Provider-agnostic inbound email parser."""

from __future__ import annotations

import email
import html
import logging
import re
from email.message import EmailMessage
from email.policy import default as default_policy
from typing import Any

from app.config import config
from app.exceptions import NowingError
from app.gateway.base.adapter import ParsedInboundEvent
from app.gateway.email.models import EmailAttachment, InboundEmail

logger = logging.getLogger(__name__)

# Fields that should not be persisted in the raw_payload audit copy.
_SENSITIVE_FIELDS = {
    "dkim",
    "domainkeys",
    "x-dkim",
    "x-sender-ip",
    "received-spf",
    "authentication-results",
    "x-mailgun-sending-ip",
    "x-mailgun-sid",
}


class EmailPayloadTooLargeError(NowingError):
    """Raised when an inbound email exceeds the configured size limit."""

    def __init__(self, message: str = "Payload too large") -> None:
        super().__init__(
            message or "Payload too large (413)",
            code="EMAIL_PAYLOAD_TOO_LARGE",
            status_code=413,
        )


class EmailRequestUnparsableError(NowingError):
    """Raised when no usable request text can be extracted."""

    def __init__(self, message: str = "Cannot understand request") -> None:
        super().__init__(message, code="EMAIL_REQUEST_UNPARSABLE", status_code=400)


def _normalize_email(address: str) -> str:
    """Lowercase and strip plus-tags from an email address."""
    address = address.strip().lower()
    local, _, domain = address.partition("@")
    if "+" in local:
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


def _extract_workspace_id(address: str) -> int | None:
    """Return the numeric workspace ID from a task+{id}@nowing.ai address."""
    match = re.match(r"^task\+(\d+)@", address.strip().lower())
    if match:
        val = int(match.group(1))
        # Guard against PostgreSQL 32-bit Integer overflow
        if val > 2147483647:
            return None
        return val
    return None


def _select_recipient(recipients: list[str], *, domain: str) -> str | None:
    """Select the first recipient matching task+{id}@{domain}."""
    for recipient in recipients:
        norm = recipient.strip().lower()
        if re.match(rf"^task\+\d+@{re.escape(domain)}$", norm):
            return recipient
    return None


def _strip_html(value: str) -> str:
    """Remove HTML tags (including script and style blocks) and decode entities to plain text."""
    # First remove style and script tags with their inner contents
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_raw_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a raw payload copy with sensitive provider tokens removed."""
    cleaned = {}
    for key, value in raw.items():
        if key.lower() in _SENSITIVE_FIELDS:
            continue
        cleaned[key] = value
    return cleaned


def _parse_mime_message(mime_text: str) -> InboundEmail:
    """Parse a full MIME message (SendGrid Inbound Parse ``email`` field)."""
    try:
        msg = email.message_from_string(mime_text, policy=default_policy)
    except Exception:
        msg = email.message_from_string(mime_text)

    from_address = _extract_header(msg, "From") or ""
    to_address = _extract_header(msg, "To") or ""
    subject = _extract_header(msg, "Subject") or ""
    message_id = _extract_header(msg, "Message-Id") or None

    body_text = ""
    body_html = ""
    attachments: list[EmailAttachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition() or ""
            if "attachment" in disposition:
                attachments.append(
                    EmailAttachment(
                        filename=part.get_filename() or "unnamed",
                        mime_type=content_type,
                        size=len(part.get_payload(decode=True) or b""),
                    )
                )
            elif content_type == "text/plain" and not body_text:
                body_text = _decode_part(part)
            elif content_type == "text/html" and not body_html:
                body_html = _decode_part(part)
    else:
        content = _decode_part(msg)
        if msg.get_content_type() == "text/html":
            body_html = content
        else:
            body_text = content

    if not body_text and body_html:
        body_text = _strip_html(body_html)

    return InboundEmail(
        provider="sendgrid",
        message_id=message_id,
        from_address=from_address,
        to_address=to_address,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
    )


def _extract_header(msg: EmailMessage, name: str) -> str | None:
    """Return a decoded header value or None."""
    value = msg.get(name)
    if value is None:
        return None
    decoded = email.header.decode_header(value)
    parts = []
    for part, charset in decoded:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts).strip() or None


def _decode_part(part: EmailMessage) -> str:
    """Decode a MIME part to a Unicode string."""
    payload = part.get_payload()
    if isinstance(payload, str):
        return payload

    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _split_addresses(value: str) -> list[str]:
    """Split a comma-separated address header into individual addresses."""
    return [a.strip() for a in value.split(",") if a.strip()]


class EmailAdapter:
    """Parse SendGrid and Mailgun inbound payloads into gateway events."""

    def _envelope_size(self, raw: dict[str, Any]) -> int:
        """Estimate the raw payload size in bytes."""
        try:
            return len(str(raw).encode("utf-8"))
        except Exception:
            return 0

    def _parse_sendgrid(self, raw: dict[str, Any]) -> InboundEmail:
        """Parse a SendGrid Inbound Parse payload."""
        mime_text = raw.get("email", "")
        email = _parse_mime_message(mime_text)

        # SendGrid also sends key headers in the ``headers`` field, and
        # SendGrid Inbound Parse exposes the top-level ``Message-Id``,
        # ``from``, ``to`` and ``subject`` fields as well.
        email.message_id = email.message_id or raw.get("Message-Id") or None
        email.from_address = email.from_address or raw.get("from") or ""
        email.to_address = email.to_address or raw.get("to") or ""
        email.subject = email.subject or raw.get("subject")

        headers = raw.get("headers") or {}
        if headers:
            email.message_id = email.message_id or headers.get("Message-Id")
            email.from_address = email.from_address or headers.get("From") or ""
            email.to_address = email.to_address or headers.get("To") or ""
            email.subject = email.subject or headers.get("Subject")

        return email

    def _parse_mailgun(self, raw: dict[str, Any]) -> InboundEmail:
        """Parse a Mailgun Route payload."""
        body_text = raw.get("body-plain", "") or ""
        body_html = raw.get("body-html", "") or ""
        if not body_text and body_html:
            body_text = _strip_html(body_html)

        attachments = []
        raw_attachments = raw.get("attachments", [])
        if isinstance(raw_attachments, str):
            try:
                import json

                raw_attachments = json.loads(raw_attachments)
            except Exception:
                raw_attachments = []
        for att in raw_attachments or []:
            if not isinstance(att, dict):
                continue
            attachments.append(
                EmailAttachment(
                    filename=att.get("filename") or att.get("name") or "unnamed",
                    mime_type=att.get("content-type") or att.get("mimetype") or "application/octet-stream",
                    size=int(att.get("size") or 0),
                )
            )

        return InboundEmail(
            provider="mailgun",
            message_id=raw.get("Message-Id"),
            from_address=raw.get("sender") or raw.get("from") or "",
            to_address=raw.get("recipient") or raw.get("to") or "",
            subject=raw.get("subject"),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def parse_inbound_email(self, raw_payload: dict[str, Any]) -> InboundEmail:
        """Return a provider-agnostic ``InboundEmail`` from a webhook payload."""
        size = self._envelope_size(raw_payload)
        if size > config.GATEWAY_EMAIL_MAX_SIZE_BYTES:
            raise EmailPayloadTooLargeError(
                f"Email body exceeds {config.GATEWAY_EMAIL_MAX_SIZE_BYTES} bytes (413)"
            )

        provider = _detect_provider(raw_payload)
        if provider == "sendgrid":
            parsed = self._parse_sendgrid(raw_payload)
        else:
            parsed = self._parse_mailgun(raw_payload)

        if not parsed.from_address or not parsed.to_address:
            raise EmailRequestUnparsableError("Missing From or To address")

        if not parsed.body_text and not parsed.body_html:
            raise EmailRequestUnparsableError("Cannot understand request")

        return parsed

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        """Return a gateway-normalized ``ParsedInboundEvent`` from a provider payload."""
        parsed = self.parse_inbound_email(raw_payload)

        to_addresses = _split_addresses(parsed.to_address)
        domain = config.GATEWAY_EMAIL_DOMAIN
        selected_to = _select_recipient(to_addresses, domain=domain) or parsed.to_address

        return ParsedInboundEvent(
            platform="email",
            event_kind="inbound",
            external_peer_id=selected_to,
            external_peer_kind="email",
            external_message_id=parsed.message_id,
            external_user_id=_normalize_email(parsed.from_address),
            text=parsed.body_text,
            raw_payload=_clean_raw_payload(raw_payload),
            display_name=None,
            username=parsed.from_address,
            provider=parsed.provider,
            metadata={
                "provider": parsed.provider,
                "subject": parsed.subject,
                "to_address": selected_to,
                "from_address": parsed.from_address,
                "body_html": parsed.body_html,
                "attachments": [att.model_dump(mode="json") for att in parsed.attachments],
            },
        )


def _detect_provider(raw: dict[str, Any]) -> str:
    """Heuristic provider detection from payload shape."""
    if "email" in raw:
        return "sendgrid"
    if "body-plain" in raw or "sender" in raw or "recipient" in raw:
        return "mailgun"
    return config.GATEWAY_EMAIL_PROVIDER
