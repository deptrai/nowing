"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


def _limit_error(limit_type: str, used: int, limit: int | None) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "error_code": "limit_exceeded",
            "limit_type": limit_type,
            "used": used,
            "limit": limit,
        },
    )


class WorkspaceChecksMixin:
    async def get_usage_snapshot(
        self, session: AsyncSession, workspace_id: int
    ) -> dict[str, Any]:
        limits = await self.get_effective_limits(session, workspace_id)
        return {
            "documents": await self.count_documents(session, workspace_id),
            "members": await self.count_members(session, workspace_id),
            "runs": await self.count_runs(
                session, workspace_id, limits.run_period_hours
            ),
            "storage_bytes": await self.sum_storage_bytes(session, workspace_id),
            "memory_count": await self.count_memories(session, workspace_id),
            "memory_bytes": await self.estimate_memory_storage_bytes(
                session, workspace_id
            ),
            "sources": await self.count_sources(session, workspace_id),
        }

    # ------------------------------------------------------------------ #
    # Gating
    # ------------------------------------------------------------------ #
    async def check_memory_limit(
        self,
        session: AsyncSession,
        workspace_id: int,
        additional: int = 1,
    ) -> None:
        await self._advisory_lock(session, workspace_id)
        limits = await self.get_effective_limits(session, workspace_id)
        if limits.max_memory_count is None:
            return
        used = await self.count_memories(session, workspace_id)
        if used + additional > limits.max_memory_count:
            raise _limit_error("memory", used, limits.max_memory_count)

    @classmethod
    async def assert_can_create_memory(
        cls,
        session: AsyncSession,
        workspace_id: int | None,
        additional: int = 1,
    ) -> None:
        if workspace_id is None:
            return
        from app.services.workspace_limits import workspace_limit_service

        await workspace_limit_service.check_memory_limit(
            session, workspace_id, additional=additional
        )

    async def check_document_limit(
        self,
        session: AsyncSession,
        workspace_id: int,
        additional: int = 0,
    ) -> None:
        await self._advisory_lock(session, workspace_id)
        limits = await self.get_effective_limits(session, workspace_id)
        if limits.max_documents is None:
            return
        used = await self.count_documents(session, workspace_id)
        if used + additional > limits.max_documents:
            raise _limit_error("documents", used, limits.max_documents)

    async def check_member_limit(
        self,
        session: AsyncSession,
        workspace_id: int,
        additional: int = 0,
    ) -> None:
        await self._advisory_lock(session, workspace_id)
        limits = await self.get_effective_limits(session, workspace_id)
        if limits.max_members is None:
            return
        used = await self.count_members(session, workspace_id)
        if used + additional > limits.max_members:
            raise _limit_error("members", used, limits.max_members)

    async def check_run_limit(
        self,
        session: AsyncSession,
        workspace_id: int,
    ) -> None:
        await self._advisory_lock(session, workspace_id)
        limits = await self.get_effective_limits(session, workspace_id)
        if limits.max_runs is None:
            return
        used = await self.count_runs(session, workspace_id, limits.run_period_hours)
        if used >= limits.max_runs:
            raise _limit_error("runs", used, limits.max_runs)
