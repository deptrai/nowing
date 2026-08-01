"""Admin endpoint for ChainLens deep-research latency percentiles (T5).

The percentiles are computed in Python from ``TokenUsage.call_details`` so the
JSON values do not require a migration to dedicated columns. The endpoint is
intended for platform operators to baseline latency per research mode.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import TokenUsage, get_async_session
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/metrics")


class LatencyPercentile(BaseModel):
    mode: str
    p50: float
    p95: float
    samples: int


class DeepResearchLatencyResponse(BaseModel):
    metric: str
    window_days: int
    percentiles: list[LatencyPercentile]


def _percentile(values: list[float], p: float) -> float:
    """Return the ``p``-th percentile using linear interpolation.

    Mirrors ``numpy.percentile`` for a small number of observations.
    """
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 1:
        return float(sorted_values[0])
    idx = (n - 1) * p
    low = int(idx)
    high = low + 1
    if high >= n:
        return float(sorted_values[-1])
    weight = idx - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


@router.get(
    "/deep-research-latency",
    response_model=DeepResearchLatencyResponse,
    status_code=status.HTTP_200_OK,
)
async def deep_research_latency(
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(require_superuser),
    metric: str = Query(default="e2e", pattern="^(e2e|ttfb)$"),
    window_days: int = Query(default=7, ge=1, le=90),
    mode: str | None = Query(default=None),
) -> DeepResearchLatencyResponse:
    """Return p50/p95 latency per research mode for the last ``window_days`` days."""
    field = "e2e_ms" if metric == "e2e" else "ttfb_ms"
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    stmt = (
        select(TokenUsage)
        .where(TokenUsage.usage_type == "deep_research")
        .where(TokenUsage.created_at >= cutoff)
    )
    if mode:
        stmt = stmt.where(TokenUsage.call_details["mode_requested"].as_string() == mode)

    rows = (await session.execute(stmt)).scalars().all()

    by_mode: dict[str, list[float]] = {}
    for row in rows:
        if not row.call_details:
            continue
        details: dict[str, Any] = row.call_details
        value = details.get(field)
        if not isinstance(value, (int, float)) or value < 0:
            continue
        mode_key = (
            details.get("mode_requested") or details.get("resolved_mode") or "unknown"
        )
        by_mode.setdefault(str(mode_key), []).append(float(value))

    percentiles = []
    for mode_key, values in by_mode.items():
        percentiles.append(
            LatencyPercentile(
                mode=mode_key,
                p50=_percentile(values, 0.5),
                p95=_percentile(values, 0.95),
                samples=len(values),
            )
        )

    return DeepResearchLatencyResponse(
        metric=metric,
        window_days=window_days,
        percentiles=sorted(percentiles, key=lambda x: x.mode),
    )
