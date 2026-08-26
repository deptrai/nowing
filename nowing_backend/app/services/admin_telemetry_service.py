from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import (
    CELERY_TASK_DEFAULT_QUEUE,
    CONNECTORS_QUEUE,
    LEAD_SCRAPERS_QUEUE,
    celery_app,
)
from app.config import config
from app.db import (
    AuditEvent,
    BillingEvent,
    CreditPurchase,
    TokenUsage,
)
from app.services.proxy_health_cache import (
    get_proxy_health_snapshot,
    update_proxy_health_snapshot,
)
from app.utils.proxy import get_active_provider

logger = logging.getLogger(__name__)

_ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "deepseek"}
_MAX_WINDOW_HOURS = 720  # 30 days
_CELERY_TASK_STALLED_SECONDS = getattr(config, "CELERY_TASK_STALLED_SECONDS", 300)
_QUEUE_NAMES = [
    CELERY_TASK_DEFAULT_QUEUE,
    CONNECTORS_QUEUE,
    LEAD_SCRAPERS_QUEUE,
    f"{CELERY_TASK_DEFAULT_QUEUE}.gateway",
]


def _redact_url(url: str | None) -> str | None:
    """Strip user:pass credentials from a proxy URL before returning it."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    if not parsed.username and not parsed.password:
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}{parsed.path or ''}"


def _redact_error(text: str | None) -> str | None:
    """Redact any embedded proxy credentials from an error string."""
    if not text:
        return text
    return re.sub(r"(https?://)[^:@\s]+:[^@\s]+@", r"\1***:***@", text)


def _is_redis_broker(url: str) -> bool:
    """Return True for Redis/Socket broker URLs used by Celery."""
    if not url:
        return False
    try:
        return urlparse(url).scheme in {"redis", "rediss", "unixsocket"}
    except Exception:
        return url.startswith(("redis://", "rediss://", "unixsocket://"))


def _clamp_window(window_hours: int) -> int:
    """Clamp requested window to [1, 720] hours."""
    if window_hours < 1:
        return 1
    if window_hours > _MAX_WINDOW_HOURS:
        return _MAX_WINDOW_HOURS
    return window_hours


def _make_time_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets created_at into a string period."""
    if granularity == "hour":
        return func.to_char(
            func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD HH24:00"
        )
    if granularity == "day":
        return func.to_char(func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD")
    return func.to_char(
        func.timezone("UTC", TokenUsage.created_at), "YYYY-MM-DD HH24:00"
    )


def _make_credit_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets CreditPurchase.completed_at (or created_at if pending) into a string period."""
    credit_ts = func.coalesce(CreditPurchase.completed_at, CreditPurchase.created_at)
    if granularity == "hour":
        return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD HH24:00")
    if granularity == "day":
        return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD")
    return func.to_char(func.timezone("UTC", credit_ts), "YYYY-MM-DD HH24:00")


def _make_billing_bucket_expr(granularity: str) -> Any:
    """Return a SQLAlchemy expression that buckets BillingEvent.created_at into a string period."""
    if granularity == "hour":
        return func.to_char(
            func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD HH24:00"
        )
    if granularity == "day":
        return func.to_char(func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD")
    return func.to_char(
        func.timezone("UTC", BillingEvent.created_at), "YYYY-MM-DD HH24:00"
    )


class AdminTelemetryService:
    """Aggregate telemetry for platform superadmins.

    Reuses SQL patterns from :class:`app.services.usage_service.UsageService`
    but removes the workspace scoping and adds admin-only dimensions.
    """

    def __init__(self, session: AsyncSession | None):
        self.session = session

    def _cutoff(self, window_hours: int) -> datetime:
        """Return the earliest inclusive timestamp for the window.

        Floored to the bucket boundary (hour or day) so time-series buckets
        start cleanly. This may slightly widen the window to the nearest whole
        bucket; callers display ``window_hours`` as requested.
        """
        window_hours = _clamp_window(window_hours)
        raw = datetime.now(UTC) - timedelta(hours=window_hours)
        if self._granularity(window_hours) == "hour":
            return raw.replace(minute=0, second=0, microsecond=0)
        return raw.replace(hour=0, minute=0, second=0, microsecond=0)

    def _granularity(self, window_hours: int) -> str:
        """Pick hour buckets for <= 48h, day buckets otherwise."""
        return "hour" if window_hours <= 48 else "day"

    def _token_filters(
        self, cutoff: datetime, workspace_id: int | None = None
    ) -> list[Any]:
        filters = [TokenUsage.created_at >= cutoff]
        if workspace_id is not None:
            filters.append(TokenUsage.workspace_id == workspace_id)
        return filters

    def _provider_expr(self) -> Any:
        """Resolve provider from model_breakdown JSONB, lower/trim, and bucket unsupported values to 'unknown'."""
        from_jsonb = func.trim(
            func.lower(
                func.coalesce(TokenUsage.model_breakdown["provider"].as_string(), "")
            )
        )
        from_details = func.trim(
            func.lower(
                func.coalesce(TokenUsage.call_details["provider"].as_string(), "")
            )
        )
        raw = func.coalesce(
            func.nullif(from_jsonb, ""),
            func.nullif(from_details, ""),
            "unknown",
        ).label("provider_raw")
        return case((raw.in_(list(_ALLOWED_PROVIDERS)), raw), else_="unknown").label(
            "provider"
        )

    def _model_expr(self) -> Any:
        """Resolve model key from model_breakdown JSONB."""
        return func.coalesce(
            func.nullif(func.trim(TokenUsage.model_breakdown["model"].as_string()), ""),
            func.coalesce(TokenUsage.call_details["model"].as_string(), ""),
            "unknown",
        ).label("model")

    def _prompt_tokens_expr(self) -> Any:
        return func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label(
            "input_tokens"
        )

    def _completion_tokens_expr(self) -> Any:
        return func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label(
            "output_tokens"
        )

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

    async def get_proxy_health(self) -> dict[str, Any]:
        """Return a cached snapshot of the active proxy provider's health.

        Probes are best-effort, throttled to once per 10 seconds per process.
        """
        provider = get_active_provider()
        provider_name = getattr(provider, "name", "unknown")
        proxy_url = provider.get_proxy_url()

        if not proxy_url:
            return {
                "status": "not_configured",
                "provider": provider_name,
                "snapshots": [],
                "total": 0,
                "healthy": 0,
                "degraded": 0,
                "dead": 0,
            }

        # Throttle: use a per-process cache to avoid hammering the proxy
        cached = get_proxy_health_snapshot()
        if cached is not None:
            return cached

        proxies = provider.get_requests_proxies()
        # httpx 0.28.1 uses ``proxy=`` with a URL string, not ``proxies=``.
        proxy_for_client = (
            proxies.get("https") or proxies.get("http") if proxies else None
        )
        start = time.perf_counter()
        last_error: str | None = None
        latency_ms: int | None = None
        status = "dead"

        try:
            async with httpx.AsyncClient(
                proxy=proxy_for_client, timeout=5.0, follow_redirects=True
            ) as client:
                response = await client.head("https://www.google.com")
                elapsed_ms = (time.perf_counter() - start) * 1000
                latency_ms = int(elapsed_ms)
                if response.status_code < 400:
                    if latency_ms <= 500:
                        status = "healthy"
                    elif latency_ms <= 2000:
                        status = "degraded"
                    else:
                        status = "dead"
                else:
                    status = "dead"
                    last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # pragma: no cover - network failures
            status = "dead"
            last_error = _redact_error(f"{type(exc).__name__}: {exc}")
            latency_ms = int((time.perf_counter() - start) * 1000)

        snapshot = {
            "provider": provider_name,
            "url": _redact_url(proxy_url),
            "latency_ms": latency_ms,
            "success_rate": 100.0 if status in {"healthy", "degraded"} else 0.0,
            "status": status,
            "last_error": _redact_error(last_error),
            "last_probed_at": datetime.now(UTC),
        }

        result = {
            "status": status,
            "provider": provider_name,
            "snapshots": [snapshot],
            "total": 1,
            "healthy": 1 if status == "healthy" else 0,
            "degraded": 1 if status == "degraded" else 0,
            "dead": 1 if status == "dead" else 0,
        }
        update_proxy_health_snapshot(result)
        return result

    async def get_celery_queue_stats(self) -> dict[str, Any]:
        """Return Celery queue lengths and worker telemetry.

        Uses Redis directly for queue lengths and Celery ``control.inspect``
        for worker/task metadata. Falls back to ``unavailable`` when the
        broker cannot be reached.
        """
        import redis.asyncio as aioredis

        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            # ``control.inspect()`` calls are synchronous and block the event
            # loop; run them in a thread and unwrap any awaitable results.
            stats = await _maybe_async(await asyncio.to_thread(inspect.stats)) or {}
            active = await _maybe_async(await asyncio.to_thread(inspect.active)) or {}
            scheduled = (
                await _maybe_async(await asyncio.to_thread(inspect.scheduled)) or {}
            )
            reserved = (
                await _maybe_async(await asyncio.to_thread(inspect.reserved)) or {}
            )
            active_queues = (
                await _maybe_async(await asyncio.to_thread(inspect.active_queues)) or {}
            )
        except Exception as exc:
            logger.warning("Celery inspect failed: %s", exc)
            return {
                "status": "unavailable",
                "active_workers": 0,
                "queues": [],
            }

        worker_count = len(stats)

        # Aggregate tasks per queue from active/scheduled/reserved.
        per_queue_tasks: dict[str, int] = defaultdict(int)
        for source in (active, scheduled, reserved):
            for _worker, tasks in source.items():
                for task in tasks or []:
                    if isinstance(task, (list, tuple)):
                        task = task[0]
                    queue = (
                        task.get("delivery_info", {}).get("routing_key")
                        or task.get("properties", {}).get("routing_key")
                        or "unknown"
                    )
                    per_queue_tasks[queue] += 1

        # Discover queue names: hardcoded fallback + active queues + Redis keys.
        discovered_queues: set[str] = set(_QUEUE_NAMES)
        for queues_info in active_queues.values():
            for q in queues_info or []:
                name = q.get("name")
                if name:
                    discovered_queues.add(name)

        broker_url = config.CELERY_BROKER_URL or ""
        if _is_redis_broker(broker_url):
            try:
                redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
                async for key in redis_client.scan_iter(match="celery*"):
                    discovered_queues.add(key.decode())
                await redis_client.aclose()
            except Exception as exc:
                logger.warning("Redis queue discovery failed: %s", exc)

        queue_names = sorted(discovered_queues)
        queue_lengths = await _redis_queue_lengths(queue_names)

        queues = []
        for name in queue_names:
            length = queue_lengths.get(name, 0)
            tasks = per_queue_tasks.get(name, 0)
            workers = sum(
                1
                for queues_info in active_queues.values()
                for q in (queues_info or [])
                if q.get("name") == name
            )
            status = "healthy"
            if length > 10000:
                status = "backed_up"
            elif length > 1000:
                status = "degraded"

            queues.append(
                {
                    "name": name,
                    "length": length,
                    "workers": workers,
                    "throughput_per_min": tasks,  # best-effort active-task proxy
                    "stalled_count": 0,  # first version: not computed inline
                    "status": status,
                }
            )

        overall = "healthy"
        if any(q["status"] == "backed_up" for q in queues):
            overall = "degraded"
        if worker_count == 0 or not queue_lengths:
            overall = "unavailable"

        return {
            "status": overall,
            "active_workers": worker_count,
            "queues": queues,
        }

    async def purge_dead_letter_queue(
        self,
        queue_name: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        """Purge stalled tasks from a Celery queue.

        Acquires a Redis lock, writes an ``AuditEvent``, and removes messages
        older than ``CELERY_TASK_STALLED_SECONDS`` from the Redis queue.
        """
        import redis.asyncio as aioredis

        if queue_name not in _QUEUE_NAMES:
            raise ValueError(f"Unknown queue: {queue_name}")

        # Idempotency key is for AuditEvent/client correlation only.
        idempotency_key = str(uuid.uuid4())
        # The lock is deterministic per queue so concurrent purges are rejected.
        lock_name = f"purge_dlq:{queue_name}"

        broker_url = config.CELERY_BROKER_URL or ""
        if not _is_redis_broker(broker_url):
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        try:
            redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
        except Exception as exc:
            logger.warning("Failed to connect to Redis for purge: %s", exc)
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        lock = redis_client.lock(lock_name, timeout=10)
        if not await lock.acquire(blocking=False):
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }

        try:
            now_wall = time.time()
            now_mono = time.monotonic_ns()
            threshold = _CELERY_TASK_STALLED_SECONDS
            purged = 0
            kept = 0

            # v1: read the whole queue, then atomically replace it with the
            # kept messages. There is a read-modify-write race with producers
            # pushing new messages between LRANGE and the pipeline; acceptable
            # for an emergency purge in v1.
            queue_len = int(await redis_client.llen(queue_name) or 0)
            messages = (
                await redis_client.lrange(queue_name, 0, queue_len - 1)
                if queue_len > 0
                else []
            )
            to_repush: list[bytes] = []

            for raw in messages:
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Malformed message - treat as stalled and purge
                    purged += 1
                    continue

                timestamps = payload.get("properties", {}).get("timestamps", {}) or {}
                sent_at = timestamps.get("sent")
                enqueued_ns = payload.get("headers", {}).get("nowing.enqueued_at_ns")

                stale = False
                if sent_at is not None:
                    # ``timestamps["sent"]`` is wall time, so compare with time.time().
                    try:
                        if now_wall - float(sent_at) > threshold:
                            stale = True
                    except (ValueError, TypeError):
                        pass
                elif enqueued_ns is not None:
                    # ``nowing.enqueued_at_ns`` is set with time.monotonic_ns(),
                    # so compare with time.monotonic_ns().
                    try:
                        if (now_mono - int(enqueued_ns)) / 1e9 > threshold:
                            stale = True
                    except (ValueError, TypeError):
                        pass

                if stale:
                    purged += 1
                    continue

                to_repush.append(raw)
                kept += 1

            # Only mutate when we are actually dropping messages; this avoids
            # the read-modify-write race for the common nothing-to-purge case.
            if purged > 0 or (queue_len > 0 and not to_repush):
                async with redis_client.pipeline(transaction=True) as pipe:
                    pipe.delete(queue_name)
                    if to_repush:
                        pipe.rpush(queue_name, *to_repush)
                    await pipe.execute()

            if actor_id:
                self.session.add(
                    AuditEvent(
                        action="telemetry.purge_dlq",
                        actor_id=actor_id,
                        diff_payload={"queue": queue_name, "count": purged},
                    )
                )
                await self.session.commit()

            return {
                "queue_name": queue_name,
                "purged_count": purged,
                "idempotency_key": idempotency_key,
            }
        except Exception as exc:
            logger.exception("Failed to purge dead queue: %s", exc)
            return {
                "queue_name": queue_name,
                "purged_count": 0,
                "idempotency_key": idempotency_key,
            }
        finally:
            with contextlib.suppress(Exception):
                await lock.release()
            await redis_client.aclose()


async def _maybe_async(value: Any) -> Any:
    """Unwrap a Celery promise/Result that may be awaitable."""
    if hasattr(value, "__await__"):
        return await value
    return value


async def _redis_queue_lengths(queue_names: list[str]) -> dict[str, int]:
    """Return the Redis list length for each Celery queue."""
    import redis.asyncio as aioredis

    broker_url = config.CELERY_BROKER_URL or ""
    if not _is_redis_broker(broker_url):
        return {}

    try:
        redis_client = aioredis.from_url(broker_url, socket_connect_timeout=2)
        lengths = {}
        for name in queue_names:
            try:
                lengths[name] = int(await redis_client.llen(name) or 0)
            except Exception:
                # Non-list key (e.g. a discovered Redis string); report 0.
                lengths[name] = 0
    except Exception as exc:
        logger.warning("Redis queue length query failed: %s", exc)
        lengths = {}
    finally:
        if "redis_client" in locals():
            await redis_client.aclose()

    return lengths
