"""Anti-bot / CAPTCHA screenshot escalation service.

Apache-2.0. Persists admin-review rows for scraper anti-bot blocks and handles
screenshot storage/retention.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AntiBotEscalation
from app.file_storage.factory import get_storage_backend
from app.observability import metrics

logger = logging.getLogger(__name__)

_SCREENSHOT_KEY_PREFIX = "anti_bot_screenshots"

_BOT_DEGRADATION_REASONS = {
    "bot_detected",
    "anti_bot_block",
    "access_blocked",
}


def _screenshot_key(workspace_id: int, run_id: UUID) -> str:
    return f"{_SCREENSHOT_KEY_PREFIX}/{workspace_id}/{run_id}.png"


def _public_url(key: str) -> str:
    """Return a public URL for a stored screenshot key.

    ponytail: The base ``StorageBackend`` falls back to ``NOWING_PUBLIC_URL``;
    Azure overrides with the blob endpoint. If a deployment serves local files
    under a different path, that mapping belongs in the backend ``public_url``.
    """
    backend = get_storage_backend()
    return backend.public_url(key)


def _updated_metadata(
    existing: dict | None,
    workspace_id: int,
    run_id: UUID,
    updates: dict | None = None,
) -> dict:
    """Merge escalation_metadata and keep the storage key for later deletion."""
    merged: dict = dict(existing) if existing else {}
    if updates:
        merged.update(updates)
    if "storage_key" not in merged:
        merged["storage_key"] = _screenshot_key(workspace_id, run_id)
    return merged


async def upload_screenshot(
    session: AsyncSession,
    data: bytes,
    workspace_id: int,
    run_id: UUID,
) -> str | None:
    """Store ``data`` as a PNG and return a public URL, or ``None`` on failure.

    The ``session`` parameter is kept for parity with the rest of the service
    layer; the bytes are written through the configured ``StorageBackend``.
    """
    key = _screenshot_key(workspace_id, run_id)
    try:
        backend = get_storage_backend()
        await backend.put(key, data, content_type="image/png")
        return _public_url(key)
    except Exception as exc:
        logger.warning("Failed to upload anti-bot screenshot: %s", exc)
        metrics.record_anti_bot_screenshot_failure(reason="upload")
        return None


async def create_or_update_escalation(
    session: AsyncSession,
    *,
    run_id: UUID,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
    screenshot_url: str | None = None,
    metadata: dict | None = None,
) -> AntiBotEscalation:
    """Create a new escalation or bump an open one for the same grouping key."""
    metrics.record_anti_bot_detection(
        capability=capability, block_type=block_type, domain=domain
    )

    result = await session.execute(
        select(AntiBotEscalation)
        .where(
            AntiBotEscalation.workspace_id == workspace_id,
            AntiBotEscalation.domain == domain,
            AntiBotEscalation.capability == capability,
            AntiBotEscalation.status == "open",
        )
        .order_by(AntiBotEscalation.created_at.desc())
        .limit(1)
    )
    existing: AntiBotEscalation | None = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if existing is not None:
        existing.detection_count += 1
        existing.last_seen_at = now
        existing.status = "open"
        if screenshot_url is not None:
            existing.screenshot_url = screenshot_url
        existing.escalation_metadata = _updated_metadata(
            existing.escalation_metadata, workspace_id, run_id, metadata
        )
        return existing

    escalation = AntiBotEscalation(
        run_id=run_id,
        workspace_id=workspace_id,
        capability=capability,
        domain=domain,
        block_type=block_type,
        screenshot_url=screenshot_url,
        status="open",
        detection_count=1,
        last_seen_at=now,
        escalation_metadata=_updated_metadata(metadata, workspace_id, run_id),
    )
    session.add(escalation)
    return escalation


async def resolve_escalation(
    session: AsyncSession,
    escalation_id: int,
    user_id: UUID | None = None,
) -> AntiBotEscalation | None:
    """Mark an escalation resolved and best-effort delete its screenshot."""
    escalation = await get_escalation(session, escalation_id)
    if escalation is None:
        return None

    now = datetime.now(UTC)
    escalation.status = "resolved"
    escalation.resolved_at = now
    escalation_metadata = (
        dict(escalation.escalation_metadata) if escalation.escalation_metadata else {}
    )
    if user_id is not None:
        escalation_metadata["resolved_by"] = str(user_id)
    escalation.escalation_metadata = escalation_metadata

    storage_key = escalation_metadata.get("storage_key")
    if storage_key:
        try:
            backend = get_storage_backend()
            await backend.delete(storage_key)
        except Exception as exc:
            logger.warning(
                "Failed to delete screenshot for escalation %s: %s",
                escalation_id,
                exc,
            )
    return escalation


async def list_escalations(
    session: AsyncSession,
    *,
    workspace_id: int | None = None,
    domain: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AntiBotEscalation]:
    """Return escalations with optional filters, newest first."""
    query = select(AntiBotEscalation).order_by(AntiBotEscalation.created_at.desc())
    if workspace_id is not None:
        query = query.where(AntiBotEscalation.workspace_id == workspace_id)
    if domain is not None:
        query = query.where(AntiBotEscalation.domain == domain)
    if status is not None:
        query = query.where(AntiBotEscalation.status == status)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_escalation(
    session: AsyncSession, escalation_id: int
) -> AntiBotEscalation | None:
    """Return one escalation by id."""
    return await session.get(AntiBotEscalation, escalation_id)
