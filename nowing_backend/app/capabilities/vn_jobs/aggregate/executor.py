"""``vn_jobs.aggregate`` executor."""

from __future__ import annotations

from typing import Any

from app.capabilities.core import Executor
from app.services.jobs_aggregator import aggregate_jobs

from .schemas import VnJobAggregateInput, VnJobAggregateOutput


def build_aggregate_executor() -> Executor:
    """Return an executor for the multi-source job aggregator."""

    async def execute(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
        return await aggregate_jobs(input, ctx)

    return execute
