"""``vn_bds.aggregate`` executor: fan-out to P0 scrapers and merge results."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.capabilities.core import CapabilityContext, Executor
from app.capabilities.core.progress import emit_progress
from app.services.bds_aggregator.orchestrator import aggregate

from .schemas import VnBdsAggregateInput, VnBdsAggregateOutput

logger = logging.getLogger(__name__)

AggregateFn = Callable[..., Awaitable[VnBdsAggregateOutput]]


def build_aggregate_executor(
    aggregate_fn: AggregateFn | None = None,
) -> Executor:
    """Bind the executor to an aggregator function (defaults to the real engine)."""
    aggregate_fn = aggregate_fn or aggregate

    async def execute(
        payload: VnBdsAggregateInput,
        ctx: CapabilityContext | None = None,
    ) -> VnBdsAggregateOutput:
        emit_progress(
            "starting",
            f"Aggregating BĐS listings from {', '.join(payload.sources)}",
            total=payload.max_items_per_source * len(payload.sources),
            unit="item",
        )

        try:
            if ctx is not None:
                output = await aggregate_fn(
                    payload,
                    workspace_id=ctx.workspace_id,
                    session=ctx.session,
                )
            else:
                output = await aggregate_fn(payload)
        except Exception:
            logger.exception("vn_bds.aggregate executor failed")
            return VnBdsAggregateOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reasons=["api_error"],
                source_breakdown={},
            )

        emit_progress(
            "done",
            f"Aggregated {output.total_items} listing(s)",
            current=output.total_items,
            total=payload.max_items_per_source * len(payload.sources),
            unit="item",
        )
        return output

    return execute
