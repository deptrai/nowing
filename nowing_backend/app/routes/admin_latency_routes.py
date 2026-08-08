"""Admin endpoint for ChainLens deep-research latency percentiles (T5).

Percentiles are computed in PostgreSQL with ``percentile_cont`` over the
dedicated ``TokenUsage.e2e_ms`` / ``ttfb_ms`` columns, falling back to the JSON
``call_details`` for rows written before the columns were added. The endpoint is
intended for platform operators to baseline latency per research mode.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import TokenUsage, get_async_session
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/metrics")

_ALLOWED_MODES = {"speed", "balanced", "quality", "auto"}


class LatencyPercentile(BaseModel):
    mode: str
    p50: float | None
    p95: float | None
    samples: int


class DeepResearchLatencyResponse(BaseModel):
    metric: str
    window_days: int
    percentiles: list[LatencyPercentile]


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
    p: float | None = Query(default=None, ge=0.0, le=1.0),
) -> DeepResearchLatencyResponse:
    """Return p50/p95 latency per research mode for the last ``window_days`` days."""
    if mode and mode not in _ALLOWED_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode. Allowed: {sorted(_ALLOWED_MODES)}",
        )
    field = "e2e_ms" if metric == "e2e" else "ttfb_ms"
    column = TokenUsage.e2e_ms if metric == "e2e" else TokenUsage.ttfb_ms
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    # Use the dedicated column when it exists, otherwise fall back to the JSON
    # call_details value if it is actually a JSON number.
    numeric_json = case(
        (
            func.jsonb_typeof(TokenUsage.call_details[field]) == "number",
            TokenUsage.call_details[field].as_float(),
        )
    )
    value_expr = func.coalesce(column, numeric_json)

    # Resolve the effective research mode per row: resolved, then details,
    # then requested, then "unknown".
    mode_expr = func.coalesce(
        TokenUsage.resolved_mode,
        TokenUsage.call_details["resolved_mode"].as_string(),
        TokenUsage.mode_requested,
        TokenUsage.call_details["mode_requested"].as_string(),
        "unknown",
    ).label("mode")

    stmt = (
        select(
            mode_expr,
            func.count(value_expr).label("samples"),
            func.percentile_cont(0.5).within_group(value_expr.asc()).label("p50"),
            func.percentile_cont(0.95).within_group(value_expr.asc()).label("p95"),
        )
        .where(TokenUsage.usage_type == "deep_research")
        .where(TokenUsage.created_at >= cutoff)
        .where(value_expr >= 0)
    )
    if mode:
        stmt = stmt.where(
            or_(
                TokenUsage.resolved_mode == mode,
                TokenUsage.mode_requested == mode,
                TokenUsage.call_details["resolved_mode"].as_string() == mode,
                TokenUsage.call_details["mode_requested"].as_string() == mode,
            )
        )

    rows = (await session.execute(stmt.group_by(mode_expr).order_by(mode_expr))).all()

    percentiles = []
    for row in rows:
        p50 = float(row.p50) if row.p50 is not None and row.samples > 0 else None
        p95 = float(row.p95) if row.p95 is not None and row.samples > 0 else None
        percentiles.append(
            LatencyPercentile(
                mode=row.mode,
                p50=p50,
                p95=p95,
                samples=row.samples,
            )
        )

    return DeepResearchLatencyResponse(
        metric=metric,
        window_days=window_days,
        percentiles=sorted(percentiles, key=lambda x: x.mode),
    )
