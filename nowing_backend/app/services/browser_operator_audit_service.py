"""Browser operator audit service for CDP command logging (Story 32.3)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import DshMission
from app.models.browser_operator_audit import BrowserOperatorAuditEvent
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)

_CDP_SESSION_TTL_SECONDS = 300  # 5 minutes


def _get_session_secret() -> str:
    """Return the CDP session secret from config or env."""
    return getattr(config, "CDP_SESSION_SECRET", "dev-cdp-secret-change-in-production")


def generate_session_token(mission_id: str, user_id: str) -> str:
    """Generate a cryptographic session token for CDP command authentication.

    Format: cdp_sess.{mission_id}.{timestamp}.{hmac_signature}
    Uses dots to avoid conflicts with hyphens in UUIDs.
    """
    timestamp = int(time.time())
    payload = f"{mission_id}:{user_id}:{timestamp}"
    signature = hmac.new(
        _get_session_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"cdp_sess.{mission_id}.{timestamp}.{signature}"


async def validate_session_token(
    token: str,
    expected_mission_id: str,
    expected_user_id: str,
    redis_client: Any | None = None,
) -> tuple[bool, str | None]:
    """Validate a CDP session token.

    Returns (is_valid, error_message).
    When ``redis_client`` is provided, enforces single-use replay protection
    by marking consumed tokens in Redis.
    """
    if not token or not token.startswith("cdp_sess."):
        return False, "Invalid token format"

    try:
        parts = token.split(".")
        if len(parts) != 4:
            return False, "Malformed token"
        _, mission_id, timestamp_str, signature = parts
        timestamp = int(timestamp_str)
    except (ValueError, IndexError):
        return False, "Malformed token"

    # Check expiry: reject future timestamps and expired tokens
    now = int(time.time())
    if timestamp > now + 60:  # 60s clock skew tolerance
        return False, "Token timestamp in future"
    if now - timestamp > _CDP_SESSION_TTL_SECONDS:
        return False, "Token expired"

    # Verify signature
    payload = f"{mission_id}:{expected_user_id}:{timestamp}"
    expected_sig = hmac.new(
        _get_session_secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]

    if not hmac.compare_digest(signature, expected_sig):
        return False, "Invalid signature"

    if mission_id != expected_mission_id:
        return False, "Mission ID mismatch"

    # Single-use replay protection: consume token in Redis
    if redis_client is not None:
        used_key = f"cdp:used_token:{token}"
        try:
            already = await redis_client.set(
                used_key, "1", ex=_CDP_SESSION_TTL_SECONDS, nx=True
            )
        except Exception:
            already = "1"  # fail open if redis unavailable
        if already is None:
            return False, "Token already used (replay detected)"

    return True, None


class BrowserOperatorAuditService:
    """Service for logging browser operator audit events."""

    @staticmethod
    def _redact_url(url: str | None) -> str | None:
        """Redact PII from URL before logging."""
        if not url:
            return url
        try:
            return redact_pii(url, context="lead_enrichment").text
        except Exception as exc:
            logger.warning("PII redaction failed for audit URL: %s", exc)
            return "<redaction_failed>"

    @staticmethod
    async def log_event(
        session: AsyncSession,
        *,
        mission_id: uuid.UUID,
        workspace_id: int,
        user_id: uuid.UUID,
        command_id: str,
        action: str,
        success: bool,
        target_url: str | None = None,
        error_message: str | None = None,
        challenge: str | None = None,
        requires_human: bool = False,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BrowserOperatorAuditEvent:
        """Log a browser operator audit event to the database."""
        event = BrowserOperatorAuditEvent(
            mission_id=mission_id,
            workspace_id=workspace_id,
            user_id=user_id,
            command_id=command_id,
            action=action,
            target_url=BrowserOperatorAuditService._redact_url(target_url),
            success=success,
            error_message=error_message,
            challenge=challenge,
            requires_human=requires_human,
            duration_ms=duration_ms,
            metadata_=metadata or {},
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def log_command_received(
        session: AsyncSession,
        *,
        mission_id: uuid.UUID,
        workspace_id: int,
        user_id: uuid.UUID,
        command_id: str,
        action: str,
        target_url: str | None = None,
    ) -> BrowserOperatorAuditEvent:
        """Log a CDP command receipt (before execution)."""
        return await BrowserOperatorAuditService.log_event(
            session,
            mission_id=mission_id,
            workspace_id=workspace_id,
            user_id=user_id,
            command_id=command_id,
            action=action,
            target_url=target_url,
            success=True,
            metadata={"event_type": "command_received"},
        )

    @staticmethod
    async def log_command_result(
        session: AsyncSession,
        *,
        mission_id: uuid.UUID,
        workspace_id: int,
        user_id: uuid.UUID,
        command_id: str,
        action: str,
        success: bool,
        target_url: str | None = None,
        error_message: str | None = None,
        challenge: str | None = None,
        requires_human: bool = False,
        duration_ms: int | None = None,
    ) -> BrowserOperatorAuditEvent:
        """Log a CDP command execution result."""
        return await BrowserOperatorAuditService.log_event(
            session,
            mission_id=mission_id,
            workspace_id=workspace_id,
            user_id=user_id,
            command_id=command_id,
            action=action,
            target_url=target_url,
            success=success,
            error_message=error_message,
            challenge=challenge,
            requires_human=requires_human,
            duration_ms=duration_ms,
            metadata={"event_type": "command_result"},
        )
