"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Document,
    Memory,
    Run,
    WorkspaceInvite,
    WorkspaceMembership,
)
from app.file_storage.persistence.models import DocumentFile
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)


class WorkspaceCountingMixin:
    # ------------------------------------------------------------------ #
    # Counting
    # ------------------------------------------------------------------ #
    @staticmethod
    async def count_documents(session: AsyncSession, workspace_id: int) -> int:
        result = await session.execute(
            select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id,
                Document.archived_at.is_(None),
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def count_members(session: AsyncSession, workspace_id: int) -> int:
        memberships = await session.execute(
            select(func.count(WorkspaceMembership.id)).where(
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        membership_count = memberships.scalar() or 0

        invites = await session.execute(
            select(func.count(WorkspaceInvite.id)).where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.is_active.is_(True),
                (
                    WorkspaceInvite.expires_at.is_(None)
                    | (WorkspaceInvite.expires_at > datetime.now(UTC))
                ),
                (
                    WorkspaceInvite.max_uses.is_(None)
                    | (WorkspaceInvite.uses_count < WorkspaceInvite.max_uses)
                ),
            )
        )
        invite_count = invites.scalar() or 0

        return membership_count + invite_count

    @staticmethod
    async def count_runs(session: AsyncSession, workspace_id: int, hours: int) -> int:
        # AC-18.8: set the workspace GUC so the RLS-protected run count
        # returns rows for this workspace.
        await set_request_tenant_context(session, workspace_id=workspace_id)
        since = datetime.now(UTC) - timedelta(hours=hours)
        result = await session.execute(
            select(func.count(Run.id)).where(
                Run.workspace_id == workspace_id,
                Run.created_at >= since,
                Run.status.in_(["running", "success", "error"]),
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def sum_storage_bytes(session: AsyncSession, workspace_id: int) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(DocumentFile.size_bytes), 0))
            .select_from(DocumentFile)
            .join(Document, DocumentFile.document_id == Document.id)
            .where(
                Document.workspace_id == workspace_id,
                Document.archived_at.is_(None),
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def reconcile_workspace_storage(
        session: AsyncSession, workspace_id: int, *, purge_orphans: bool = True
    ) -> dict[str, Any]:
        """Reconcile workspace storage: remove orphaned DocumentFiles and compute verified total (Story 30.3)."""
        await set_request_tenant_context(session, workspace_id=workspace_id)
        orphaned_stmt = (
            select(DocumentFile)
            .outerjoin(Document, DocumentFile.document_id == Document.id)
            .where(
                DocumentFile.workspace_id == workspace_id,
                or_(Document.id.is_(None), DocumentFile.size_bytes < 0),
            )
        )
        orphans_res = await session.execute(orphaned_stmt)
        orphans = orphans_res.scalars().all()
        orphaned_found_count = len(orphans)
        cleaned_count = 0

        if purge_orphans and orphans:
            backend = None
            try:
                from app.file_storage.factory import get_storage_backend

                backend = get_storage_backend()
            except Exception as exc:  # storage backend down → skip blob purge, orphans listed for retry
                logger.warning("Storage backend not available for blob purge: %s", exc)

            for orphan in orphans:
                if backend is not None and orphan.storage_key:
                    with contextlib.suppress(Exception):
                        await backend.delete(orphan.storage_key)
                await session.delete(orphan)
            await session.flush()
            cleaned_count = orphaned_found_count

        from app.services.workspace_limits import WorkspaceLimitService

        active_bytes = await WorkspaceLimitService.sum_storage_bytes(
            session, workspace_id
        )
        return {
            "workspace_id": workspace_id,
            "reconciled_storage_bytes": active_bytes,
            "orphaned_files_cleaned": cleaned_count,
        }

    @staticmethod
    async def count_memories(session: AsyncSession, workspace_id: int) -> int:
        await set_request_tenant_context(session, workspace_id=workspace_id)
        result = await session.execute(
            select(func.count(Memory.id)).where(
                Memory.workspace_id == workspace_id,
                Memory.archived_at.is_(None),
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def estimate_memory_storage_bytes(
        session: AsyncSession, workspace_id: int
    ) -> int:
        """Estimate memory storage in bytes (best-effort soft metric)."""
        await set_request_tenant_context(session, workspace_id=workspace_id)
        dim = getattr(config.embedding_model_instance, "dimension", 384)
        result = await session.execute(
            select(
                func.coalesce(
                    func.sum(func.length(Memory.content) + (dim * 4) + 128),
                    0,
                )
            ).where(
                Memory.workspace_id == workspace_id,
                Memory.archived_at.is_(None),
            )
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def count_sources(session: AsyncSession, workspace_id: int) -> int:
        from app.models.connectors import SearchSourceConnector

        result = await session.execute(
            select(func.count(SearchSourceConnector.id)).where(
                SearchSourceConnector.workspace_id == workspace_id
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------ #
    # Usage snapshot
    # ------------------------------------------------------------------ #
