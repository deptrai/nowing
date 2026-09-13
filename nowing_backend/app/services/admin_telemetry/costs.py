from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from app.db import (
    BillingEvent,
    TokenUsage,
)

from ._helpers import _ALLOWED_PROVIDERS, _clamp_window, _make_time_bucket_expr

logger = logging.getLogger(__name__)


class CostTelemetryMixin:
    async def get_llm_cost_breakdown(
        self,
        window_hours: int,
        provider: str | None = None,
        workspace_id: int | None = None,
    ) -> dict[str, Any]:
        """Return aggregate LLM cost/token breakdowns and a time series.

        ``provider`` filters to one provider (case-insensitive); unsupported
        values are treated as ``unknown`` and still returned if they exist in the
        data.
        """
        window_hours = _clamp_window(window_hours)
        cutoff = self._cutoff(window_hours)
        granularity = self._granularity(window_hours)
        provider_normalized = (provider or "").strip().lower() or None

        token_filters = self._token_filters(cutoff, workspace_id)

        # Aggregate totals
        total_stmt = select(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.cost_micros), 0).label(
                "total_cost_micros"
            ),
            func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
            func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            func.coalesce(
                func.count(TokenUsage.id).filter(
                    func.coalesce(TokenUsage.cost_micros, 0) == 0
                ),
                0,
            ).label("unreported_cost_rows"),
        ).where(*token_filters)

        totals = (await self.session.execute(total_stmt)).one()

        # Provider breakdown
        provider_expr = self._provider_expr()
        provider_stmt = (
            select(
                provider_expr,
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
                func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
                func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            )
            .where(*token_filters)
            .group_by(provider_expr)
            .order_by(func.sum(TokenUsage.cost_micros).desc())
        )
        if provider_normalized:
            provider_stmt = provider_stmt.where(
                provider_expr == provider_normalized
                if provider_normalized in _ALLOWED_PROVIDERS
                else provider_expr == "unknown"
            )

        provider_rows = (await self.session.execute(provider_stmt)).all()

        # Model breakdown
        model_expr = self._model_expr()
        model_stmt = (
            select(
                model_expr,
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
                func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
                func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            )
            .where(*token_filters)
            .group_by(model_expr)
            .order_by(func.sum(TokenUsage.cost_micros).desc())
            .limit(100)
        )
        if provider_normalized:
            provider_col = self._provider_expr()
            model_stmt = model_stmt.where(
                provider_col == provider_normalized
                if provider_normalized in _ALLOWED_PROVIDERS
                else provider_col == "unknown"
            )

        model_rows = (await self.session.execute(model_stmt)).all()

        # Workspace breakdown
        workspace_stmt = (
            select(
                TokenUsage.workspace_id,
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
                func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
                func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            )
            .where(*token_filters)
            .group_by(TokenUsage.workspace_id)
            .order_by(func.sum(TokenUsage.cost_micros).desc())
            .limit(100)
        )
        if provider_normalized:
            provider_col = self._provider_expr()
            workspace_stmt = workspace_stmt.where(
                provider_col == provider_normalized
                if provider_normalized in _ALLOWED_PROVIDERS
                else provider_col == "unknown"
            )
        workspace_rows = (await self.session.execute(workspace_stmt)).all()

        # Usage type breakdown
        usage_type_stmt = (
            select(
                TokenUsage.usage_type,
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
                func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
                func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            )
            .where(*token_filters)
            .group_by(TokenUsage.usage_type)
            .order_by(func.sum(TokenUsage.cost_micros).desc())
        )
        if provider_normalized:
            provider_col = self._provider_expr()
            usage_type_stmt = usage_type_stmt.where(
                provider_col == provider_normalized
                if provider_normalized in _ALLOWED_PROVIDERS
                else provider_col == "unknown"
            )
        usage_type_rows = (await self.session.execute(usage_type_stmt)).all()

        # Time series
        bucket_expr = _make_time_bucket_expr(granularity)
        ts_stmt = (
            select(
                bucket_expr.label("period"),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
                func.coalesce(self._prompt_tokens_expr(), 0).label("input_tokens"),
                func.coalesce(self._completion_tokens_expr(), 0).label("output_tokens"),
            )
            .where(*token_filters)
            .group_by(bucket_expr)
            .order_by(bucket_expr.asc())
        )
        if provider_normalized:
            provider_col = self._provider_expr()
            ts_stmt = ts_stmt.where(
                provider_col == provider_normalized
                if provider_normalized in _ALLOWED_PROVIDERS
                else provider_col == "unknown"
            )

        ts_rows = (await self.session.execute(ts_stmt)).all()

        # Billing cost total (non-LLM COGS) - not bucketed by provider/model
        billing_filters = [BillingEvent.created_at >= cutoff]
        if workspace_id is not None:
            billing_filters.append(BillingEvent.workspace_id == workspace_id)
        billing_stmt = select(
            func.coalesce(func.sum(BillingEvent.cost_micros), 0).label(
                "billing_cost_micros"
            )
        ).where(*billing_filters)
        billing_row = (await self.session.execute(billing_stmt)).one()

        def _bucket(rows, key_attr: str = "key"):
            return [
                {
                    "key": str(getattr(row, key_attr)),
                    "total_tokens": int(row.total_tokens),
                    "cost_micros": int(row.cost_micros),
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                }
                for row in rows
            ]

        return {
            "window_hours": window_hours,
            "provider": provider,
            "workspace_id": workspace_id,
            "total_tokens": int(totals.total_tokens),
            "total_cost_micros": int(totals.total_cost_micros),
            "non_llm_cost_micros": int(billing_row.billing_cost_micros),
            "billing_cost_micros": int(billing_row.billing_cost_micros),
            "input_tokens": int(totals.input_tokens),
            "output_tokens": int(totals.output_tokens),
            "by_provider": _bucket(provider_rows, key_attr="provider"),
            "by_model": _bucket(model_rows, key_attr="model"),
            "by_workspace": _bucket(workspace_rows, key_attr="workspace_id"),
            "by_usage_type": _bucket(usage_type_rows, key_attr="usage_type"),
            "time_series": [
                {
                    "period": row.period,
                    "total_tokens": int(row.total_tokens),
                    "cost_micros": int(row.cost_micros),
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                }
                for row in ts_rows
            ],
            "unreported_cost_rows": int(totals.unreported_cost_rows),
        }
