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

# ponytail: guard the Celery broker and storage from multi-MB screenshots.
_MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024


@celery_app.task(name="persist_anti_bot_escalation")
def persist_anti_bot_escalation_task(
    screenshot_png_b64: str | None,
    run_id: str,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
    metadata: dict | None = None,
    screenshot_id: str | None = None,
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
            screenshot_id,
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
    screenshot_id: str | None = None,
) -> None:
    screenshot_url: str | None = None
    run_uuid = UUID(run_id)

    if screenshot_png_b64 is not None:
        try:
            data = base64.b64decode(screenshot_png_b64, validate=True)
        except Exception as exc:
            logger.warning("Failed to decode anti-bot screenshot: %s", exc)
            metrics.record_anti_bot_screenshot_failure(reason="decode")
        else:
            if len(data) > _MAX_SCREENSHOT_BYTES:
                logger.warning(
                    "Decoded screenshot too large (%s bytes), skipping upload",
                    len(data),
                )
                metrics.record_anti_bot_screenshot_failure(reason="size")
            else:
                try:
                    key = _screenshot_key(workspace_id, run_uuid, screenshot_id)
                    backend = get_storage_backend()
                    await backend.put(key, data, content_type="image/png")
                    screenshot_url = _public_url(key)
                except Exception as exc:
                    logger.warning("Failed to upload anti-bot screenshot: %s", exc)
                    metrics.record_anti_bot_screenshot_failure(reason="upload")

    async with get_celery_session_maker()() as session:
        escalation = await create_or_update_escalation(
            session,
            run_id=run_uuid,
            workspace_id=workspace_id,
            capability=capability,
            domain=domain,
            block_type=block_type,
            screenshot_url=None,
            metadata=metadata,
            screenshot_id=screenshot_id,
        )
        if screenshot_url is not None:
            escalation.screenshot_url = (
                f"/api/v1/admin/anti-bot-escalations/{escalation.id}/screenshot"
            )
        await session.commit()


@celery_app.task(name="apply_anti_bot_screenshot_retention")
def apply_anti_bot_screenshot_retention_task() -> None:
    """Delete screenshot files for escalations older than 30 days."""
    return run_async_celery_task(_apply_anti_bot_screenshot_retention)


async def _apply_anti_bot_screenshot_retention(
    batch_size: int = 100,
) -> int:
    """Delete screenshot files for escalations older than 30 days and mark resolved."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    total = 0
    async with get_celery_session_maker()() as session:
        while True:
            result = await session.execute(
                select(AntiBotEscalation)
                .where(
                    AntiBotEscalation.created_at < cutoff,
                    AntiBotEscalation.screenshot_url.is_not(None),
                )
                .limit(batch_size)
            )
            escalations = list(result.scalars())
            if not escalations:
                break

            for escalation in escalations:
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
                        # Mark the failure for later cleanup but still resolve.
                        meta["retention_delete_error"] = str(exc)
                        continue

                escalation.screenshot_url = None
                escalation.status = "resolved"
                escalation.resolved_at = datetime.now(UTC)
                escalation.escalation_metadata = _updated_metadata(
                    meta, escalation.workspace_id, escalation.run_id
                )
                escalation.escalation_metadata["retention_deleted_at"] = (
                    datetime.now(UTC).isoformat()
                )
                total += 1

            await session.commit()
    return total


@celery_app.task(name="capture_platform_anti_bot_screenshot")
def capture_platform_anti_bot_screenshot_task(
    url: str,
    run_id: str,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
) -> None:
    """Capture a browser screenshot of a platform URL for anti-bot evidence.

    Platform scrapers use HTTP APIs and do not have a page object. This task
    re-fetches the representative URL through the browser tier so the stealth
    capture logic can record the anti-bot challenge page. It is best-effort:
    missing screenshots are still escalated with the original block telemetry.
    """
    return run_async_celery_task(
        lambda: _capture_platform_anti_bot_screenshot(
            url, run_id, workspace_id, capability, domain, block_type
        )
    )


async def _capture_platform_anti_bot_screenshot(
    url: str,
    run_id: str,
    workspace_id: int,
    capability: str,
    domain: str,
    block_type: str,
) -> None:
    screenshot_png_b64: str | None = None
    try:
        from app.proprietary.web_crawler import WebCrawlerConnector

        outcome = await WebCrawlerConnector().crawl_url(url)
        if outcome.screenshot_png is not None:
            screenshot_png_b64 = base64.b64encode(outcome.screenshot_png).decode()
            block_type = outcome.block_type.value or block_type
    except Exception as exc:
        logger.warning(
            "Failed to capture platform screenshot for %s (run %s): %s",
            url,
            run_id,
            exc,
        )

    await _persist_anti_bot_escalation(
        screenshot_png_b64,
        run_id,
        workspace_id,
        capability,
        domain,
        block_type,
        None,
    )
