from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select

from app.db import (
    BillingEvent,
    CreditPurchase,
    TokenUsage,
)

from ._helpers import (
    _clamp_window,
    _make_billing_bucket_expr,
    _make_credit_bucket_expr,
    _make_time_bucket_expr,
)

logger = logging.getLogger(__name__)


class MarginTelemetryMixin:
    async def get_gross_margin(self, window_hours: int) -> dict[str, Any]:
        """Return revenue, COGS, and gross margin over a time window.

        Revenue = completed CreditPurchase.credit_micros_granted.
        COGS = TokenUsage.cost_micros + BillingEvent.cost_micros.
        """
        from app.db import Workspace

        window_hours = _clamp_window(window_hours)
        cutoff = self._cutoff(window_hours)
        granularity = self._granularity(window_hours)

        # Revenue per bucket
        credit_bucket = _make_credit_bucket_expr(granularity)
        credit_ts = func.coalesce(
            CreditPurchase.completed_at, CreditPurchase.created_at
        )
        revenue_stmt = (
            select(
                credit_bucket.label("period"),
                func.coalesce(func.sum(CreditPurchase.credit_micros_granted), 0).label(
                    "revenue_micros"
                ),
            )
            .where(
                CreditPurchase.status == "completed",
                credit_ts >= cutoff,
            )
            .group_by(credit_bucket)
            .order_by(credit_bucket.asc())
        )
        revenue_rows = (await self.session.execute(revenue_stmt)).all()

        # COGS per bucket from TokenUsage
        token_bucket = _make_time_bucket_expr(granularity)
        token_cogs_stmt = (
            select(
                token_bucket.label("period"),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cogs_micros"),
            )
            .where(TokenUsage.created_at >= cutoff)
            .group_by(token_bucket)
            .order_by(token_bucket.asc())
        )
        token_cogs_rows = (await self.session.execute(token_cogs_stmt)).all()

        # COGS per bucket from BillingEvent
        billing_bucket = _make_billing_bucket_expr(granularity)
        billing_cogs_stmt = (
            select(
                billing_bucket.label("period"),
                func.coalesce(func.sum(BillingEvent.cost_micros), 0).label(
                    "cogs_micros"
                ),
            )
            .where(BillingEvent.created_at >= cutoff)
            .group_by(billing_bucket)
            .order_by(billing_bucket.asc())
        )
        billing_cogs_rows = (await self.session.execute(billing_cogs_stmt)).all()

        # Merge revenue and COGS by period
        revenue_by_period = {
            row.period: int(row.revenue_micros) for row in revenue_rows
        }
        token_cogs_by_period: dict[str, int] = defaultdict(int)
        billing_cogs_by_period: dict[str, int] = defaultdict(int)
        for row in token_cogs_rows:
            token_cogs_by_period[row.period] += int(row.cogs_micros)
        for row in billing_cogs_rows:
            billing_cogs_by_period[row.period] += int(row.cogs_micros)

        all_periods = sorted(
            set(revenue_by_period.keys())
            | set(token_cogs_by_period.keys())
            | set(billing_cogs_by_period.keys())
        )
        points = []
        total_revenue = 0
        total_token_cogs = 0
        total_billing_cogs = 0
        for period in all_periods:
            revenue = revenue_by_period.get(period, 0)
            token_cogs = token_cogs_by_period.get(period, 0)
            billing_cogs = billing_cogs_by_period.get(period, 0)
            cogs = token_cogs + billing_cogs
            total_revenue += revenue
            total_token_cogs += token_cogs
            total_billing_cogs += billing_cogs
            margin = None
            if revenue != 0:
                margin = (revenue - cogs) / revenue
            points.append(
                {
                    "period": period,
                    "revenue_micros": revenue,
                    "cogs_micros": cogs,
                    "gross_margin": margin,
                }
            )

        total_cogs = total_token_cogs + total_billing_cogs
        overall_margin = None
        if total_revenue != 0:
            overall_margin = (total_revenue - total_cogs) / total_revenue

        # Worst workspace margin: per-workspace revenue vs cogs.
        # ponytail: CreditPurchase has no workspace_id, so we attribute revenue to
        # the user's owned workspaces via Workspace.user_id. This is a v1
        # approximation; a dedicated workspace_id on credit_purchases would be
        # more accurate.
        workspace_revenue_stmt = (
            select(
                Workspace.id.label("workspace_id"),
                func.coalesce(func.sum(CreditPurchase.credit_micros_granted), 0).label(
                    "revenue_micros"
                ),
            )
            .join(CreditPurchase, Workspace.user_id == CreditPurchase.user_id)
            .where(
                CreditPurchase.status == "completed",
                func.coalesce(CreditPurchase.completed_at, CreditPurchase.created_at)
                >= cutoff,
            )
            .group_by(Workspace.id)
        )
        workspace_revenue_rows = (
            await self.session.execute(workspace_revenue_stmt)
        ).all()

        workspace_cogs_stmt = (
            select(
                TokenUsage.workspace_id,
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cogs_micros"),
            )
            .where(TokenUsage.created_at >= cutoff)
            .group_by(TokenUsage.workspace_id)
        )
        workspace_cogs_rows = (await self.session.execute(workspace_cogs_stmt)).all()

        workspace_billing_cogs_stmt = (
            select(
                BillingEvent.workspace_id,
                func.coalesce(func.sum(BillingEvent.cost_micros), 0).label(
                    "cogs_micros"
                ),
            )
            .where(BillingEvent.created_at >= cutoff)
            .group_by(BillingEvent.workspace_id)
        )
        workspace_billing_cogs_rows = (
            await self.session.execute(workspace_billing_cogs_stmt)
        ).all()

        revenue_by_workspace = {
            int(row.workspace_id): int(row.revenue_micros)
            for row in workspace_revenue_rows
        }
        cogs_by_workspace: dict[int, int] = defaultdict(int)
        for row in workspace_cogs_rows:
            cogs_by_workspace[int(row.workspace_id)] += int(row.cogs_micros)
        for row in workspace_billing_cogs_rows:
            cogs_by_workspace[int(row.workspace_id)] += int(row.cogs_micros)

        worst_workspace_id = None
        worst_workspace_margin = None
        for ws_id, revenue in revenue_by_workspace.items():
            if revenue <= 0:
                continue
            cogs = cogs_by_workspace.get(ws_id, 0)
            margin = (revenue - cogs) / revenue
            if worst_workspace_margin is None or margin < worst_workspace_margin:
                worst_workspace_margin = margin
                worst_workspace_id = ws_id

        # Worst model by token COGS
        model_expr = self._model_expr()
        model_cogs_stmt = (
            select(
                model_expr,
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cogs_micros"),
            )
            .where(TokenUsage.created_at >= cutoff)
            .group_by(model_expr)
            .order_by(func.coalesce(func.sum(TokenUsage.cost_micros), 0).desc())
            .limit(1)
        )
        worst_model_row = (await self.session.execute(model_cogs_stmt)).one_or_none()
        worst_model = worst_model_row.model if worst_model_row else None

        return {
            "window_hours": window_hours,
            "total_revenue_micros": total_revenue,
            "total_cogs_micros": total_cogs,
            "overall_gross_margin": overall_margin,
            "billing_cost_micros": total_billing_cogs,
            "non_llm_cost_micros": total_billing_cogs,
            "worst_workspace_id": worst_workspace_id,
            "worst_workspace_margin": worst_workspace_margin,
            "worst_model": worst_model,
            "points": points,
        }
