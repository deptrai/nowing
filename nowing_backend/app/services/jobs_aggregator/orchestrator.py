"""``jobs_aggregator`` orchestrator: fan-out, normalize, deduplicate, score."""

from __future__ import annotations

from typing import Any

from app.capabilities.core import CapabilityContext
from app.capabilities.core.store import get_capability

from .schemas import VnJobAggregateInput, VnJobAggregateOutput


async def aggregate_jobs(input: VnJobAggregateInput, ctx: CapabilityContext) -> VnJobAggregateOutput:
    """Run the multi-source job aggregation pipeline.

    This is a skeleton implementation for Epic 12. The actual source fetchers,
    normalizers, deduplication, and PII redaction will be wired in after the
    ToS/legal/anti-bot hard gates are resolved.
    """
    output = VnJobAggregateOutput()
    output.source_breakdown = {source: {"total": 0, "degraded": False} for source in input.sources}

    for source in input.sources:
        cap = get_capability(f"{source}.scrape")
        if cap is None:
            output.degraded = True
            output.degradation_reasons.append(f"{source}: capability_not_found")
            continue

        # Skeleton: emit a placeholder degraded result for every source until
        # the scrapers are implemented.
        output.degraded = True
        output.degradation_reasons.append(f"{source}: not_implemented")

    return output


def build_aggregate_executor() -> Any:
    """Factory matching the capability executor pattern."""

    async def execute(input: VnJobAggregateInput, ctx: CapabilityContext) -> VnJobAggregateOutput:
        return await aggregate_jobs(input, ctx)

    return execute
