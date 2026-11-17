"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Document,
    Memory,
    Run,
    Workspace,
    WorkspaceInvite,
    WorkspaceLimit,
    WorkspaceMembership,
)
from app.file_storage.persistence.models import DocumentFile
from app.tenant_context import set_request_tenant_context


@dataclass
class ResolvedWorkspaceLimits:
    """Effective limits for a workspace, after override/plan resolution."""

    plan_tier: str | None
    max_documents: int | None
    max_members: int | None
    max_runs: int | None
    max_storage_bytes: int | None
    run_period_hours: int = 720
    # Story 8.14: auto-extract budget caps.
    auto_extract_item_cap: int | None = None
    auto_extract_spend_cap_micros: int | None = None
    auto_extract_wallet_pre_check: bool | None = None
    # Story 14.2a: news entity extraction caps.
    news_entity_extraction_item_cap: int | None = None
    news_entity_extraction_spend_cap_micros: int | None = None
    news_entity_extraction_wallet_pre_check: bool | None = None
    # Story 28.5: workspace memory storage cap and retention.
    max_memory_count: int | None = None
    max_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        """Enforce invariants on resolved limit values."""
        for field in (
            "max_documents",
            "max_members",
            "max_runs",
            "max_storage_bytes",
            "auto_extract_item_cap",
            "auto_extract_spend_cap_micros",
            "news_entity_extraction_item_cap",
            "news_entity_extraction_spend_cap_micros",
            "max_memory_count",
            "max_memory_bytes",
        ):
            value = getattr(self, field)
            if value is None:
                continue
            if not isinstance(value, int):
                raise TypeError(
                    f"{field} must be int or None, got {type(value).__name__}"
                )
            if value < 0:
                raise ValueError(f"{field} must be >= 0, got {value}")

        if (
            self.run_period_hours is None
            or not isinstance(self.run_period_hours, int)
            or self.run_period_hours < 1
        ):
            object.__setattr__(self, "run_period_hours", 720)


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


class WorkspaceLimitService:
    """Resolve and enforce workspace plan limits."""

    # ------------------------------------------------------------------ #
    # Locking
    # ------------------------------------------------------------------ #
    @staticmethod
    async def _advisory_lock(session: AsyncSession, workspace_id: int) -> None:
        """Acquire a transaction-scoped advisory lock keyed by workspace.

        Uses the two-argument lock form with a fixed namespace hash and the
        workspace id as the second key. This avoids cross-workspace hash
        collisions while keeping the lock scoped per workspace.
        """
        await session.execute(
            text(
                "SELECT pg_advisory_xact_lock(hashtext('workspace_limits'), :wid)"
            ).bindparams(wid=workspace_id)
        )

    # ------------------------------------------------------------------ #
    # Resolution
    # ------------------------------------------------------------------ #
    @staticmethod
    async def get_effective_limits(
        session: AsyncSession, workspace_id: int
    ) -> ResolvedWorkspaceLimits:
        """Return the effective limits for a workspace.

        Resolution order:
        1. Self-hosted: all limits are None (unlimited).
        2. Per-workspace override row.
        3. Plan default row for workspace.plan_tier.
        4. Optional WORKSPACE_PLAN_LIMITS env override.
        5. Fallback to the `free` plan default if the workspace plan is unknown.
        """
        if not hasattr(session, "get") or not callable(getattr(session, "get", None)):
            return ResolvedWorkspaceLimits(
                plan_tier=None,
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                max_memory_count=None,
                max_memory_bytes=None,
                run_period_hours=720,
            )

        if config.is_self_hosted():
            workspace = await session.get(Workspace, workspace_id)
            override = await session.execute(
                select(WorkspaceLimit).where(
                    WorkspaceLimit.workspace_id == workspace_id,
                    WorkspaceLimit.plan_tier.is_(None),
                )
            )
            override_row = override.scalars().first()
            return ResolvedWorkspaceLimits(
                plan_tier=workspace.plan_tier if workspace else None,
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                run_period_hours=720,
                auto_extract_item_cap=getattr(
                    override_row, "auto_extract_item_cap", None
                )
                if override_row
                else None,
                auto_extract_spend_cap_micros=getattr(
                    override_row, "auto_extract_spend_cap_micros", None
                )
                if override_row
                else None,
                auto_extract_wallet_pre_check=getattr(
                    override_row, "auto_extract_wallet_pre_check", None
                )
                if override_row
                else None,
                news_entity_extraction_item_cap=getattr(
                    override_row, "news_entity_extraction_item_cap", None
                )
                if override_row
                else None,
                news_entity_extraction_spend_cap_micros=getattr(
                    override_row, "news_entity_extraction_spend_cap_micros", None
                )
                if override_row
                else None,
                news_entity_extraction_wallet_pre_check=getattr(
                    override_row, "news_entity_extraction_wallet_pre_check", None
                )
                if override_row
                else None,
                max_memory_count=getattr(override_row, "max_memory_count", None)
                if override_row
                else None,
                max_memory_bytes=getattr(override_row, "max_memory_bytes", None)
                if override_row
                else None,
            )

        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            return ResolvedWorkspaceLimits(
                plan_tier=None,
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                run_period_hours=720,
            )

        # Normalize plan tier for lookup and fall back to `free` if it is unknown.
        plan_tier = (workspace.plan_tier or "free").lower()

        # 1. Try workspace-specific override.
        override = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.workspace_id == workspace_id,
                WorkspaceLimit.plan_tier.is_(None),
            )
        )
        override_row = override.scalars().first()

        # 2. Fall back to plan default.
        plan_row = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.plan_tier == plan_tier,
                WorkspaceLimit.workspace_id.is_(None),
            )
        )
        plan_row = plan_row.scalars().first()

        # 3. Apply optional env override on top of plan defaults.
        # Defensive: WORKSPACE_PLAN_LIMITS may be misconfigured to a non-dict.
        env_overrides = config.WORKSPACE_PLAN_LIMITS
        if not isinstance(env_overrides, Mapping):
            env_overrides = {}

        def _plan_env(tier: str) -> dict[str, Any]:
            raw = env_overrides.get(tier, {})
            if not isinstance(raw, Mapping):
                return {}
            return dict(raw)

        plan_env = _plan_env(plan_tier)

        # 4. If the workspace's tier is unknown and has no env override, fall
        # back to the `free` plan default so cloud workspaces cannot silently
        # become unlimited.
        free_row: WorkspaceLimit | None = None
        if plan_row is None and not plan_env and plan_tier != "free":
            free_result = await session.execute(
                select(WorkspaceLimit).where(
                    WorkspaceLimit.plan_tier == "free",
                    WorkspaceLimit.workspace_id.is_(None),
                )
            )
            free_row = free_result.scalars().first()
            plan_env = _plan_env("free")

        effective_plan_row = free_row if free_row is not None else plan_row

        def _resolve(field: str) -> Any:
            if override_row is not None and getattr(override_row, field) is not None:
                return getattr(override_row, field)
            if field in plan_env:
                return plan_env[field]
            if effective_plan_row is not None:
                return getattr(effective_plan_row, field)
            return None

        return ResolvedWorkspaceLimits(
            plan_tier=plan_tier,
            max_documents=_resolve("max_documents"),
            max_members=_resolve("max_members"),
            max_runs=_resolve("max_runs"),
            max_storage_bytes=_resolve("max_storage_bytes"),
            run_period_hours=_resolve("run_period_hours") or 720,
            auto_extract_item_cap=_resolve("auto_extract_item_cap"),
            auto_extract_spend_cap_micros=_resolve("auto_extract_spend_cap_micros"),
            auto_extract_wallet_pre_check=_resolve("auto_extract_wallet_pre_check"),
            news_entity_extraction_item_cap=_resolve("news_entity_extraction_item_cap"),
            news_entity_extraction_spend_cap_micros=_resolve(
                "news_entity_extraction_spend_cap_micros"
            ),
            news_entity_extraction_wallet_pre_check=_resolve(
                "news_entity_extraction_wallet_pre_check"
            ),
            max_memory_count=_resolve("max_memory_count"),
            max_memory_bytes=_resolve("max_memory_bytes"),
        )

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

    # ------------------------------------------------------------------ #
    # Usage snapshot
    # ------------------------------------------------------------------ #
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


workspace_limit_service = WorkspaceLimitService()

# Re-export WorkspaceCreditService and errors for unified limits & credit access (Story 24.3)
from app.services.workspace_credit_service import (  # noqa: E402
    CreditDeductionResult,
    InsufficientCreditsError,
    MemberSpendStatus,
    SpendCapExceededError,
    WorkspaceCreditService,
    workspace_credit_service,
)

__all__ = [
    "CreditDeductionResult",
    "InsufficientCreditsError",
    "MemberSpendStatus",
    "ResolvedWorkspaceLimits",
    "SpendCapExceededError",
    "WorkspaceCreditService",
    "WorkspaceLimitService",
    "workspace_credit_service",
    "workspace_limit_service",
]
