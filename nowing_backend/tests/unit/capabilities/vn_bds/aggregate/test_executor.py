"""Unit tests for the ``vn_bds.aggregate`` executor."""

from __future__ import annotations

from typing import Any

import pytest

from app.capabilities.vn_bds.aggregate.executor import build_aggregate_executor
from app.capabilities.vn_bds.aggregate.schemas import (
    VnBdsAggregateInput,
    VnBdsAggregateOutput,
)
from app.services.bds_aggregator.schemas import VnBdsAggregatedListing

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_executor_calls_aggregator_and_returns_output():
    async def fake_aggregate(payload: VnBdsAggregateInput) -> VnBdsAggregateOutput:
        return VnBdsAggregateOutput(
            items=[
                VnBdsAggregatedListing(
                    canonical_id="abc",
                    source_ids={"batdongsan": 1},
                    sources=["batdongsan"],
                    source_count=1,
                    confidence_score=0.9,
                )
            ],
            cost_micros=5000,
            degraded=False,
        )

    execute = build_aggregate_executor(aggregate_fn=fake_aggregate)
    output = await execute(VnBdsAggregateInput(city="Hà Nội"))

    assert output.total_items == 1
    assert output.items[0].confidence_score == 0.9
    assert output.degraded is False


@pytest.mark.asyncio
async def test_executor_catches_exceptions_as_degraded():
    async def exploding_aggregate(_: Any) -> VnBdsAggregateOutput:
        raise RuntimeError("boom")

    execute = build_aggregate_executor(aggregate_fn=exploding_aggregate)
    output = await execute(VnBdsAggregateInput(city="Hà Nội"))

    assert output.degraded is True
    assert output.degradation_reasons == ["api_error"]
    assert output.total_items == 0


def test_input_rejects_duplicate_sources():
    with pytest.raises(ValueError, match="unique"):
        VnBdsAggregateInput(sources=["batdongsan", "batdongsan"], city="Hà Nội")
