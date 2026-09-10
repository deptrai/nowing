"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Document,
    Memory,
    Run,
    SubscriptionChange,
    Workspace,
    WorkspaceInvite,
    WorkspaceLimit,
    WorkspaceMembership,
)
from app.file_storage.persistence.models import DocumentFile
from app.schemas.workspace import PlanDefinitionCreate, PlanDefinitionUpdate
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
    # Story 29.3: plan catalog & tenant quota expansion (AD-8, AD-51, PM-1)
    max_monthly_credits: int | None = None
    max_sources: int | None = None
    support_level: str | None = None
    price_micros: int | None = None
    currency: str = "USD"

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
            "max_monthly_credits",
            "max_sources",
            "price_micros",
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
                max_monthly_credits=None,
                max_sources=None,
                support_level=None,
                price_micros=None,
                currency="USD",
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
            max_monthly_credits=_resolve("max_monthly_credits"),
            max_sources=_resolve("max_sources"),
            support_level=_resolve("support_level") or "community",
            price_micros=_resolve("price_micros") or 0,
            currency=_resolve("currency") or "USD",
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
    async def reconcile_workspace_storage(
        session: AsyncSession, workspace_id: int, *, purge_orphans: bool = True
    ) -> dict[str, Any]:
        """Reconcile workspace storage: remove orphaned DocumentFiles and compute verified total (Story 30.3)."""
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
        cleaned_count = len(orphans)

        if purge_orphans and orphans:
            for orphan in orphans:
                await session.delete(orphan)
            await session.flush()

        active_bytes = await WorkspaceLimitService.sum_storage_bytes(session, workspace_id)
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

    # ------------------------------------------------------------------ #
    # Story 29.3: Plan catalog & Subscription changes (FR-102, PM-1..PM-6)
    # ------------------------------------------------------------------ #
    async def check_plan_change_conflicts(
        self, session: AsyncSession, workspace_id: int, target_plan: str
    ) -> dict[str, dict[str, int]]:
        """Compare current workspace resource usage against target plan limits.

        Returns dict of conflicting metrics:
        {"metric": {"current": used, "limit": limit}}
        """
        target_plan = target_plan.lower().strip()
        res = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.plan_tier == target_plan,
                WorkspaceLimit.workspace_id.is_(None),
            )
        )
        plan_def = res.scalars().first()
        if plan_def is None:
            raise HTTPException(
                status_code=404,
                detail=f"Plan tier '{target_plan}' not found in catalog",
            )

        usage = await self.get_usage_snapshot(session, workspace_id)
        conflicts: dict[str, dict[str, int]] = {}

        metrics = [
            ("documents", plan_def.max_documents),
            ("members", plan_def.max_members),
            ("runs", plan_def.max_runs),
            ("storage_bytes", plan_def.max_storage_bytes),
            ("memory_count", plan_def.max_memory_count),
            ("memory_bytes", plan_def.max_memory_bytes),
            ("sources", plan_def.max_sources),
        ]

        for metric_name, max_val in metrics:
            if max_val is not None:
                current_val = usage.get(metric_name, 0)
                if current_val > max_val:
                    conflicts[metric_name] = {
                        "current": current_val,
                        "limit": max_val,
                    }

        return conflicts

    async def create_subscription_change(
        self,
        session: AsyncSession,
        workspace_id: int,
        to_plan: str,
        immediate: bool = False,
        user_id: uuid.UUID | None = None,
        payment_method_id: str | None = None,
    ) -> SubscriptionChange:
        await self._advisory_lock(session, workspace_id)
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        to_plan = to_plan.lower().strip()
        current_plan = (workspace.plan_tier or "free").lower()

        res = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.plan_tier == to_plan,
                WorkspaceLimit.workspace_id.is_(None),
            )
        )
        target_plan_def = res.scalars().first()
        if target_plan_def is None:
            raise HTTPException(
                status_code=422,
                detail=f"Plan tier '{to_plan}' does not exist",
            )

        conflicts = await self.check_plan_change_conflicts(
            session, workspace_id, to_plan
        )
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "quota_conflict",
                    "message": "Cannot change plan: current usage exceeds new plan limits",
                    "conflicts": conflicts,
                },
            )

        # Cancel any active pending changes
        pending_res = await session.execute(
            select(SubscriptionChange).where(
                SubscriptionChange.workspace_id == workspace_id,
                SubscriptionChange.status == "pending",
            )
        )
        for p in pending_res.scalars().all():
            p.status = "cancelled"

        now = datetime.now(UTC)
        if immediate:
            effective_at = now
            reversible_until = now + timedelta(days=7)
            status = "active"
            workspace.plan_tier = to_plan
            await session.execute(
                sa_delete(WorkspaceLimit).where(
                    WorkspaceLimit.workspace_id == workspace_id,
                    WorkspaceLimit.plan_tier.is_(None),
                )
            )
        else:
            effective_at = now + timedelta(days=7)
            reversible_until = effective_at
            status = "pending"

        diff_payload = {
            "from_plan": current_plan,
            "to_plan": to_plan,
            "immediate": immediate,
            "effective_at": effective_at.isoformat(),
            "reversible_until": (
                reversible_until.isoformat() if reversible_until else None
            ),
        }

        change = SubscriptionChange(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            from_plan=current_plan,
            to_plan=to_plan,
            effective_at=effective_at,
            reversible_until=reversible_until,
            status=status,
            initiated_by=user_id,
            payment_method_id=payment_method_id,
            immediate=immediate,
            diff_payload=diff_payload,
        )
        session.add(change)

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action=(
                    "subscription.change_requested"
                    if not immediate
                    else "subscription.upgraded_immediate"
                ),
                actor_id=user_id,
                diff_payload=diff_payload,
            )
        )
        await session.flush()
        return change

    async def revert_subscription_change(
        self,
        session: AsyncSession,
        workspace_id: int,
        change_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> SubscriptionChange:
        await self._advisory_lock(session, workspace_id)
        change = await session.get(SubscriptionChange, change_id)
        if change is None or change.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Subscription change not found")

        if change.status not in ("active", "pending"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot revert change with status '{change.status}'",
            )

        now = datetime.now(UTC)
        if change.reversible_until is None or now > change.reversible_until:
            raise HTTPException(
                status_code=409,
                detail="Reversal window has expired (reversible period is 7 days)",
            )

        conflicts = await self.check_plan_change_conflicts(
            session, workspace_id, change.from_plan
        )
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "quota_conflict",
                    "message": f"Cannot revert: current usage exceeds {change.from_plan} plan limits",
                    "conflicts": conflicts,
                },
            )

        workspace = await session.get(Workspace, workspace_id)
        if workspace and change.status == "active":
            workspace.plan_tier = change.from_plan
            await session.execute(
                sa_delete(WorkspaceLimit).where(
                    WorkspaceLimit.workspace_id == workspace_id,
                    WorkspaceLimit.plan_tier.is_(None),
                )
            )

        change.status = "reverted"

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action="subscription.reverted",
                actor_id=user_id,
                diff_payload={
                    "change_id": str(change.id),
                    "reverted_to": change.from_plan,
                    "original_to_plan": change.to_plan,
                },
            )
        )
        await session.flush()
        return change

    async def cancel_subscription_change(
        self,
        session: AsyncSession,
        workspace_id: int,
        change_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> SubscriptionChange:
        await self._advisory_lock(session, workspace_id)
        change = await session.get(SubscriptionChange, change_id)
        if change is None or change.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Subscription change not found")

        if change.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Only pending changes can be cancelled, current status is '{change.status}'",
            )

        change.status = "cancelled"

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action="subscription.cancelled",
                actor_id=user_id,
                diff_payload={
                    "change_id": str(change.id),
                    "cancelled_plan": change.to_plan,
                },
            )
        )
        await session.flush()
        return change

    async def get_subscription_changes(
        self, session: AsyncSession, workspace_id: int
    ) -> list[SubscriptionChange]:
        res = await session.execute(
            select(SubscriptionChange)
            .where(SubscriptionChange.workspace_id == workspace_id)
            .order_by(SubscriptionChange.created_at.desc())
        )
        return list(res.scalars().all())

    async def get_plan_catalog(self, session: AsyncSession) -> list[WorkspaceLimit]:
        res = await session.execute(
            select(WorkspaceLimit)
            .where(WorkspaceLimit.workspace_id.is_(None))
            .order_by(WorkspaceLimit.price_micros.asc().nullslast())
        )
        return list(res.scalars().all())

    async def get_plan_definition(
        self, session: AsyncSession, plan_tier: str
    ) -> WorkspaceLimit | None:
        res = await session.execute(
            select(WorkspaceLimit).where(
                WorkspaceLimit.plan_tier == plan_tier.lower().strip(),
                WorkspaceLimit.workspace_id.is_(None),
            )
        )
        return res.scalars().first()

    async def create_plan_definition(
        self,
        session: AsyncSession,
        data: PlanDefinitionCreate,
        user_id: uuid.UUID | None = None,
    ) -> WorkspaceLimit:
        plan_tier = data.plan_tier.lower().strip()
        existing = await self.get_plan_definition(session, plan_tier)
        if existing is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Plan '{plan_tier}' already exists",
            )

        plan_limit = WorkspaceLimit(
            plan_tier=plan_tier,
            workspace_id=None,
            max_documents=data.max_documents,
            max_members=data.max_members,
            max_runs=data.max_runs,
            max_storage_bytes=data.max_storage_bytes,
            max_memory_count=data.max_memory_count,
            max_memory_bytes=data.max_memory_bytes,
            run_period_hours=data.run_period_hours or 720,
            max_monthly_credits=data.max_monthly_credits,
            max_sources=data.max_sources,
            support_level=data.support_level or "community",
            price_micros=data.price_micros or 0,
            currency=data.currency or "USD",
        )
        session.add(plan_limit)

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action="admin.plan_created",
                actor_id=user_id,
                diff_payload=data.model_dump(),
            )
        )
        await session.flush()
        return plan_limit

    async def update_plan_definition(
        self,
        session: AsyncSession,
        plan_tier: str,
        data: PlanDefinitionUpdate,
        user_id: uuid.UUID | None = None,
    ) -> WorkspaceLimit:
        plan_tier = plan_tier.lower().strip()
        plan_limit = await self.get_plan_definition(session, plan_tier)
        if plan_limit is None:
            raise HTTPException(
                status_code=404,
                detail=f"Plan '{plan_tier}' not found",
            )

        # Grandfathering invariant: snapshot existing limits for active workspaces on this tier
        ws_res = await session.execute(
            select(Workspace.id).where(Workspace.plan_tier == plan_tier)
        )
        active_ws_ids = ws_res.scalars().all()
        if active_ws_ids:
            existing_overrides_res = await session.execute(
                select(WorkspaceLimit.workspace_id).where(
                    WorkspaceLimit.workspace_id.in_(active_ws_ids),
                    WorkspaceLimit.plan_tier.is_(None),
                )
            )
            already_overridden = set(existing_overrides_res.scalars().all())
            for wid in active_ws_ids:
                if wid not in already_overridden:
                    session.add(
                        WorkspaceLimit(
                            workspace_id=wid,
                            plan_tier=None,
                            max_documents=plan_limit.max_documents,
                            max_members=plan_limit.max_members,
                            max_runs=plan_limit.max_runs,
                            max_storage_bytes=plan_limit.max_storage_bytes,
                            max_memory_count=plan_limit.max_memory_count,
                            max_memory_bytes=plan_limit.max_memory_bytes,
                            run_period_hours=plan_limit.run_period_hours,
                            max_monthly_credits=plan_limit.max_monthly_credits,
                            max_sources=plan_limit.max_sources,
                            support_level=plan_limit.support_level,
                            price_micros=plan_limit.price_micros,
                            currency=plan_limit.currency,
                        )
                    )

        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            if hasattr(plan_limit, k):
                setattr(plan_limit, k, v)

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action="admin.plan_updated",
                actor_id=user_id,
                diff_payload={"plan_tier": plan_tier, "updates": update_data},
            )
        )
        await session.flush()
        return plan_limit

    async def delete_plan_definition(
        self,
        session: AsyncSession,
        plan_tier: str,
        user_id: uuid.UUID | None = None,
    ) -> None:
        plan_tier = plan_tier.lower().strip()
        if plan_tier in ("free", "team", "growth", "enterprise"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete system default plan '{plan_tier}'",
            )

        ws_count_res = await session.execute(
            select(func.count(Workspace.id)).where(Workspace.plan_tier == plan_tier)
        )
        count = ws_count_res.scalar() or 0
        if count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete plan '{plan_tier}' as it is currently assigned to {count} workspace(s)",
            )

        plan_limit = await self.get_plan_definition(session, plan_tier)
        if plan_limit is None:
            raise HTTPException(
                status_code=404,
                detail=f"Plan '{plan_tier}' not found",
            )

        await session.delete(plan_limit)

        from app.models.billing import AuditEvent

        session.add(
            AuditEvent(
                action="admin.plan_deleted",
                actor_id=user_id,
                diff_payload={"deleted_plan": plan_tier},
            )
        )
        await session.flush()


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
