"""Celery task that backfills embeddings for canonical entities."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import celery_app
from app.db import CanonicalEntity
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.utils.document_converters import embed_texts

from ..tenant_context import set_canonical_workspace_id

logger = logging.getLogger(__name__)


async def _backfill_canonical_embedding_with_session(
    session,
    entity_uuid: uuid.UUID,
    workspace_id: int,
    expected_version: int,
    embedding_model_name: str,
) -> None:
    """Load the entity, verify version, embed ``search_text``, and update."""
    await set_canonical_workspace_id(session, workspace_id)

    result = await session.execute(
        select(CanonicalEntity).where(CanonicalEntity.id == entity_uuid)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        logger.info("Canonical entity %s not found; skipping embedding", entity_uuid)
        return

    if entity.version != expected_version:
        logger.info(
            "Canonical entity %s version mismatch (expected %s, got %s); "
            "skipping stale embedding job",
            entity_uuid,
            expected_version,
            entity.version,
        )
        return

    search_text = entity.search_text or ""
    if not search_text:
        await _set_embedding_status(
            session,
            entity_uuid,
            expected_version,
            status="failed",
        )
        return

    try:
        # ponytail: sync embed in a thread for local models; API models are
        # also wrapped by embed_texts and run fine in asyncio.to_thread.
        vectors = await asyncio.to_thread(embed_texts, [search_text])
    except Exception as exc:
        logger.warning("Embedding failed for %s: %s", entity_uuid, exc)
        await _set_embedding_status(
            session,
            entity_uuid,
            expected_version,
            status="failed",
        )
        return

    if not vectors:
        await _set_embedding_status(
            session,
            entity_uuid,
            expected_version,
            status="failed",
        )
        return

    vector = vectors[0]
    content_hash = hashlib.sha256(search_text.encode("utf-8")).hexdigest()

    result = await session.execute(
        update(CanonicalEntity)
        .where(
            CanonicalEntity.id == entity_uuid,
            CanonicalEntity.version == expected_version,
        )
        .values(
            embedding=vector,
            embedding_model_name=embedding_model_name,
            embedding_content_hash=content_hash,
            embedding_status="ready",
        )
    )
    if result.rowcount != 1:
        logger.info(
            "Canonical entity %s version changed during embedding; skipping",
            entity_uuid,
        )
        return

    await session.commit()
    logger.debug("Embedding ready for %s model=%s", entity_uuid, embedding_model_name)


async def _set_embedding_status(
    session,
    entity_uuid: uuid.UUID,
    expected_version: int,
    *,
    status: str,
) -> None:
    """Update ``embedding_status`` only if the row still has ``expected_version``."""
    result = await session.execute(
        update(CanonicalEntity)
        .where(
            CanonicalEntity.id == entity_uuid,
            CanonicalEntity.version == expected_version,
        )
        .values(
            embedding=None,
            embedding_model_name=None,
            embedding_content_hash=None,
            embedding_status=status,
        )
    )
    if result.rowcount != 1:
        logger.info(
            "Canonical entity %s version changed before embedding status update; "
            "skipping",
            entity_uuid,
        )
        return
    await session.commit()


async def _backfill_canonical_embedding(
    entity_id: str,
    workspace_id: int,
    expected_version: int,
    embedding_model_name: str,
    session=None,
) -> None:
    """Load the entity, verify version, embed ``search_text``, and update."""
    entity_uuid = uuid.UUID(entity_id)

    if session is not None:
        await _backfill_canonical_embedding_with_session(
            session, entity_uuid, workspace_id, expected_version, embedding_model_name
        )
        return

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        await _backfill_canonical_embedding_with_session(
            session, entity_uuid, workspace_id, expected_version, embedding_model_name
        )


@celery_app.task(
    name="backfill_canonical_embedding",
    bind=True,
    autoretry_for=(SQLAlchemyError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def backfill_canonical_embedding(
    self,
    entity_id: str,
    workspace_id: int,
    expected_version: int,
    embedding_model_name: str,
) -> None:
    """Best-effort embedding backfill for a canonical entity.

    Idempotency key: (entity_id, workspace_id, expected_version, embedding_model_name).
    """
    try:
        return run_async_celery_task(
            lambda: _backfill_canonical_embedding(
                entity_id, workspace_id, expected_version, embedding_model_name
            )
        )
    except (MaxRetriesExceededError, SQLAlchemyError):
        raise
