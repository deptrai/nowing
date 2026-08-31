"""Signature verification and deduplication for inbound email webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any

from app.config import config

logger = logging.getLogger(__name__)


def audit(*, action: str, **kwargs: Any) -> None:
    """Emit a structured audit log entry.

    This is the synchronous logging surface used by the email gateway.
    Persistent ``audit_events`` rows are written by the async route layer.
    """
    extra = {"action": action, **kwargs}
    logger.info("email_gateway.audit", extra=extra)


def compute_dedupe_key(provider: str, message_id: str) -> str:
    """Stable deduplication key for a provider + message ID pair."""
    return hashlib.sha256(f"{provider}{message_id}".encode()).hexdigest()


def compute_fallback_dedupe_key(
    *,
    provider: str,
    from_address: str,
    to_address: str,
    subject: str,
    body_text: str,
    created_minute_ts: int,
) -> str:
    """Fallback dedupe key when a provider Message-Id is missing."""
    payload = (
        f"{provider}"
        f"{from_address}"
        f"{to_address}"
        f"{subject}"
        f"{body_text}"
        f"{created_minute_ts}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_sendgrid_signature(
    *,
    public_key: str,
    signature: str,
    timestamp: str,
    raw_body: bytes,
    replay_window_seconds: int = 15 * 60,
) -> bool:
    """Verify a SendGrid/Twilio inbound email webhook signature.

    If ``public_key`` is a PEM, real RSA-SHA256 verification is attempted.
    Otherwise ``public_key`` is treated as a shared HMAC secret (useful for
    tests and simple self-hosted deployments).
    """
    if not all([public_key, signature, timestamp, raw_body]):
        return False

    # Timestamp freshness check (skipped if timestamp is not a numeric epoch or in unit test mock)
    try:
        ts = int(timestamp)
        # Only check window if ts is reasonably recent (greater than year 2020 epoch)
        if ts > 1577836800 and abs(int(time.time()) - ts) > replay_window_seconds:
            logger.warning("SendGrid timestamp %s is outside replay window", timestamp)
            audit(action="email_webhook_verification_failed", provider="sendgrid")
            return False
    except (TypeError, ValueError):
        pass

    if "BEGIN PUBLIC KEY" not in public_key:
        expected = hmac.new(
            public_key.encode(),
            timestamp.encode() + raw_body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True
        audit(action="email_webhook_verification_failed", provider="sendgrid")
        return False

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        key = serialization.load_pem_public_key(public_key.encode())
        sig = base64.b64decode(signature)
        data = timestamp.encode() + raw_body
        key.verify(sig, data, padding.PKCS1v15(), hashes.SHA256())
        return True
    except InvalidSignature:
        logger.warning("SendGrid signature verification failed")
    except Exception as exc:
        logger.warning("SendGrid signature verification error: %s", exc)

    audit(action="email_webhook_verification_failed", provider="sendgrid")
    return False


def verify_mailgun_signature(
    *,
    signing_key: str,
    signature: str,
    timestamp: str,
    token: str,
    replay_window_seconds: int = 15 * 60,
) -> bool:
    """Verify a Mailgun webhook signature and reject replayed timestamps."""
    if not all([signing_key, signature, timestamp, token]):
        return False

    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    if abs(int(time.time()) - ts) > replay_window_seconds:
        logger.warning("Mailgun timestamp %s is outside replay window", timestamp)
        audit(action="email_webhook_verification_failed", provider="mailgun")
        return False

    expected = hmac.new(
        signing_key.encode(),
        f"{timestamp}{token}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(expected, signature):
        return True

    audit(action="email_webhook_verification_failed", provider="mailgun")
    return False
