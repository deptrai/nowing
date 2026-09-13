"""Memory browser service: list, filter, detail, review flag (Story 29.5 / FR-104)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.db import (
    Memory,
    MemoryRelation,
    MemoryRelationType,
    MemoryVersion,
    Permission,
    ResearchThread,
    User,
    WorkspaceMembership,
    WorkspaceRole,
)
from app.schemas.memory_browser import (
    MemoryBrowserCreator,
    MemoryBrowserCreatorListResponse,
    MemoryBrowserDetailCitations,
    MemoryBrowserDetailResponse,
    MemoryBrowserListItem,
    MemoryBrowserListResponse,
    MemoryBrowserTimelineResponse,
    MemoryBrowserTimelineThread,
    MemoryRelationListResponse,
    MemoryRelationRead,
    MemoryReviewQueueRead,
    MemoryVersionListResponse,
    MemoryVersionRead,
    ResearchThreadSummary,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
SNIPPET_LENGTH = 120
# Upper bound on the timeline payload — a research thread can accumulate
# thousands of memories; the UI paginates by thread so a generous cap is
# sufficient.
TIMELINE_LIMIT = 500

# Spec AC-2.1 lists connector ``DocumentType`` values as valid ``source_types``
# filters, but ``Memory.source_type`` only stores ``MemorySourceType`` values —
# connector-ingested content lands in memories as ``document``. Mapping them
# keeps the filter composable instead of 422-ing on spec-listed values.
CONNECTOR_SOURCE_TYPE_ALIASES: dict[str, str] = {
    "luma_connector": "document",
    "elasticsearch_connector": "document",
    "webcrawler_connector": "document",
    "bookstack_connector": "document",
    "circleback_connector": "document",
    "obsidian_connector": "document",
    "mcp_connector": "document",
    "exa_mcp_connector": "document",
    "dropbox_connector": "document",
    "composio_google_drive_connector": "document",
    "composio_gmail_connector": "document",
    "composio_google_calendar_connector": "document",
    "rss_feed": "document",
}

# Canonical entity routes for ``source_uuid`` + ``source_entity_type``
# provenance (AC-3.2). Anything unmapped falls back to the type badge.
_ENTITY_ROUTE_MAP: dict[str, str] = {
    "lead": "leads",
    "document": "documents",
    "run": "runs",
    "chat": "chats",
    "chat_message": "chats",
    "signal": "signals",
    "sequence": "sequences",
    "campaign": "campaigns",
}

# AC-4.3: relations that act as branch/merge markers on the timeline.
_BRANCH_RELATION_TYPES = {
    MemoryRelationType.DERIVED_FROM.value,
    MemoryRelationType.CORRECTS.value,
}


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
            mapped = {
                CONNECTOR_SOURCE_TYPE_ALIASES.get(st.lower(), st.lower())
                for st in source_types
            }
            conditions.append(Memory.source_type.in_(sorted(mapped)))

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
            conditions.append(self._keyword_condition(keyword.strip()))

        order_by = self._order_by_clause(sort, sort_dir)

        stmt = (
            select(Memory)
            .options(defer(Memory.embedding))
            .where(*conditions)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            self._decrypt_memory(row)

        total = await self._count_total(conditions)

        memory_ids = [r.id for r in rows]
        flag_status_map = await self._load_review_status(workspace_id, memory_ids)
        version_count_map = await self._load_version_counts(workspace_id, memory_ids)
        creator_map = await self._load_creator_emails(workspace_id, memory_ids)
        marker_map = await self._load_relation_markers(workspace_id, memory_ids)

        items = [
            self._to_list_item(row, workspace_id, creator_map, version_count_map, flag_status_map, marker_map)
            for row in rows
        ]

        return MemoryBrowserListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_creators(
        self,
        workspace_id: int,
        client_id: str | None = None,
    ) -> MemoryBrowserCreatorListResponse:
        """AC-2.4: dropdown of distinct memory creators in this workspace,
        scoped to the same client partition as the list endpoint."""
        conditions = [
            Memory.workspace_id == workspace_id,
            Memory.created_by_id.isnot(None),
        ]
        if client_id is not None:
            conditions.append(Memory.client_id == client_id)
        else:
            conditions.append(Memory.client_id.is_(None))
        stmt = (
            select(User.id, User.email)
            .join(Memory, Memory.created_by_id == User.id)
            .where(*conditions)
            .distinct()
            .order_by(User.email)
        )
        result = await self.session.execute(stmt)
        items = [
            MemoryBrowserCreator(id=str(row[0]), email=row[1])
            for row in result.all()
        ]
        return MemoryBrowserCreatorListResponse(items=items)

    async def get_timeline(
        self,
        workspace_id: int,
        client_id: str | None = None,
    ) -> MemoryBrowserTimelineResponse:
        """AC-4: group memories by research thread, chronological per thread."""
        conditions = self._base_conditions(workspace_id, client_id)
        stmt = (
            select(Memory)
            .options(defer(Memory.embedding))
            .where(*conditions)
            .order_by(Memory.research_thread_id.asc().nulls_last(), Memory.created_at.asc(), Memory.id.asc())
            .limit(TIMELINE_LIMIT)
        )
        result = await self.session.execute(stmt)
        memories = list(result.scalars().all())
        for m in memories:
            self._decrypt_memory(m)

        memory_ids = [m.id for m in memories]
        flag_status_map = await self._load_review_status(workspace_id, memory_ids)
        version_count_map = await self._load_version_counts(workspace_id, memory_ids)
        creator_map = await self._load_creator_emails(workspace_id, memory_ids)
        marker_map = await self._load_relation_markers(workspace_id, memory_ids)

        thread_ids = {m.research_thread_id for m in memories if m.research_thread_id is not None}
        thread_titles = await self._load_thread_titles(workspace_id, thread_ids)

        grouped: dict[int, list[MemoryBrowserListItem]] = {}
        unthreaded: list[MemoryBrowserListItem] = []
        for m in memories:
            item = self._to_list_item(m, workspace_id, creator_map, version_count_map, flag_status_map, marker_map)
            if m.research_thread_id is None:
                unthreaded.append(item)
            else:
                grouped.setdefault(m.research_thread_id, []).append(item)

        threads = [
            MemoryBrowserTimelineThread(
                id=thread_id,
                title=thread_titles.get(thread_id) or f"Untitled thread #{thread_id}",
                memories=items,
            )
            for thread_id, items in sorted(grouped.items())
        ]
        return MemoryBrowserTimelineResponse(threads=threads, unthreaded=unthreaded)

    def _to_list_item(
        self,
        row: Any,
        workspace_id: int,
        creator_map: dict[uuid.UUID, str],
        version_count_map: dict[int, int],
        flag_status_map: dict[int, str],
        marker_map: dict[int, str],
    ) -> MemoryBrowserListItem:
        return MemoryBrowserListItem(
            id=row.id,
            content_snippet=self._snippet(row.content or "", SNIPPET_LENGTH),
            source_type=row.source_type.value if hasattr(row.source_type, "value") else str(row.source_type),
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
            research_thread_id=row.research_thread_id,
            relation_marker=marker_map.get(row.id),
        )

    def _keyword_condition(self, keyword: str) -> Any:
        """AC-2.5: full-text search over the GIN-indexed tsvector; ILIKE
        fallback only covers encrypted rows lacking ``content_search``."""
        from app.services.memory.encryption import MemoryEncryptionService

        tsquery = func.plainto_tsquery("english", keyword)
        if MemoryEncryptionService.from_env().is_enabled():
            tsvector = func.to_tsvector("english", Memory.content_search)
            fts = tsvector.op("@@")(tsquery)
            # Rows encrypted before content_search existed have no token
            # stream — ILIKE over ciphertext never matches, so these are
            # effectively unsearchable; keep the fallback for plaintext rows.
            ilike = Memory.content.ilike(f"%{keyword}%")
            return or_(fts, ilike)
        return func.to_tsvector("english", Memory.content).op("@@")(tsquery)

    async def _count_total(self, conditions: list[Any]) -> int:
        stmt = select(func.count(Memory.id)).where(*conditions)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_memory_detail(
        self,
        workspace_id: int,
        memory_id: int,
        client_id: str | None = None,
    ) -> MemoryBrowserDetailResponse:
        memory = await self._get_scoped_memory(workspace_id, memory_id, client_id)

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
            research_thread=await self._build_thread(workspace_id, memory.research_thread_id, client_id),
            relations=(await self._build_relations(workspace_id, memory, client_id)).items,
        )

    async def get_memory_versions(
        self,
        workspace_id: int,
        memory_id: int,
        client_id: str | None = None,
    ) -> MemoryVersionListResponse:
        memory = await self._get_scoped_memory(workspace_id, memory_id, client_id)
        return MemoryVersionListResponse(items=await self._build_versions(memory))

    async def get_memory_relations(
        self,
        workspace_id: int,
        memory_id: int,
        client_id: str | None = None,
    ) -> MemoryRelationListResponse:
        memory = await self._get_scoped_memory(workspace_id, memory_id, client_id)
        return await self._build_relations(workspace_id, memory, client_id)

    async def _get_scoped_memory(
        self,
        workspace_id: int,
        memory_id: int,
        client_id: str | None,
    ) -> Any:
        """Fail-closed tenant lookup: PAT-scoped requests only see memories in
        their ``client_id`` partition; session requests see the unscoped
        partition (mirrors ``_require_memory_tenant_match``)."""
        conditions = [
            Memory.id == memory_id,
            Memory.workspace_id == workspace_id,
            Memory.archived_at.is_(None),
        ]
        if client_id is not None:
            conditions.append(Memory.client_id == client_id)
        else:
            conditions.append(Memory.client_id.is_(None))
        stmt = select(Memory).where(*conditions)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory is None:
            raise ValueError(f"Memory {memory_id} not found")
        return memory

    # ------------------------------------------------------------------
    # Review flag
    # ------------------------------------------------------------------

    async def flag_for_review(
        self,
        workspace_id: int,
        memory_id: int,
        flag_reason: str,
        flagged_by: uuid.UUID,
        client_id: str | None = None,
    ) -> MemoryReviewQueueRead:
        if not flag_reason or not flag_reason.strip():
            raise ValueError("flag_reason cannot be empty")

        memory = await self._get_scoped_memory(workspace_id, memory_id, client_id)

        from app.models.billing import AuditEvent
        from app.models.memory_review_queue import MemoryReviewQueue
        from app.notifications.persistence import Notification

        reason = flag_reason.strip()

        # Idempotency: an already-open flag on the same memory is returned
        # as-is without stacking rows or emitting duplicate notifications.
        existing_stmt = select(MemoryReviewQueue).where(
            MemoryReviewQueue.memory_id == memory.id,
            MemoryReviewQueue.workspace_id == workspace_id,
            MemoryReviewQueue.status == "open",
        )
        existing = (await self.session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return MemoryReviewQueueRead(
                id=existing.id,
                memory_id=existing.memory_id,
                workspace_id=existing.workspace_id,
                flag_reason=existing.flag_reason,
                flagged_by=str(existing.flagged_by) if existing.flagged_by else None,
                status=existing.status,
                created_at=existing.created_at,
                resolved_at=existing.resolved_at,
                resolved_by=str(existing.resolved_by) if existing.resolved_by else None,
            )

        queue = MemoryReviewQueue(
            memory_id=memory.id,
            workspace_id=workspace_id,
            flag_reason=reason,
            flagged_by=flagged_by,
            status="open",
        )
        self.session.add(queue)
        await self.session.flush()

        # AC-5.2: immutable audit entry in the same transaction.
        audit = AuditEvent(
            action="memory_review_flag",
            actor_id=flagged_by,
            diff_payload={
                "memory_id": memory.id,
                "workspace_id": workspace_id,
                "flag_reason": reason,
                "review_queue_id": queue.id,
            },
        )
        self.session.add(audit)

        # AC-5.2: notify workspace owners/editors in the SAME transaction —
        # ``NotificationService.create_notification`` commits internally and
        # would break the flag+notify atomicity required by spec Q4, so the
        # rows are staged here and committed together below.
        recipients = await self._load_review_recipients(workspace_id)
        for user_id in recipients:
            self.session.add(
                Notification(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type="memory_review_flag",
                    title="Memory flagged for review",
                    message=f"A memory has been flagged for review: {reason[:100]}",
                    notification_metadata={
                        "memory_id": memory.id,
                        "review_queue_id": queue.id,
                        "flag_reason": reason,
                    },
                )
            )

        await self.session.commit()
        await self.session.refresh(queue)

        return MemoryReviewQueueRead(
            id=queue.id,
            memory_id=queue.memory_id,
            workspace_id=queue.workspace_id,
            flag_reason=queue.flag_reason,
            flagged_by=str(queue.flagged_by) if queue.flagged_by else None,
            status=queue.status,
            created_at=queue.created_at,
            resolved_at=queue.resolved_at,
            resolved_by=str(queue.resolved_by) if queue.resolved_by else None,
        )

    async def _load_review_recipients(self, workspace_id: int) -> list[uuid.UUID]:
        """Owners plus members whose role grants ``memory:update`` (AC-5.2)."""
        stmt = (
            select(WorkspaceMembership.user_id)
            .outerjoin(WorkspaceRole, WorkspaceMembership.role_id == WorkspaceRole.id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                or_(
                    WorkspaceMembership.is_owner.is_(True),
                    WorkspaceRole.permissions.any(Permission.MEMORY_UPDATE.value),
                    WorkspaceRole.permissions.any(Permission.FULL_ACCESS.value),
                ),
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all() if row[0] is not None]

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

    def _order_by_clause(self, sort: str, sort_dir: str) -> list[Any]:
        mapping = {
            "created_at": Memory.created_at,
            "updated_at": Memory.updated_at,
            "confidence": Memory.confidence,
        }
        col = mapping.get(sort, Memory.created_at)
        # ``id`` tie-break keeps pagination stable when rows share a timestamp.
        if sort_dir == "desc":
            return [col.desc(), Memory.id.desc()]
        return [col.asc(), Memory.id.asc()]

    def _derive_source_url(self, workspace_id: int, memory: Any) -> str | None:
        """AC-3.2: canonical entity routes; unmapped types fall back to the
        ``source_type`` badge on the frontend (``source_url = None``)."""
        if memory.source_run_id:
            return f"/dashboard/{workspace_id}/runs/{memory.source_run_id}"
        if memory.source_uuid and memory.source_entity_type:
            route = _ENTITY_ROUTE_MAP.get(str(memory.source_entity_type).lower())
            if route:
                return f"/dashboard/{workspace_id}/{route}/{memory.source_uuid}"
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

    async def _build_thread(
        self,
        workspace_id: int,
        research_thread_id: int | None,
        client_id: str | None = None,
    ) -> ResearchThreadSummary | None:
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

        memory_conditions = [
            Memory.research_thread_id == thread.id,
            Memory.workspace_id == workspace_id,
            Memory.archived_at.is_(None),
        ]
        if client_id is not None:
            memory_conditions.append(Memory.client_id == client_id)
        else:
            memory_conditions.append(Memory.client_id.is_(None))
        memories_stmt = (
            select(Memory)
            .options(defer(Memory.embedding))
            .where(*memory_conditions)
            .order_by(Memory.created_at.asc(), Memory.id.asc())
        )
        res = await self.session.execute(memories_stmt)
        memories = list(res.scalars().all())
        for m in memories:
            self._decrypt_memory(m)

        memory_ids = [m.id for m in memories]
        version_count_map = await self._load_version_counts(workspace_id, memory_ids)
        flag_status_map = await self._load_review_status(workspace_id, memory_ids)
        creator_map = await self._load_creator_emails(workspace_id, memory_ids)
        marker_map = await self._load_relation_markers(workspace_id, memory_ids)

        title = thread.title or f"Untitled thread #{thread.id}"
        return ResearchThreadSummary(
            id=thread.id,
            title=title,
            memories=[
                self._to_list_item(m, workspace_id, creator_map, version_count_map, flag_status_map, marker_map)
                for m in memories
            ],
        )

    async def _build_relations(
        self,
        workspace_id: int,
        memory: Any,
        client_id: str | None = None,
    ) -> MemoryRelationListResponse:
        """AC-3.5: show both incoming and outgoing relations for the memory,
        scoped to the workspace and client partition to satisfy hard tenant
        boundaries."""
        conditions = [
            MemoryRelation.workspace_id == workspace_id,
            or_(
                MemoryRelation.from_memory_id == memory.id,
                MemoryRelation.to_memory_id == memory.id,
            ),
        ]
        if client_id is not None:
            conditions.append(MemoryRelation.client_id == client_id)
        else:
            conditions.append(MemoryRelation.client_id.is_(None))
        stmt = select(MemoryRelation).where(*conditions).order_by(
            MemoryRelation.created_at.asc()
        )
        result = await self.session.execute(stmt)
        relations = list(result.scalars().all())
        out = []
        for r in relations:
            relation_type = r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type)
            if r.from_memory_id == memory.id:
                to_memory_id = r.to_memory_id
            else:
                to_memory_id = r.from_memory_id
                # Flip the type for incoming relations so the UI reads naturally.
                if relation_type == "derived_from":
                    relation_type = "derived_by"
                elif relation_type == "corrects":
                    relation_type = "corrected_by"
            out.append(
                MemoryRelationRead(
                    relation_type=relation_type,
                    to_memory_id=to_memory_id,
                    weight=r.weight,
                )
            )
        return MemoryRelationListResponse(items=out)

    async def _load_thread_titles(self, workspace_id: int, thread_ids: set[int]) -> dict[int, str]:
        if not thread_ids:
            return {}
        stmt = (
            select(ResearchThread.id, ResearchThread.title)
            .where(
                ResearchThread.id.in_(sorted(thread_ids)),
                ResearchThread.workspace_id == workspace_id,
            )
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all() if row is not None}

    async def _load_relation_markers(self, workspace_id: int, memory_ids: Sequence[int]) -> dict[int, str]:
        """AC-4.3: thread markers for memories that branch from or correct
        another memory in the same workspace."""
        if not memory_ids:
            return {}
        stmt = (
            select(MemoryRelation.from_memory_id, MemoryRelation.relation_type)
            .where(
                MemoryRelation.workspace_id == workspace_id,
                MemoryRelation.from_memory_id.in_(memory_ids),
                MemoryRelation.relation_type.in_(_BRANCH_RELATION_TYPES),
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        out: dict[int, str] = {}
        for row in result.all():
            if isinstance(row, (tuple, list)) and len(row) >= 2 and row[0] not in out:
                out[row[0]] = row[1].value if hasattr(row[1], "value") else str(row[1])
        return out

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
