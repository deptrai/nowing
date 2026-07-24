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

from app.db import (
    Memory,
    MemoryRelation,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    MemoryVersion,
)
from app.services.token_tracking_service import record_token_usage
from app.utils.document_converters import embed_texts

logger = logging.getLogger(__name__)


def _as_np(embedding: Any) -> np.ndarray:
    return np.asarray(embedding, dtype=np.float32)


class MemoryRepository:
    """Data-access layer for unified memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _embed(
        self,
        content: str,
        workspace_id: int | None,
        user_id: UUID | None,
    ) -> np.ndarray:
        embeddings = await asyncio.to_thread(embed_texts, [content])
        embedding = embeddings[0]

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

    async def create_memory(
        self,
        *,
        workspace_id: int | None,
        content: str,
        type: str | MemoryType = MemoryType.SEMANTIC,
        source_type: str | MemorySourceType = MemorySourceType.MANUAL,
        source_id: int | None = None,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        research_thread_id: int | None = None,
        created_by_id: UUID | None = None,
        embedding: np.ndarray | list[float] | None = None,
        update_on_duplicate: bool = False,
        commit: bool = True,
    ) -> Memory:
        if isinstance(type, str):
            type = MemoryType(type)
        if isinstance(source_type, str):
            source_type = MemorySourceType(source_type)

        if embedding is None:
            embedding = await self._embed(
                content, workspace_id=workspace_id, user_id=created_by_id
            )
        else:
            embedding = _as_np(embedding)

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
                    tags=tags,
                    confidence=confidence,
                    research_thread_id=research_thread_id,
                    embedding=embedding,
                    skip_version_if_unchanged=True,
                    commit=commit,
                )
                if updated is not None:
                    return updated
                # The duplicate was deleted concurrently between find and
                # update; fall through to insert a fresh row so we always
                # return a Memory (matches the -> Memory contract).
            else:
                existing.content = content
                existing.type = type
                existing.source_type = source_type
                existing.source_id = source_id
                existing.tags = tags or []
                existing.confidence = confidence
                # Only overwrite the thread association when a new one is given,
                # so re-creating a duplicate doesn't silently wipe it.
                if research_thread_id is not None:
                    existing.research_thread_id = research_thread_id
                existing.updated_at = datetime.now(UTC)
                self.session.add(existing)
                await self._persist(commit=commit)
                self.session.expire(existing, ["versions"])
                return await self._load_with_versions(existing)

        memory = Memory(
            workspace_id=workspace_id,
            content=content,
            embedding=embedding,
            type=type,
            source_type=source_type,
            source_id=source_id,
            tags=tags or [],
            confidence=confidence,
            research_thread_id=research_thread_id,
            created_by_id=created_by_id,
        )
        self.session.add(memory)
        await self._persist(commit=commit)
        self.session.expire(memory, ["versions"])
        return await self._load_with_versions(memory)

    async def update_memory(
        self,
        memory_id: int,
        *,
        corrected_content: str,
        corrected_by_id: UUID | None = None,
        source_type: str | MemorySourceType | None = None,
        source_id: int | None = None,
        tags: list[str] | None = None,
        confidence: float | None = None,
        research_thread_id: int | None = None,
        created_by_id: UUID | None = None,
        embedding: np.ndarray | list[float] | None = None,
        skip_version_if_unchanged: bool = False,
        commit: bool = True,
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
        if tags is not None:
            memory.tags = tags
        if confidence is not None:
            memory.confidence = confidence
        if research_thread_id is not None:
            memory.research_thread_id = research_thread_id
        if created_by_id is not None:
            memory.created_by_id = created_by_id

        # Re-embed when content changes, unless an embedding is provided.
        if embedding is not None:
            memory.embedding = _as_np(embedding)
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
        return await self._load_with_versions(memory)

    async def get_memory(self, memory_id: int) -> Memory | None:
        result = await self.session.execute(
            select(Memory)
            .options(selectinload(Memory.versions))
            .where(Memory.id == memory_id)
        )
        return result.scalar_one_or_none()

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
