"""Canonical entity persistence service with explicit tenancy."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalMergeHistory,
    CanonicalPersistOutbox,
)

from ..tenant_context import set_canonical_workspace_id
from .canonical_pii import redact_canonical_data, redact_source_snapshot

logger = logging.getLogger(__name__)


class _LazyBackfillTask:
    """Proxy for the Celery backfill task that defers import until first use.

    Importing ``app.canonical.tasks.backfill_canonical_embedding`` at module
    load would create a circular import with
    ``app.canonical.tasks.process_canonical_persist_outbox``, which imports this
    service. The proxy breaks the cycle: the real task is resolved on the first
    attribute access, while tests can still monkeypatch
    ``backfill_canonical_embedding.apply_async`` because the proxy stores any
    attributes set on it.
    """

    def __getattr__(self, name: str) -> Any:
        from ..tasks.backfill_canonical_embedding import backfill_canonical_embedding

        return getattr(backfill_canonical_embedding, name)


backfill_canonical_embedding = _LazyBackfillTask()


class ConcurrentUpdateError(Exception):
    """The entity version changed between read and write; the caller should retry."""

    def __init__(self, message: str = "Concurrent update detected") -> None:
        super().__init__(message)


class RevertNotPossibleError(Exception):
    """The selected history entry cannot be reverted to the current entity state."""

    def __init__(self, message: str = "Revert not possible") -> None:
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(UTC)


def _is_search_text_changed(
    entity: CanonicalEntity, new_search_text: str | None
) -> bool:
    old = entity.search_text or ""
    new = new_search_text or ""
    return old != new


async def _enqueue_embedding_backfill(entity: CanonicalEntity) -> None:
    """Queue an idempotent embedding backfill keyed by (entity, version, model)."""
    model_name = config.EMBEDDING_MODEL or "unknown"
    # ponytail: apply_async with a small delay keeps the enqueued task from
    # racing the same transaction that just staged the row.
    backfill_canonical_embedding.apply_async(
        args=[str(entity.id), entity.workspace_id, entity.version, model_name],
        countdown=1,
    )


async def record_merge_history(
    session: AsyncSession,
    *,
    entity: CanonicalEntity,
    previous_data: dict[str, Any],
    new_data: dict[str, Any],
    operation: str,
    actor: str | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    method: str | None = None,
    previous_version: int | None = None,
    new_version: int | None = None,
    previous_source_ids: list[dict[str, Any]] | None = None,
    new_source_ids: list[dict[str, Any]] | None = None,
) -> CanonicalMergeHistory:
    """Record one merge/revert/resolve audit row with full provenance."""
    redacted_previous_data = redact_canonical_data(entity.entity_type, previous_data)
    redacted_new_data = redact_canonical_data(entity.entity_type, new_data)
    prev = (
        previous_version if previous_version is not None else max(0, entity.version - 1)
    )
    nxt = new_version if new_version is not None else entity.version
    history = CanonicalMergeHistory(
        canonical_entity_id=entity.id,
        workspace_id=entity.workspace_id,
        entity_type=entity.entity_type,
        previous_version=prev,
        new_version=nxt,
        previous_data=redacted_previous_data,
        new_data=redacted_new_data,
        previous_source_ids=previous_source_ids or [],
        new_source_ids=new_source_ids or [],
        operation=operation,
        actor=actor,
        conflicts=conflicts or [],
        method=method,
        created_at=_now(),
    )
    session.add(history)
    await session.flush()
    return history


async def create_persist_outbox(
    session: AsyncSession,
    workspace_id: int,
    entity_type: str,
    payload: dict[str, Any],
    *,
    error: str | None = None,
    retry_count: int = 0,
    next_attempt_at: datetime | None = None,
) -> CanonicalPersistOutbox:
    """Stage a durable outbox row for retry."""
    await set_canonical_workspace_id(session, workspace_id)
    redacted_payload = redact_canonical_data(entity_type, payload)
    outbox = CanonicalPersistOutbox(
        workspace_id=workspace_id,
        entity_type=entity_type,
        payload=redacted_payload,
        status="pending",
        retry_count=retry_count,
        next_attempt_at=next_attempt_at,
        error=error,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(outbox)
    await session.flush()
    return outbox


async def _find_previous_canonical_entity_id(
    session: AsyncSession,
    workspace_id: int,
    entity_type: str,
    source_name: str,
    source_record_id: str,
) -> uuid.UUID | None:
    """Return the canonical entity a source is currently linked to, if any."""
    result = await session.scalar(
        select(CanonicalEntitySource.canonical_entity_id).where(
            CanonicalEntitySource.workspace_id == workspace_id,
            CanonicalEntitySource.entity_type == entity_type,
            CanonicalEntitySource.source_name == source_name,
            CanonicalEntitySource.source_record_id == source_record_id,
        )
    )
    return result


async def _update_source_count(
    session: AsyncSession, canonical_entity_id: uuid.UUID
) -> int:
    """Derive and return ``source_count`` for a canonical entity."""
    count = await session.scalar(
        select(func.count())
        .select_from(CanonicalEntitySource)
        .where(CanonicalEntitySource.canonical_entity_id == canonical_entity_id)
    )
    return count or 0


async def _source_ids_for_entity(
    session: AsyncSession, canonical_entity_id: uuid.UUID
) -> list[dict[str, str]]:
    """Return the linked source set for a canonical entity, ordered by recency."""
    rows = await session.execute(
        select(
            CanonicalEntitySource.source_name, CanonicalEntitySource.source_record_id
        )
        .where(CanonicalEntitySource.canonical_entity_id > canonical_entity_id)
        .order_by(CanonicalEntitySource.last_seen_at.desc())
    )
    return [
        {"source_name": source_name, "source_record_id": source_record_id}
        for source_name, source_record_id in rows
    ]


async def _upsert_source(
    session: AsyncSession,
    entity: CanonicalEntity,
    *,
    source_name: str,
    source_record_id: str,
    source_snapshot: dict[str, Any],
    source_url: str | None,
    source_fingerprint: str | None,
) -> uuid.UUID | None:
    """Idempotently link a source record to a canonical entity.

    Returns the previous ``canonical_entity_id`` (if the source moved) so the
    caller can refresh both affected entities' ``source_count``.

    The unique constraint on ``(workspace_id, entity_type, source_name,
    source_record_id)`` means a source record can only belong to one active
    canonical entity per domain.  On conflict we move the source to the
    matching entity and update its redacted snapshot.
    """
    previous_id = await _find_previous_canonical_entity_id(
        session,
        entity.workspace_id,
        entity.entity_type,
        source_name,
        source_record_id,
    )

    now = _now()
    upsert_stmt = (
        insert(CanonicalEntitySource)
        .values(
            id=uuid.uuid4(),
            workspace_id=entity.workspace_id,
            canonical_entity_id=entity.id,
            entity_type=entity.entity_type,
            source_name=source_name,
            source_record_id=source_record_id,
            source_snapshot=source_snapshot,
            source_url=source_url,
            source_fingerprint=source_fingerprint,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
        )
        .on_conflict_do_update(
            index_elements=[
                "workspace_id",
                "entity_type",
                "source_name",
                "source_record_id",
            ],
            set_={
                "canonical_entity_id": entity.id,
                "source_snapshot": source_snapshot,
                "source_url": source_url,
                "source_fingerprint": source_fingerprint,
                "last_seen_at": now,
            },
        )
    )
    await session.execute(upsert_stmt)
    return previous_id if previous_id != entity.id else None


async def upsert_canonical_entity(
    session: AsyncSession,
    workspace_id: int,
    entity_type: str,
    fingerprint: str,
    title: str | None,
    data: dict[str, Any],
    search_text: str | None,
    *,
    source_name: str,
    source_record_id: str,
    source_snapshot: dict[str, Any] | None = None,
    source_url: str | None = None,
    source_fingerprint: str | None = None,
    confidence_score: float = 0.0,
    conflict_flags: list[dict[str, Any]] | None = None,
    actor: str | None = None,
    merge_method: str | None = None,
    expected_version: int | None = None,
) -> CanonicalEntity:
    """Upsert a canonical entity and its source provenance.

    The workspace ID is explicit; tenant context is set in the current SQL
    transaction before any canonical read or write.
    """
    await set_canonical_workspace_id(session, workspace_id)

    data = redact_canonical_data(entity_type, data)
    source_snapshot = redact_source_snapshot(entity_type, source_snapshot or {})

    existing = await session.scalar(
        select(CanonicalEntity)
        .where(
            CanonicalEntity.workspace_id == workspace_id,
            CanonicalEntity.entity_type == entity_type,
            CanonicalEntity.fingerprint == fingerprint,
        )
        .with_for_update()
    )

    now = _now()
    conflict_flags = conflict_flags or []

    if existing is not None:
        if expected_version is not None and existing.version != expected_version:
            raise ConcurrentUpdateError(
                f"Expected version {expected_version}, found {existing.version}"
            )
        previous_data = existing.canonical_data
        previous_version = existing.version
        previous_source_ids = await _source_ids_for_entity(session, existing.id)

        previous_source_entity_id = await _upsert_source(
            session,
            existing,
            source_name=source_name,
            source_record_id=source_record_id,
            source_snapshot=source_snapshot,
            source_url=source_url,
            source_fingerprint=source_fingerprint,
        )
        source_moved = (
            previous_source_entity_id is not None
            and previous_source_entity_id != existing.id
        )

        # A re-poll of an unchanged article is the common RSS path: identical
        # title, data, search text, conflict flags and confidence with the
        # same source linkage. Treating it as a merge churned the version and
        # merge history on every poll; instead only refresh last_seen_at.
        content_unchanged = (
            title == existing.canonical_title
            and data == existing.canonical_data
            and not _is_search_text_changed(existing, search_text)
            and conflict_flags == (existing.conflict_flags or [])
            and confidence_score == existing.confidence_score
        )

        if not content_unchanged or source_moved:
            new_version = previous_version + 1

            existing.canonical_title = title
            existing.canonical_data = data
            existing.confidence_score = confidence_score
            existing.conflict_flags = conflict_flags
            existing.version = new_version
            existing.last_seen_at = now

            # ponytail: simple conflict-resolution heuristic for day one — prefer
            # longer search text and mark the embedding stale when it changes.
            if _is_search_text_changed(existing, search_text):
                existing.search_text = search_text
                existing.embedding_status = "pending"
                existing.embedding = None
                existing.embedding_model_name = None
                existing.embedding_content_hash = None

            existing.source_count = await _update_source_count(session, existing.id)
            if source_moved:
                previous_count = await _update_source_count(
                    session, previous_source_entity_id
                )
                previous_entity = await session.get(
                    CanonicalEntity, previous_source_entity_id
                )
                if previous_entity:
                    previous_entity.source_count = previous_count

            new_source_ids = await _source_ids_for_entity(session, existing.id)

            await record_merge_history(
                session,
                entity=existing,
                previous_data=previous_data,
                new_data=data,
                operation="merge",
                actor=actor,
                conflicts=conflict_flags,
                method=merge_method,
                previous_version=previous_version,
                new_version=new_version,
                previous_source_ids=previous_source_ids,
                new_source_ids=new_source_ids,
            )

            # The version was locked with ``with_for_update`` and the caller
            # passed ``expected_version`` to guard against a concurrent merge
            # that happened while waiting for the lock.  The ORM flush inside
            # ``record_merge_history`` writes the row, so the explicit extra
            # UPDATE is not needed and was actively wrong (it matched
            # ``new_version``, not the locked version).

            await _enqueue_embedding_backfill(existing)
        else:
            existing.last_seen_at = now
            existing.source_count = await _update_source_count(session, existing.id)

        return existing

    # New canonical entity.
    if expected_version is not None and expected_version != 0:
        raise ConcurrentUpdateError(
            f"Expected version {expected_version}, but entity does not exist"
        )
    entity = CanonicalEntity(
        workspace_id=workspace_id,
        entity_type=entity_type,
        canonical_title=title,
        canonical_data=data,
        fingerprint=fingerprint,
        search_text=search_text,
        source_count=1,
        confidence_score=confidence_score,
        conflict_flags=conflict_flags,
        version=1,
        first_seen_at=now,
        last_seen_at=now,
        embedding_status="pending",
    )
    session.add(entity)
    await session.flush()

    previous_source_entity_id = await _upsert_source(
        session,
        entity,
        source_name=source_name,
        source_record_id=source_record_id,
        source_snapshot=source_snapshot,
        source_url=source_url,
        source_fingerprint=source_fingerprint,
    )
    entity.source_count = await _update_source_count(session, entity.id)
    if previous_source_entity_id and previous_source_entity_id != entity.id:
        previous_count = await _update_source_count(session, previous_source_entity_id)
        previous_entity = await session.get(CanonicalEntity, previous_source_entity_id)
        if previous_entity:
            previous_entity.source_count = previous_count

    new_source_ids = await _source_ids_for_entity(session, entity.id)

    await record_merge_history(
        session,
        entity=entity,
        previous_data={},
        new_data=data,
        operation="create",
        actor=actor,
        conflicts=conflict_flags,
        method=merge_method,
        previous_version=0,
        new_version=1,
        previous_source_ids=[],
        new_source_ids=new_source_ids,
    )

    await _enqueue_embedding_backfill(entity)
    return entity


def _revert_data(previous_data: dict[str, Any]) -> dict[str, Any]:
    """Restore canonical_data without clobbering identity/system columns."""
    data = dict(previous_data)
    for key in ("id", "workspace_id", "entity_type", "fingerprint"):
        data.pop(key, None)
    return data


def _conflict_matches_field(conflict: dict[str, Any], field: str) -> bool:
    """Day-one heuristic: a conflict matches a field by its declared field or type.

    ponytail: conflict schema is not stable yet; this is a best-effort match.
    A future version should carry an explicit ``field`` key and a conflict id.
    """
    normalized = field.lower().replace("_", "").replace("-", "")
    conflict_field = (
        str(conflict.get("field", "")).lower().replace("_", "").replace("-", "")
    )
    conflict_type = (
        str(conflict.get("type", "")).lower().replace("_", "").replace("-", "")
    )
    return (
        conflict_field == normalized
        or normalized in conflict_type
        or (conflict_type and conflict_type in normalized)
    )


async def revert_canonical_entity(
    session: AsyncSession,
    workspace_id: int,
    entity_id: uuid.UUID,
    target_history_id: uuid.UUID,
    actor: str | None = None,
) -> CanonicalEntity:
    """Revert a canonical entity to the state recorded in a target history entry.

    The revert is itself a new audited transition. It fails if the entity has
    moved past the target history version, ensuring it never overwrites newer
    changes.
    """
    await set_canonical_workspace_id(session, workspace_id)

    current = await session.scalar(
        select(CanonicalEntity)
        .where(
            CanonicalEntity.id == entity_id,
            CanonicalEntity.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if current is None:
        raise RevertNotPossibleError(f"Entity {entity_id} not found")

    history = await session.scalar(
        select(CanonicalMergeHistory).where(
            CanonicalMergeHistory.id == target_history_id,
            CanonicalMergeHistory.canonical_entity_id == entity_id,
        )
    )
    if history is None:
        raise RevertNotPossibleError(
            f"History entry {target_history_id} not found for entity {entity_id}"
        )

    if current.version != history.new_version:
        raise RevertNotPossibleError(
            f"Entity version {current.version} does not match history version {history.new_version}"
        )

    previous_version = current.version
    new_version = previous_version + 1
    previous_data = dict(current.canonical_data)
    reverted_data = _revert_data(history.previous_data)
    current_source_ids = await _source_ids_for_entity(session, current.id)

    # ponytail: search_text and canonical_title are not stored per-history yet,
    # so we revert canonical_data only and conservatively mark embedding pending.
    result = await session.execute(
        update(CanonicalEntity)
        .where(
            CanonicalEntity.id == current.id,
            CanonicalEntity.version == previous_version,
        )
        .values(
            canonical_data=reverted_data,
            version=new_version,
            last_seen_at=_now(),
            embedding_status="pending",
            embedding=None,
            embedding_model_name=None,
            embedding_content_hash=None,
        )
    )
    if result.rowcount != 1:
        raise ConcurrentUpdateError(f"Entity {entity_id} changed during revert")

    await session.refresh(current)

    await record_merge_history(
        session,
        entity=current,
        previous_data=previous_data,
        new_data=reverted_data,
        operation="revert",
        actor=actor,
        conflicts=history.conflicts,
        method="revert_to_history",
        previous_version=previous_version,
        new_version=new_version,
        previous_source_ids=current_source_ids,
        new_source_ids=current_source_ids,
    )

    await _enqueue_embedding_backfill(current)
    return current


async def resolve_canonical_conflict(
    session: AsyncSession,
    workspace_id: int,
    entity_id: uuid.UUID,
    field: str,
    value: Any,
    actor: str | None = None,
) -> CanonicalEntity:
    """Manually resolve a conflict by writing a field value and recording history."""
    await set_canonical_workspace_id(session, workspace_id)

    entity = await session.scalar(
        select(CanonicalEntity)
        .where(
            CanonicalEntity.id == entity_id,
            CanonicalEntity.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if entity is None:
        raise RevertNotPossibleError(f"Entity {entity_id} not found")

    previous_version = entity.version
    new_version = previous_version + 1
    previous_data = dict(entity.canonical_data)
    new_data = {**previous_data, field: value}
    resolved_conflicts = [
        c for c in entity.conflict_flags if _conflict_matches_field(c, field)
    ]
    new_conflict_flags = [
        c for c in entity.conflict_flags if not _conflict_matches_field(c, field)
    ]
    current_source_ids = await _source_ids_for_entity(session, entity.id)

    if field == "canonical_title":
        entity.canonical_title = value

    new_data = redact_canonical_data(entity.entity_type, new_data)
    entity.canonical_data = new_data
    entity.conflict_flags = new_conflict_flags
    entity.version = new_version
    entity.last_seen_at = _now()
    # Conservative: data changed, so recompute embedding on next backfill.
    entity.embedding_status = "pending"
    entity.embedding = None
    entity.embedding_model_name = None
    entity.embedding_content_hash = None

    await record_merge_history(
        session,
        entity=entity,
        previous_data=previous_data,
        new_data=new_data,
        operation="resolve",
        actor=actor,
        conflicts=resolved_conflicts,
        method="manual",
        previous_version=previous_version,
        new_version=new_version,
        previous_source_ids=current_source_ids,
        new_source_ids=current_source_ids,
    )

    await _enqueue_embedding_backfill(entity)
    return entity


async def retry_persist_outbox(
    session: AsyncSession,
    outbox_id: uuid.UUID,
    workspace_id: int,
) -> CanonicalPersistOutbox | None:
    """Mark an outbox row as processing and return its payload for retry."""
    await set_canonical_workspace_id(session, workspace_id)
    await session.execute(
        update(CanonicalPersistOutbox)
        .where(CanonicalPersistOutbox.id == outbox_id)
        .values(
            status="processing",
            retry_count=CanonicalPersistOutbox.retry_count + 1,
            updated_at=_now(),
        )
    )
    return await session.get(CanonicalPersistOutbox, outbox_id)
