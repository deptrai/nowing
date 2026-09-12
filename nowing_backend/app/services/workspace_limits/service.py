"""Workspace limit resolution and gating.

This service is the single owner of per-workspace plan/override limit lookup
and enforcement for documents, members, and runs.  Storage is exposed but not
enforced in Story 8.12.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Workspace,
    WorkspaceLimit,
)

from .checks import WorkspaceChecksMixin
from .counting import WorkspaceCountingMixin
from .plans import WorkspacePlansMixin

logger = logging.getLogger(__name__)


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


class WorkspaceLimitService(
    WorkspaceCountingMixin, WorkspaceChecksMixin, WorkspacePlansMixin
):
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
