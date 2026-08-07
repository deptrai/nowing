"""Celery worker that drains the canonical persist outbox.

When BDS/Jobs aggregation fails to write a canonical entity, the orchestrator
stages a durable outbox row. This task retries those rows with exponential
backoff under the correct workspace RLS context.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import celery_app
from app.db import CanonicalPersistOutbox
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from ..services.canonical_persist_service import (
    ConcurrentUpdateError,
    upsert_canonical_entity,
)
from ..tenant_context import set_canonical_workspace_id

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BATCH_SIZE = 25
_BASE_BACKOFF_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(retry_count: int) -> int:
    """Exponential backoff capped at 30 minutes."""
    return min(_BASE_BACKOFF_SECONDS * (2 ** max(0, retry_count)), 30 * 60)


async def _mark_outbox(
    session,
    outbox_id: uuid.UUID,
    *,
    status: str,
    retry_count: int | None = None,
    error: str | None = None,
    next_attempt_at: datetime | None = None,
) -> None:
    values: dict[str, Any] = {
        "status": status,
        "updated_at": _now(),
    }
    if retry_count is not None:
        values["retry_count"] = retry_count
    if error is not None:
        values["error"] = error[:2000]
    if next_attempt_at is not None or status in {"done", "failed"}:
        values["next_attempt_at"] = next_attempt_at
    await session.execute(
        update(CanonicalPersistOutbox)
        .where(CanonicalPersistOutbox.id == outbox_id)
        .values(**values)
    )


async def _process_one_outbox(session, outbox: CanonicalPersistOutbox) -> None:
    """Replay one outbox payload into canonical storage."""
    workspace_id = outbox.workspace_id
    await set_canonical_workspace_id(session, workspace_id)

    payload = outbox.payload or {}
    entity_type = payload.get("entity_type") or outbox.entity_type
    fingerprint = payload.get("fingerprint")
    title = payload.get("title")
    data = payload.get("data") or {}
    search_text = payload.get("search_text")
    sources = payload.get("sources") or []
    confidence = float(payload.get("confidence_score") or 0.0)
    conflict_flags = payload.get("conflict_flags") or []

    if not fingerprint or not sources:
        await _mark_outbox(
            session,
            outbox.id,
            status="failed",
            retry_count=outbox.retry_count,
            error="invalid outbox payload: missing fingerprint or sources",
            next_attempt_at=None,
        )
        await session.commit()
        return

    try:
        for source in sources:
            source_name = source.get("source_name")
            source_record_id = source.get("source_record_id")
            if not source_name or not source_record_id:
                raise ValueError("source entry missing source_name/source_record_id")
            await upsert_canonical_entity(
                session,
                workspace_id=workspace_id,
                entity_type=entity_type,
                fingerprint=fingerprint,
                title=title,
                data=data,
                search_text=search_text,
                source_name=str(source_name),
                source_record_id=str(source_record_id),
                source_snapshot=source.get("source_snapshot") or data,
                source_url=source.get("source_url"),
                confidence_score=confidence,
                conflict_flags=conflict_flags,
                actor="outbox_worker",
                merge_method="outbox_retry",
            )
        await _mark_outbox(
            session,
            outbox.id,
            status="done",
            retry_count=outbox.retry_count,
            error=None,
            next_attempt_at=None,
        )
        await session.commit()
        logger.info("Outbox %s processed successfully", outbox.id)
    except (ConcurrentUpdateError, ValueError, SQLAlchemyError) as exc:
        await session.rollback()
        # Re-bind tenant after rollback (SET LOCAL is cleared).
        await set_canonical_workspace_id(session, workspace_id)
        new_retry = (outbox.retry_count or 0) + 1
        if new_retry >= _MAX_RETRIES:
            await _mark_outbox(
                session,
                outbox.id,
                status="failed",
                retry_count=new_retry,
                error=str(exc),
                next_attempt_at=None,
            )
            logger.warning(
                "Outbox %s permanently failed after %s retries: %s",
                outbox.id,
                new_retry,
                exc,
            )
        else:
            await _mark_outbox(
                session,
                outbox.id,
                status="pending",
                retry_count=new_retry,
                error=str(exc),
                next_attempt_at=_now() + timedelta(seconds=_backoff_seconds(new_retry)),
            )
            logger.info(
                "Outbox %s re-queued retry=%s error=%s",
                outbox.id,
                new_retry,
                exc,
            )
        await session.commit()


async def _drain_canonical_persist_outbox(batch_size: int = _BATCH_SIZE) -> int:
    """Process up to ``batch_size`` due outbox rows. Returns count attempted."""
    from sqlalchemy import text

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        # Outbox is FORCE RLS. The drain must see cross-tenant pending rows,
        # then re-enter each row's workspace context before replay. Requires a
        # DB role that can SET row_security=off (table owner / superuser), which
        # matches the Celery engine used elsewhere for migrations/bootstrap.
        await session.execute(text("SET LOCAL row_security = off"))
        now = _now()
        result = await session.execute(
            select(CanonicalPersistOutbox)
            .where(
                CanonicalPersistOutbox.status.in_(("pending", "processing")),
                (
                    CanonicalPersistOutbox.next_attempt_at.is_(None)
                    | (CanonicalPersistOutbox.next_attempt_at <= now)
                ),
            )
            .order_by(CanonicalPersistOutbox.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = list(result.scalars().all())
        if not rows:
            return 0

        for outbox in rows:
            # Mark processing under the row's tenant before replaying.
            await set_canonical_workspace_id(session, outbox.workspace_id)
            await _mark_outbox(
                session,
                outbox.id,
                status="processing",
                retry_count=outbox.retry_count,
                next_attempt_at=outbox.next_attempt_at,
            )
            await session.commit()
            # Refresh after commit
            outbox = await session.get(CanonicalPersistOutbox, outbox.id)
            if outbox is None:
                continue
            await _process_one_outbox(session, outbox)

        return len(rows)


@celery_app.task(
    name="process_canonical_persist_outbox",
    bind=True,
    autoretry_for=(SQLAlchemyError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_canonical_persist_outbox(self, batch_size: int = _BATCH_SIZE) -> int:
    """Drain due canonical persist outbox rows."""
    try:
        return run_async_celery_task(
            lambda: _drain_canonical_persist_outbox(batch_size=batch_size)
        )
    except (MaxRetriesExceededError, SQLAlchemyError):
        raise
