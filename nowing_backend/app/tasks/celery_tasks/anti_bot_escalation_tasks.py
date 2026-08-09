"""Celery tasks for anti-bot / CAPTCHA screenshot escalation.

These tasks run out-of-band so that the capability executor can return a
`degraded` response immediately (AD-17 / AD-19).
"""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import AntiBotEscalation
from app.file_storage.factory import get_storage_backend
from app.observability import metrics
from app.services.anti_bot_escalation import (
    _public_url,
    _screenshot_key,
    _updated_metadata,
    create_or_update_escalation,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="persist_anti_bot_escalation")
def persist_anti_bot_escalation_task(
    screenshot_png_b64: str | None,
    run_id: str,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
    metadata: dict | None = None,
) -> None:
    """Upload a screenshot and create/update an escalation in the background.

    The screenshot bytes are base64-encoded because the Celery broker is
    configured for JSON. For a typical anti-bot challenge page the PNG is a few
    hundred KB, which is acceptable for the broker. If it becomes a bottleneck,
    the caller can write to a temporary file on shared storage and pass the
    path instead.
    """
    return run_async_celery_task(
        lambda: _persist_anti_bot_escalation(
            screenshot_png_b64,
            run_id,
            workspace_id,
            capability,
            domain,
            block_type,
            metadata,
        )
    )


async def _persist_anti_bot_escalation(
    screenshot_png_b64: str | None,
    run_id: str,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
    metadata: dict | None,
) -> None:
    screenshot_url: str | None = None
    run_uuid = UUID(run_id)

    if screenshot_png_b64 is not None:
        try:
            data = base64.b64decode(screenshot_png_b64)
            key = _screenshot_key(workspace_id, run_uuid)
            backend = get_storage_backend()
            await backend.put(key, data, content_type="image/png")
            screenshot_url = _public_url(key)
        except Exception as exc:
            logger.warning("Failed to upload anti-bot screenshot: %s", exc)
            metrics.record_anti_bot_screenshot_failure(reason="upload")

    async with get_celery_session_maker()() as session:
        await create_or_update_escalation(
            session,
            run_id=run_uuid,
            workspace_id=workspace_id,
            capability=capability,
            domain=domain,
            block_type=block_type,
            screenshot_url=screenshot_url,
            metadata=metadata,
        )
        await session.commit()


@celery_app.task(name="apply_anti_bot_screenshot_retention")
def apply_anti_bot_screenshot_retention_task() -> None:
    """Delete screenshot files for escalations older than 30 days."""
    return run_async_celery_task(_apply_anti_bot_screenshot_retention)


async def _apply_anti_bot_screenshot_retention() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    async with get_celery_session_maker()() as session:
        result = await session.execute(
            select(AntiBotEscalation).where(
                AntiBotEscalation.created_at < cutoff,
                AntiBotEscalation.screenshot_url.is_not(None),
            )
        )
        for escalation in result.scalars():
            meta = (
                dict(escalation.escalation_metadata)
                if escalation.escalation_metadata
                else {}
            )
            storage_key = meta.get("storage_key")
            if storage_key:
                try:
                    backend = get_storage_backend()
                    await backend.delete(storage_key)
                except Exception as exc:
                    logger.warning(
                        "Failed to delete old screenshot for escalation %s: %s",
                        escalation.id,
                        exc,
                    )
                    continue
            escalation.screenshot_url = None
            escalation.escalation_metadata = _updated_metadata(
                meta, escalation.workspace_id, escalation.run_id
            )
            escalation.escalation_metadata["retention_deleted_at"] = datetime.now(
                UTC
            ).isoformat()

        await session.commit()
