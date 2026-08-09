"""Repository for long-term memory CRUD, search, and deduplication."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import Float, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import (
    Memory,
    MemoryRelation,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    MemoryVersion,
)
from app.services.memory.vector import (
    VectorValidationError,
    validate_embedding_vector,
    validate_single_embedding_result,
)
from app.services.token_tracking_service import record_token_usage
from app.utils.document_converters import embed_texts

logger = logging.getLogger(__name__)


def _validate_vector(embedding: Any) -> np.ndarray:
    """Validate a caller-supplied embedding before dedup SQL/assignment/flush (D6)."""
    return validate_embedding_vector(
        embedding, dimension=config.embedding_model_instance.dimension
    )


class MemoryRepository:
    """Data-access layer for unified memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Deferred ``memory.changed`` payloads for ``commit=False`` batch writes
        # (auto-extraction): the caller commits once at the end, then calls
        # ``flush_pending_memory_changed`` so each durable memory is announced
        # exactly once (never per-flush). Entries are ``(workspace_id, payload)``
        # dicts built while the ORM row is still loaded, so flushing after the
        # caller's commit never triggers async lazy-load on expired attributes.
        self._pending_memory_changed: list[tuple[int, dict[str, Any]]] = []

    async def _embed(
        self,
        content: str,
        workspace_id: int | None,
        user_id: UUID | None,
    ) -> np.ndarray:
        try:
            embeddings = await asyncio.to_thread(embed_texts, [content])
        except Exception as exc:
            raise VectorValidationError("provider_error") from exc
        embedding = validate_single_embedding_result(embeddings)
        embedding = _validate_vector(embedding)

        # Best-effort token accounting: estimate one token per ~4 chars.
        # User memory has no workspace, so token usage is recorded only when a
        # workspace context exists.
        if user_id is not None and workspace_id is not None:
            estimated_tokens = max(1, len(content) // 4)
            await record_token_usage(
                self.session,
                usage_type="memory_embedding",
                workspace_id=workspace_id,
                user_id=user_id,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=estimated_tokens,
                cost_micros=0,
            )
        return embedding

    async def _find_near_duplicate(
        self,
        workspace_id: int | None,
        content: str,
        embedding: np.ndarray,
        *,
        created_by_id: UUID | None = None,
        content_match_required: bool = True,
    ) -> Memory | None:
        conditions = [
            Memory.workspace_id == workspace_id,
            Memory.embedding.op("<=>", return_type=Float)(embedding) < 0.08,
        ]
        # User-scoped memories have no workspace; scope deduplication to the
        # owner so one user's personal memory cannot overwrite another's.
        if workspace_id is None and created_by_id is not None:
            conditions.append(Memory.created_by_id == created_by_id)

        stmt = (
            select(Memory)
            .where(*conditions)
            .order_by(Memory.embedding.op("<=>", return_type=Float)(embedding))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            return None
        if not content_match_required:
            return existing
        if existing.content.strip().lower() == content.strip().lower():
            return existing
        return None

    async def _load_with_versions(self, memory: Memory) -> Memory:
        result = await self.session.execute(
            select(Memory)
            .options(selectinload(Memory.versions))
            .where(Memory.id == memory.id)
        )
        loaded = result.scalar_one_or_none()
        return loaded if loaded is not None else memory

    async def _persist(self, *, commit: bool) -> None:
        """Commit when running standalone, or flush to keep the caller's
        transaction open (e.g. batch extraction that commits once at the end so
        a mid-loop crash leaves nothing behind)."""
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()

    async def _emit_memory_changed(
        self,
        memory: Memory | None,
        *,
        change: str,
        commit: bool,
        automation_run_id: int | None,
    ) -> None:
        """Announce a durable memory write as ``memory.changed`` (Story 6.5, AC-1).

        Immediate (``commit=True``) writes publish right away; batch
        (``commit=False``) writes are buffered and published by the caller via
        ``flush_pending_memory_changed`` after its final commit, so
        auto-extraction announces each durable memory exactly once (not
        per-flush).

        Loop guard (AC-5, mechanism 1): the origin is resolved from the explicit
        ``automation_run_id`` kwarg OR, when absent, the contextvar the run
        executor stamps (``get_current_automation_run_id``) so in-process writes
        inside an automation run are recognised WITHOUT a hand-passed kwarg. An
        automation-origin write is never announced, so a memory-writing
        automation cannot re-fire its own ``memory_change`` trigger. Truthiness
        is used consistently with the selector's drop (``0`` is not a valid run
        id — treated as no origin).

        Only workspace-scoped memories are announced (user-scoped memory has no
        workspace to route the event to). A bus failure never fails the write.
        """
        run_id = automation_run_id
        if run_id is None:
            # Lazy import: the memory repository is imported while ``app.automations``
            # self-registers (the continue_research action pulls in the memory
            # search/citations modules), so importing the automations runtime at
            # module top level here would risk a partial-import cycle. At call
            # time everything is loaded, so a function-level import is safe.
            from app.automations.runtime.origin import get_current_automation_run_id

            run_id = get_current_automation_run_id()
        if run_id:  # automation origin (truthy) → skip: loop guard, mechanism 1
            return
        if memory is None or memory.workspace_id is None or memory.id is None:
            return

        # Build the payload NOW, while the ORM row is loaded, so a deferred flush
        # after the caller's commit never touches expired attributes.
        payload = self._build_memory_changed_payload(memory, change=change)
        if commit:
            await self._publish_memory_changed(memory.workspace_id, payload)
        else:
            self._pending_memory_changed.append((memory.workspace_id, payload))

    @staticmethod
    def _build_memory_changed_payload(memory: Memory, *, change: str) -> dict[str, Any]:
        from app.event_bus.events.memory_changed import MemoryChangedPayload

        return MemoryChangedPayload(
            memory_id=memory.id,
            workspace_id=memory.workspace_id,
            type=getattr(memory.type, "value", memory.type),
            tags=list(memory.tags or []),
            change=change,
            source_type=getattr(memory.source_type, "value", memory.source_type),
            research_thread_id=memory.research_thread_id,
            # Repo-emitted events are non-origin by construction (origin writes
            # are skipped above); the field carries the selector's contract.
            automation_run_id=None,
        ).model_dump(mode="json")

    async def _publish_memory_changed(
        self, workspace_id: int, payload: dict[str, Any]
    ) -> None:
        """Best-effort publish; a bus failure must never fail the memory write."""
        try:
            from app.event_bus import bus
            from app.event_bus.events.memory_changed import EVENT_TYPE

            await bus.publish(EVENT_TYPE, payload, workspace_id=workspace_id)
        except Exception:  # best-effort: never fail a write on a bus error
            logger.warning(
                "best-effort memory.changed emission failed for memory %s",
                payload.get("memory_id"),
                exc_info=True,
            )

    async def flush_pending_memory_changed(self) -> None:
        """Publish the ``memory.changed`` events buffered by ``commit=False`` writes.

        Called by batch callers (auto-extraction) AFTER their single commit, so
        each durable memory is announced exactly once. Best-effort per event;
        the buffer is drained even if a publish fails so a retry cannot re-emit.
        """
        pending, self._pending_memory_changed = self._pending_memory_changed, []
        for workspace_id, payload in pending:
            await self._publish_memory_changed(workspace_id, payload)

    async def create_memory(
        self,
        *,
        workspace_id: int | None,
        content: str,
        type: str | MemoryType = MemoryType.SEMANTIC,
        source_type: str | MemorySourceType = MemorySourceType.MANUAL,
        source_id: int | None = None,
        source_run_id: UUID | None = None,
        source_capability: str | None = None,
        source_input: Any | None = None,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        research_thread_id: int | None = None,
        created_by_id: UUID | None = None,
        embedding: np.ndarray | list[float] | None = None,
        update_on_duplicate: bool = False,
        commit: bool = True,
        automation_run_id: int | None = None,
        client_id: str | None = None,
        agent_id: str | None = None,
    ) -> Memory:
        if isinstance(type, str):
            type = MemoryType(type)
        if isinstance(source_type, str):
            source_type = MemorySourceType(source_type)

        if client_id:
            tags = list(tags or [])
            tags.append(f"client:{client_id}")

        if embedding is None:
            embedding = await self._embed(
                content, workspace_id=workspace_id, user_id=created_by_id
            )
        else:
            embedding = _validate_vector(embedding)

        existing = await self._find_near_duplicate(
            workspace_id,
            content,
            embedding,
            created_by_id=created_by_id,
            content_match_required=not update_on_duplicate,
        )
        if existing is not None:
            if update_on_duplicate:
                # Auto-dedup updates content but must NOT re-attribute a
                # shared-workspace memory: preserve the original created_by_id
                # (the version records who made the change via corrected_by_id).
                # skip_version_if_unchanged avoids version churn when a fact is
                # re-derived identically (retries / repeated turns).
                updated = await self.update_memory(
                    existing.id,
                    corrected_content=content,
                    corrected_by_id=created_by_id,
                    source_type=source_type,
                    source_id=source_id,
                    source_run_id=source_run_id,
                    source_capability=source_capability,
                    source_input=source_input,
                    tags=tags,
                    confidence=confidence,
                    research_thread_id=research_thread_id,
                    embedding=embedding,
                    skip_version_if_unchanged=True,
                    commit=commit,
                    automation_run_id=automation_run_id,
                )
                if updated is not None:
                    return updated
                # The duplicate was deleted concurrently between find and
                # update; fall through to insert a fresh row so we always
                # return a Memory (matches the -> Memory contract).
            else:
                # This branch is only reached for a CONTENT-matching duplicate
                # (content_match_required=True), so ``content`` is effectively
                # unchanged — but other fields (tags/type/source) may differ.
                content_changed = existing.content != content
                existing.content = content
                existing.type = type
                existing.source_type = source_type
                existing.source_id = source_id
                # Story 3.13 (D6): a run-derived fact that semantically matches
                # an existing memory must not silently lose its run identity —
                # the idempotency guard and the recall citation both key off
                # ``source_run_id``. Only overwrite when a run id is supplied so
                # a chat-origin re-write cannot erase an earlier run's
                # provenance.
                if source_run_id is not None:
                    existing.source_run_id = source_run_id
                if source_capability is not None and existing.source_capability is None:
                    existing.source_capability = source_capability
                if source_input is not None and existing.source_input is None:
                    existing.source_input = source_input
                existing.tags = tags or []
                existing.confidence = confidence
                # Only overwrite the thread/tenant association when a new one is
                # given, so re-creating a duplicate doesn't silently wipe it.
                if research_thread_id is not None:
                    existing.research_thread_id = research_thread_id
                if client_id is not None:
                    existing.client_id = client_id
                if agent_id is not None:
                    existing.agent_id = agent_id
                existing.updated_at = datetime.now(UTC)
                self.session.add(existing)
                await self._persist(commit=commit)
                self.session.expire(existing, ["versions"])
                loaded = await self._load_with_versions(existing)
                # No-op content re-write must not announce ``change="updated"``:
                # a spurious event would re-fire ``memory_change`` triggers.
                if content_changed:
                    await self._emit_memory_changed(
                        loaded,
                        change="updated",
                        commit=commit,
                        automation_run_id=automation_run_id,
                    )
                return loaded

        memory = Memory(
            workspace_id=workspace_id,
            content=content,
            embedding=embedding,
            type=type,
            source_type=source_type,
            source_id=source_id,
            source_run_id=source_run_id,
            source_capability=source_capability,
            source_input=source_input,
            tags=tags or [],
            confidence=confidence,
            research_thread_id=research_thread_id,
            created_by_id=created_by_id,
            client_id=client_id,
            agent_id=agent_id,
        )
        self.session.add(memory)
        await self._persist(commit=commit)
        self.session.expire(memory, ["versions"])
        loaded = await self._load_with_versions(memory)
        await self._emit_memory_changed(
            loaded,
            change="created",
            commit=commit,
            automation_run_id=automation_run_id,
        )
        return loaded

    async def update_memory(
        self,
        memory_id: int,
        *,
        corrected_content: str,
        corrected_by_id: UUID | None = None,
        source_type: str | MemorySourceType | None = None,
        source_id: int | None = None,
        source_run_id: UUID | None = None,
        source_capability: str | None = None,
        source_input: Any | None = None,
        tags: list[str] | None = None,
        confidence: float | None = None,
        research_thread_id: int | None = None,
        created_by_id: UUID | None = None,
        embedding: np.ndarray | list[float] | None = None,
        skip_version_if_unchanged: bool = False,
        commit: bool = True,
        automation_run_id: int | None = None,
        client_id: str | None = None,
        agent_id: str | None = None,
    ) -> Memory | None:
        result = await self.session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            return None

        content_changed = memory.content != corrected_content
        if not (skip_version_if_unchanged and not content_changed):
            version = MemoryVersion(
                memory_id=memory.id,
                previous_content=memory.content,
                corrected_content=corrected_content,
                corrected_by_id=corrected_by_id,
            )
            self.session.add(version)

        memory.content = corrected_content
        memory.updated_at = datetime.now(UTC)

        if source_type is not None:
            if isinstance(source_type, str):
                source_type = MemorySourceType(source_type)
            memory.source_type = source_type
        if source_id is not None:
            memory.source_id = source_id
        # Soft run provenance is only ever set, never cleared, by an update: see
        # the dedupe note in ``create_memory``.
        if source_run_id is not None:
            memory.source_run_id = source_run_id
        # Recipe is an immutable snapshot (Story 9.6a): only seed it when the
        # memory does not already carry one. Re-validation creates a new memory
        # or version rather than mutating the original recipe.
        if source_capability is not None and memory.source_capability is None:
            memory.source_capability = source_capability
        if source_input is not None and memory.source_input is None:
            memory.source_input = source_input
        if tags is not None:
            memory.tags = tags
        if confidence is not None:
            memory.confidence = confidence
        if research_thread_id is not None:
            memory.research_thread_id = research_thread_id
        if created_by_id is not None:
            memory.created_by_id = created_by_id
        if client_id is not None:
            memory.client_id = client_id
        if agent_id is not None:
            memory.agent_id = agent_id

        # Re-embed when content changes, unless an embedding is provided.
        if embedding is not None:
            memory.embedding = _validate_vector(embedding)
        elif content_changed:
            new_embedding = await self._embed(
                corrected_content,
                workspace_id=memory.workspace_id,
                user_id=corrected_by_id,
            )
            memory.embedding = new_embedding

        self.session.add(memory)
        await self._persist(commit=commit)
        self.session.expire(memory, ["versions"])
        loaded = await self._load_with_versions(memory)
        # Gate on content_changed: a no-op update (e.g. a re-derived identical
        # fact via skip_version_if_unchanged) must not announce
        # ``change="updated"`` — a spurious event would re-fire memory_change
        # triggers (Story 6.5).
        if content_changed:
            await self._emit_memory_changed(
                loaded,
                change="updated",
                commit=commit,
                automation_run_id=automation_run_id,
            )
        return loaded

    async def get_memory(self, memory_id: int) -> Memory | None:
        result = await self.session.execute(
            select(Memory)
            .options(selectinload(Memory.versions))
            .where(Memory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def list_memories(
        self,
        *,
        workspace_id: int,
        limit: int = 20,
        type: str | MemoryType | None = None,
        tags: list[str] | None = None,
        client_id: str | None = None,
    ) -> list[Memory]:
        """List workspace memories, newest first, with optional type/tags filters."""
        conditions = [Memory.workspace_id == workspace_id]
        if client_id is not None:
            conditions.append(Memory.client_id == client_id)
        else:
            conditions.append(Memory.client_id.is_(None))
        if type is not None:
            if isinstance(type, MemoryType):
                conditions.append(Memory.type == type.value)
            elif isinstance(type, str):
                try:
                    conditions.append(Memory.type == MemoryType(type).value)
                except ValueError as exc:
                    raise ValueError(f"invalid memory type {type!r}") from exc
            else:
                raise ValueError(f"invalid memory type {type!r}")
        if tags:
            conditions.append(Memory.tags.op("&&")(tags))
        result = await self.session.execute(
            select(Memory)
            .options(selectinload(Memory.versions))
            .where(*conditions)
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_memory(self, memory_id: int) -> bool:
        result = await self.session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            return False
        await self.session.delete(memory)
        await self.session.commit()
        return True

    async def add_relation(
        self,
        *,
        workspace_id: int,
        from_memory_id: int,
        to_memory_id: int | None,
        relation_type: str | MemoryRelationType = MemoryRelationType.RELATED,
        weight: float = 1.0,
    ) -> MemoryRelation:
        if isinstance(relation_type, str):
            relation_type = MemoryRelationType(relation_type)
        relation = MemoryRelation(
            workspace_id=workspace_id,
            from_memory_id=from_memory_id,
            to_memory_id=to_memory_id,
            relation_type=relation_type,
            weight=weight,
        )
        self.session.add(relation)
        await self.session.commit()
        return relation
