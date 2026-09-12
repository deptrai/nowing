"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    SubscriptionChange,
    Workspace,
    WorkspaceLimit,
)
from app.schemas.workspace import PlanDefinitionCreate, PlanDefinitionUpdate


class WorkspacePlansMixin:
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
