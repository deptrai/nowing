"""Memory browser service: list, filter, detail, review flag (Story 29.5 / FR-104)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Memory,
    MemoryRelation,
    MemoryVersion,
    ResearchThread,
    User,
)
from app.schemas.memory_browser import (
    MemoryBrowserCreator,
    MemoryBrowserDetailCitations,
    MemoryBrowserDetailResponse,
    MemoryBrowserListItem,
    MemoryBrowserListResponse,
    MemoryRelationRead,
    MemoryReviewQueueRead,
    MemoryVersionRead,
    ResearchThreadSummary,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
SNIPPET_LENGTH = 120


class MemoryBrowserService:
    """Service for the analyst memory browser."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # List / filter
    # ------------------------------------------------------------------

    async def list_memories(
        self,
        workspace_id: int,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        source_types: list[str] | None = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        created_by: uuid.UUID | None = None,
        keyword: str | None = None,
        client_id: str | None = None,
        sort: str = "created_at",
        sort_dir: str = "desc",
    ) -> MemoryBrowserListResponse:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if confidence_min is not None and confidence_max is not None and confidence_min > confidence_max:
            raise ValueError("confidence_min cannot be greater than confidence_max")

        conditions = self._base_conditions(workspace_id, client_id)

        if source_types:
            conditions.append(Memory.source_type.in_(source_types))

        if confidence_min is not None:
            conditions.append(func.coalesce(Memory.confidence, 0.0) >= confidence_min)
        if confidence_max is not None:
            conditions.append(func.coalesce(Memory.confidence, 0.0) <= confidence_max)

        if created_after is not None:
            conditions.append(Memory.created_at >= created_after)
        if created_before is not None:
            conditions.append(Memory.created_at <= created_before)

        if created_by is not None:
            conditions.append(Memory.created_by_id == created_by)

        if keyword and keyword.strip():
            q = keyword.strip()
            # Use content_search when encryption is enabled (it stores
            # tsvector literals of plaintext); fall back to content otherwise.
            tsvector = func.to_tsvector(
                "english",
                func.coalesce(Memory.content_search, Memory.content),
            )
            tsquery = func.plainto_tsquery("english", q)
            conditions.append(tsvector.op("@@")(tsquery))

        order_by = self._order_by_clause(sort, sort_dir)

        stmt = (
            select(Memory)
            .where(*conditions)
            .order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        total = await self._count_total(conditions)

        flag_status_map = await self._load_review_status(workspace_id, [r.id for r in rows])
        version_count_map = await self._load_version_counts(workspace_id, [r.id for r in rows])

        memory_ids = [r.id for r in rows if r.created_by_id is not None]
        creator_map = await self._load_creator_emails(workspace_id, memory_ids)

        items = [
            MemoryBrowserListItem(
                id=row.id,
                content_snippet=self._snippet(row.content or "", SNIPPET_LENGTH),
                source_type=row.source_type.value if hasattr(row.source_type, "value") else str(row.source_type),  # type: ignore[attr-defined]
                source_url=self._derive_source_url(workspace_id, row),
                confidence=row.confidence,
                created_at=row.created_at,
                updated_at=row.updated_at,
                created_by=MemoryBrowserCreator(
                    id=str(row.created_by_id),
                    email=creator_map.get(row.created_by_id),
                ) if row.created_by_id else None,
                version_count=version_count_map.get(row.id, 0),
                flag_status=flag_status_map.get(row.id),
            )
            for row in rows
        ]

        return MemoryBrowserListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _count_total(self, conditions: list[Any]) -> int:
        stmt = select(func.count(Memory.id)).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_memory_detail(self, workspace_id: int, memory_id: int) -> MemoryBrowserDetailResponse:
        stmt = select(Memory).where(
            Memory.id == memory_id,
            Memory.workspace_id == workspace_id,
            Memory.archived_at.is_(None),
        )
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory is None:
            raise Exception(f"Memory {memory_id} not found")

        self._decrypt_memory(memory)

        creator = None
        if memory.created_by_id is not None:
            email_map = await self._load_creator_emails(workspace_id, [memory.id])
            email = email_map.get(memory.created_by_id)
            creator = MemoryBrowserCreator(id=str(memory.created_by_id), email=email)

        return MemoryBrowserDetailResponse(
            id=memory.id,
            workspace_id=memory.workspace_id,
            content=memory.content or "",
            source_type=memory.source_type.value if hasattr(memory.source_type, "value") else str(memory.source_type),
            source_url=self._derive_source_url(workspace_id, memory),
            confidence=memory.confidence,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            created_by=creator,
            citations=MemoryBrowserDetailCitations(
                source_type=memory.source_type.value if hasattr(memory.source_type, "value") else str(memory.source_type),
                source_url=self._derive_source_url(workspace_id, memory),
                source_run_id=str(memory.source_run_id) if memory.source_run_id else None,
                source_uuid=str(memory.source_uuid) if memory.source_uuid else None,
                source_entity_type=memory.source_entity_type,
                source_id=memory.source_id,
                source_capability=memory.source_capability,
                source_input=memory.source_input,
            ),
            versions=await self._build_versions(memory),
            research_thread=await self._build_thread(workspace_id, memory.research_thread_id),
            relations=await self._build_relations(memory),
        )

    # ------------------------------------------------------------------
    # Review flag
    # ------------------------------------------------------------------

    async def flag_for_review(
        self,
        workspace_id: int,
        memory_id: int,
        flag_reason: str,
        flagged_by: uuid.UUID,
    ) -> MemoryReviewQueueRead:
        if not flag_reason or not flag_reason.strip():
            raise ValueError("flag_reason cannot be empty")

        stmt = select(Memory).where(
            Memory.id == memory_id,
            Memory.workspace_id == workspace_id,
            Memory.archived_at.is_(None),
        )
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise Exception(f"Memory {memory_id} not found")

        # Lazy import to avoid schema cycles until the model exists.
        from app.models.memory_review_queue import MemoryReviewQueue

        queue = MemoryReviewQueue(
            memory_id=memory.id,
            workspace_id=workspace_id,
            flag_reason=flag_reason.strip(),
            flagged_by=flagged_by,
            status="open",
        )
        self.session.add(queue)
        await self.session.commit()
        await self.session.refresh(queue)
        await self._notify_owners(workspace_id, memory_id, flag_reason)

        return MemoryReviewQueueRead(
            id=queue.id,
            memory_id=queue.memory_id,
            workspace_id=queue.workspace_id,
            flag_reason=queue.flag_reason,
            flagged_by=str(queue.flagged_by),
            status=queue.status,
            created_at=queue.created_at,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _base_conditions(self, workspace_id: int, client_id: str | None) -> list[Any]:
        conditions = [
            Memory.workspace_id == workspace_id,
            Memory.archived_at.is_(None),
        ]
        if client_id is not None:
            conditions.append(Memory.client_id == client_id)
        else:
            conditions.append(Memory.client_id.is_(None))
        return conditions

    def _order_by_clause(self, sort: str, sort_dir: str) -> Any:
        mapping = {
            "created_at": Memory.created_at,
            "updated_at": Memory.updated_at,
            "confidence": Memory.confidence,
        }
        col = mapping.get(sort, Memory.created_at)
        if sort_dir == "desc":
            return col.desc()
        return col.asc()

    def _derive_source_url(self, workspace_id: int, memory: Any) -> str | None:
        if memory.source_run_id:
            return f"/dashboard/{workspace_id}/runs/{memory.source_run_id}"
        if memory.source_uuid and memory.source_entity_type:
            return f"/dashboard/{workspace_id}/{memory.source_entity_type}s/{memory.source_uuid}"
        return None

    def _snippet(self, text: str, length: int) -> str:
        if len(text) <= length:
            return text
        return text[:length].rsplit(" ", 1)[0] + "..."

    def _decrypt_memory(self, memory: Any) -> None:
        from app.services.memory.encryption import MemoryEncryptionService

        encryption = MemoryEncryptionService.from_env()
        if encryption.is_enabled() and memory.key_id:
            encryption.decrypt_memory(memory)

    async def _build_versions(self, memory: Any) -> list[MemoryVersionRead]:
        from app.services.memory.encryption import MemoryEncryptionService

        encryption = MemoryEncryptionService.from_env()
        stmt = select(MemoryVersion).where(MemoryVersion.memory_id == memory.id).order_by(MemoryVersion.created_at.asc())
        result = await self.session.execute(stmt)
        versions = list(result.scalars().all())
        out = []
        for v in versions:
            if encryption.is_enabled():
                encryption.decrypt_memory_version(v)
            corrected_by = None
            if v.corrected_by_id:
                corrected_by = MemoryBrowserCreator(id=str(v.corrected_by_id), email=None)
            out.append(
                MemoryVersionRead(
                    previous_content=v.previous_content,
                    corrected_content=v.corrected_content,
                    corrected_by=corrected_by,
                    created_at=v.created_at,
                )
            )
        return out

    async def _build_thread(self, workspace_id: int, research_thread_id: int | None) -> ResearchThreadSummary | None:
        if research_thread_id is None:
            return None
        stmt = select(ResearchThread).where(
            ResearchThread.id == research_thread_id,
            ResearchThread.workspace_id == workspace_id,
        )
        result = await self.session.execute(stmt)
        thread = result.scalar_one_or_none()
        if thread is None:
            return None

        memories_stmt = (
            select(Memory)
            .where(
                Memory.research_thread_id == thread.id,
                Memory.archived_at.is_(None),
            )
            .order_by(Memory.created_at.asc())
        )
        res = await self.session.execute(memories_stmt)
        memories = list(res.scalars().all())

        memory_ids = [m.id for m in memories]
        version_count_map = await self._load_version_counts(workspace_id, memory_ids)
        flag_status_map = await self._load_review_status(workspace_id, memory_ids)
        creator_map = await self._load_creator_emails(
            workspace_id,
            [m.id for m in memories if m.created_by_id is not None],
        )

        title = thread.title or f"Untitled thread #{thread.id}"
        return ResearchThreadSummary(
            id=thread.id,
            title=title,
            memories=[
                MemoryBrowserListItem(
                    id=m.id,
                    content_snippet=self._snippet(m.content or "", SNIPPET_LENGTH),
                    source_type=m.source_type.value if hasattr(m.source_type, "value") else str(m.source_type),
                    source_url=self._derive_source_url(workspace_id, m),
                    confidence=m.confidence,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    created_by=MemoryBrowserCreator(
                        id=str(m.created_by_id),
                        email=creator_map.get(m.created_by_id),
                    ) if m.created_by_id else None,
                    version_count=version_count_map.get(m.id, 0),
                    flag_status=flag_status_map.get(m.id),
                )
                for m in memories
            ],
        )

    async def _build_relations(self, memory: Any) -> list[MemoryRelationRead]:
        stmt = select(MemoryRelation).where(MemoryRelation.from_memory_id == memory.id)
        result = await self.session.execute(stmt)
        relations = list(result.scalars().all())
        return [
            MemoryRelationRead(
                relation_type=r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type),
                to_memory_id=r.to_memory_id,
                weight=r.weight,
            )
            for r in relations
        ]

    async def _load_version_counts(self, workspace_id: int, memory_ids: Sequence[int]) -> dict[int, int]:
        """Return memory_id -> version_count without triggering lazy loads."""
        if not memory_ids:
            return {}
        stmt = (
            select(MemoryVersion.memory_id, func.count(MemoryVersion.id))
            .where(MemoryVersion.memory_id.in_(memory_ids))
            .group_by(MemoryVersion.memory_id)
        )
        result = await self.session.execute(stmt)
        out = {}
        for row in result.all():
            if isinstance(row, (tuple, list)) and len(row) >= 2:
                out[row[0]] = row[1]
        return out

    async def _load_review_status(self, workspace_id: int, memory_ids: Sequence[int]) -> dict[int, str]:
        from app.models.memory_review_queue import MemoryReviewQueue

        if not memory_ids:
            return {}
        stmt = select(MemoryReviewQueue.memory_id, MemoryReviewQueue.status).where(
            MemoryReviewQueue.workspace_id == workspace_id,
            MemoryReviewQueue.memory_id.in_(memory_ids),
            MemoryReviewQueue.status == "open",
        )
        result = await self.session.execute(stmt)
        out = {}
        for row in result.all():
            if isinstance(row, (tuple, list)) and len(row) >= 2:
                out[row[0]] = row[1]
        return out

    async def _load_creator_emails(self, workspace_id: int, memory_ids: Sequence[int]) -> dict[uuid.UUID, str]:
        """Return created_by_id -> email for memories in the workspace."""
        if not memory_ids:
            return {}
        stmt = (
            select(Memory.created_by_id, User.email)
            .distinct()
            .join(User, Memory.created_by_id == User.id)
            .where(
                Memory.id.in_(memory_ids),
                Memory.workspace_id == workspace_id,
                Memory.created_by_id.isnot(None),
            )
        )
        result = await self.session.execute(stmt)
        out: dict[uuid.UUID, str] = {}
        for row in result.all():
            if isinstance(row, (tuple, list)) and len(row) >= 2:
                out[row[0]] = row[1]
        return out

    async def _notify_owners(self, workspace_id: int, memory_id: int, flag_reason: str) -> None:
        from app.notifications.service.facade import NotificationService

        stmt = select(Memory.created_by_id).where(
            Memory.id == memory_id,
            Memory.workspace_id == workspace_id,
        )
        result = await self.session.execute(stmt)
        # Find owner/editor members and notify them.
        # Stub: send to memory creator for unit test.
        user_id = result.scalar_one_or_none()
        if user_id:
            await NotificationService.create_notification(
                session=self.session,
                user_id=user_id,
                notification_type="memory_review_flag",
                title="Memory flagged for review",
                message=f"A memory has been flagged for review: {flag_reason[:100]}",
                workspace_id=workspace_id,
                notification_metadata={"memory_id": memory_id, "flag_reason": flag_reason},
            )
