from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    INCENTIVE_TASKS_CONFIG,
    CreditPurchase,
    PagePurchase,
    TokenUsage,
    User,
    UserIncentiveTask,
)
from app.schemas.usage import (
    UsageBreakdownItem,
    UsageSummaryResponse,
    UsageTimeSeriesPoint,
    UsageTimeSeriesResponse,
    UsageTransactionItem,
    UsageTransactionsResponse,
)

Granularity = Literal["day", "week", "month"]


def _ensure_utc(value: datetime) -> datetime:
    """Make a datetime timezone-aware in UTC, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class UsageService:
    """Aggregate token usage, credit balance, and transaction history."""

    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user

    def _normalize_range(
        self, start_date: datetime | None, end_date: datetime | None
    ) -> tuple[datetime, datetime]:
        end_date = datetime.now(UTC) if end_date is None else _ensure_utc(end_date)
        start_date = (
            end_date - timedelta(days=30)
            if start_date is None
            else _ensure_utc(start_date)
        )

        if start_date > end_date:
            raise ValueError("start_date must not be after end_date")

        return start_date, end_date

    async def get_summary(
        self,
        workspace_id: int,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> UsageSummaryResponse:
        start_date, end_date = self._normalize_range(start_date, end_date)

        totals = await self._workspace_totals(workspace_id, start_date, end_date)
        by_usage_type = await self._breakdown_by_usage_type(
            workspace_id, start_date, end_date
        )
        by_model = await self._breakdown_by_model(workspace_id, start_date, end_date)
        by_provider = await self._breakdown_by_provider(
            workspace_id, start_date, end_date
        )

        return UsageSummaryResponse(
            current_balance_micros=self.user.credit_micros_balance,
            reserved_micros=self.user.credit_micros_reserved,
            total_tokens=totals["total_tokens"],
            total_cost_micros=totals["total_cost_micros"],
            start_date=start_date,
            end_date=end_date,
            by_usage_type=by_usage_type,
            by_model=by_model,
            by_provider=by_provider,
        )

    async def _workspace_totals(
        self, workspace_id: int, start_date: datetime, end_date: datetime
    ) -> dict[str, int]:
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label(
                    "total_cost_micros"
                ),
            ).filter(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= start_date,
                TokenUsage.created_at <= end_date,
            )
        )
        row = result.one()
        return {
            "total_tokens": int(row.total_tokens),
            "total_cost_micros": int(row.total_cost_micros),
        }

    async def _breakdown_by_usage_type(
        self, workspace_id: int, start_date: datetime, end_date: datetime
    ) -> list[UsageBreakdownItem]:
        result = await self.session.execute(
            select(
                TokenUsage.usage_type.label("key"),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
            )
            .filter(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= start_date,
                TokenUsage.created_at <= end_date,
            )
            .group_by(TokenUsage.usage_type)
            .order_by(func.sum(TokenUsage.cost_micros).desc())
        )
        return [
            UsageBreakdownItem(
                key=row.key,
                total_tokens=int(row.total_tokens),
                cost_micros=int(row.cost_micros),
            )
            for row in result.all()
        ]

    async def _breakdown_by_model(
        self, workspace_id: int, start_date: datetime, end_date: datetime
    ) -> list[UsageBreakdownItem]:
        """Explode model_breakdown JSONB and aggregate per model key."""
        stmt = text(
            """
            SELECT
                elem.key AS key,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(elem.value -> 'total_tokens') = 'number'
                        THEN (elem.value ->> 'total_tokens')::bigint
                        ELSE 0
                    END
                ), 0) AS total_tokens,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(elem.value -> 'cost_micros') = 'number'
                        THEN (elem.value ->> 'cost_micros')::bigint
                        ELSE 0
                    END
                ), 0) AS cost_micros
            FROM token_usage,
            LATERAL jsonb_each(
                COALESCE(NULLIF(token_usage.model_breakdown, '{}'::jsonb), '{}'::jsonb)
            ) AS elem
            WHERE token_usage.workspace_id = :workspace_id
              AND token_usage.created_at >= :start_date
              AND token_usage.created_at <= :end_date
            GROUP BY elem.key
            ORDER BY cost_micros DESC
            """
        )
        result = await self.session.execute(
            stmt,
            {
                "workspace_id": workspace_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return [
            UsageBreakdownItem(
                key=row.key,
                total_tokens=int(row.total_tokens),
                cost_micros=int(row.cost_micros),
            )
            for row in result.mappings().all()
        ]

    async def _breakdown_by_provider(
        self, workspace_id: int, start_date: datetime, end_date: datetime
    ) -> list[UsageBreakdownItem]:
        """Explode model_breakdown JSONB and aggregate by provider field."""
        stmt = text(
            """
            SELECT
                COALESCE(elem.value ->> 'provider', elem.key, 'unknown') AS key,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(elem.value -> 'total_tokens') = 'number'
                        THEN (elem.value ->> 'total_tokens')::bigint
                        ELSE 0
                    END
                ), 0) AS total_tokens,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(elem.value -> 'cost_micros') = 'number'
                        THEN (elem.value ->> 'cost_micros')::bigint
                        ELSE 0
                    END
                ), 0) AS cost_micros
            FROM token_usage,
            LATERAL jsonb_each(
                COALESCE(NULLIF(token_usage.model_breakdown, '{}'::jsonb), '{}'::jsonb)
            ) AS elem
            WHERE token_usage.workspace_id = :workspace_id
              AND token_usage.created_at >= :start_date
              AND token_usage.created_at <= :end_date
            GROUP BY COALESCE(elem.value ->> 'provider', elem.key, 'unknown')
            ORDER BY cost_micros DESC
            """
        )
        result = await self.session.execute(
            stmt,
            {
                "workspace_id": workspace_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return [
            UsageBreakdownItem(
                key=row.key,
                total_tokens=int(row.total_tokens),
                cost_micros=int(row.cost_micros),
            )
            for row in result.mappings().all()
        ]

    async def get_time_series(
        self,
        workspace_id: int,
        granularity: Granularity,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> UsageTimeSeriesResponse:
        start_date, end_date = self._normalize_range(start_date, end_date)

        # Build the period expression per granularity. All expressions are
        # evaluated in UTC and use safe string literals for the format string.
        period_expr = {
            "day": func.to_char(
                func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD"
            ),
            "week": func.to_char(
                func.timezone("UTC", TokenUsage.created_at), "IYYY-IW"
            ),
            "month": func.to_char(
                func.timezone("UTC", TokenUsage.created_at), "YYYY-MM"
            ),
        }[granularity]

        result = await self.session.execute(
            select(
                period_expr.label("period"),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
            )
            .filter(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= start_date,
                TokenUsage.created_at <= end_date,
            )
            .group_by(period_expr)
            .order_by(period_expr.asc())
        )

        points = [
            UsageTimeSeriesPoint(
                period=row.period,
                total_tokens=int(row.total_tokens),
                cost_micros=int(row.cost_micros),
            )
            for row in result.mappings().all()
        ]

        return UsageTimeSeriesResponse(granularity=granularity, points=points)

    async def get_transactions(
        self, limit: int, offset: int
    ) -> UsageTransactionsResponse:
        """Return a unified, paginated list of credit/page purchases and incentives."""
        credit_purchases = (
            (
                await self.session.execute(
                    select(CreditPurchase)
                    .where(CreditPurchase.user_id == self.user.id)
                    .order_by(CreditPurchase.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

        page_purchases = (
            (
                await self.session.execute(
                    select(PagePurchase)
                    .where(PagePurchase.user_id == self.user.id)
                    .order_by(PagePurchase.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

        incentives = (
            (
                await self.session.execute(
                    select(UserIncentiveTask)
                    .where(UserIncentiveTask.user_id == self.user.id)
                    .order_by(UserIncentiveTask.completed_at.desc())
                )
            )
            .scalars()
            .all()
        )

        transactions: list[UsageTransactionItem] = []

        for cp in credit_purchases:
            # Use completed_at when available; fallback to created_at.
            created_at = cp.completed_at or cp.created_at
            transactions.append(
                UsageTransactionItem(
                    type="credit_purchase",
                    amount_micros=cp.credit_micros_granted,
                    description=f"{cp.quantity} credit packs ({cp.source})",
                    status=cp.status.value if cp.status else None,
                    created_at=created_at,
                )
            )

        for pp in page_purchases:
            created_at = pp.completed_at or pp.created_at
            # amount_total is in Stripe's smallest currency unit (cents); convert to micros.
            amount_micros = (pp.amount_total or 0) * 10_000
            transactions.append(
                UsageTransactionItem(
                    type="page_purchase",
                    amount_micros=amount_micros,
                    description=f"Legacy {pp.pages_granted} page pack",
                    status=pp.status.value if pp.status else None,
                    created_at=created_at,
                )
            )

        for it in incentives:
            config = INCENTIVE_TASKS_CONFIG.get(it.task_type, {})
            title = config.get("title", it.task_type)
            transactions.append(
                UsageTransactionItem(
                    type="incentive",
                    amount_micros=it.credit_micros_awarded,
                    description=f"Earned credit: {title}",
                    status="completed",
                    created_at=it.completed_at,
                )
            )

        transactions.sort(key=lambda t: t.created_at, reverse=True)
        total = len(transactions)
        paginated = transactions[offset : offset + limit]

        return UsageTransactionsResponse(transactions=paginated, total=total)
