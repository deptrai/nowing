"""Integration tests for ``vn_bds.aggregate`` billing and provenance."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.capabilities.vn_bds.aggregate.executor import build_aggregate_executor
from app.capabilities.vn_bds.aggregate.schemas import VnBdsAggregateInput
from app.config import config
from app.db import TokenUsage
from app.services.bds_aggregator.schemas import (
    VnBdsAggregatedListing,
    VnBdsAggregateOutput,
    VnBdsProvenance,
)

pytestmark = [pytest.mark.integration]


def _fake_aggregate_output(
    items: list[VnBdsAggregatedListing] | None = None,
    cost: int = 0,
) -> VnBdsAggregateOutput:
    return VnBdsAggregateOutput(
        items=items or [],
        cost_micros=cost,
        source_breakdown={
            "batdongsan": {"items": 1, "cost_micros": 3500, "degraded": False},
            "chotot_bds": {"items": 1, "cost_micros": 3500, "degraded": False},
            "muaban_bds": {
                "items": 0,
                "cost_micros": 0,
                "degraded": True,
                "degradation_reason": "rate_limited",
            },
        },
    )


@pytest.mark.asyncio
async def test_gate_reserves_child_and_aggregate_worst_case(
    db_session, db_workspace, db_user, monkeypatch
):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3500)
    monkeypatch.setattr(config, "CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM", 3500)
    monkeypatch.setattr(config, "MUABAN_BDS_SCRAPE_MICROS_PER_ITEM", 5500)
    monkeypatch.setattr(config, "VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY", 5000)
    db_user.credit_micros_balance = 1_000_000

    payload = VnBdsAggregateInput(city="Hà Nội", max_items_per_source=10)
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    # Should not raise; 10*3 items + 5000 = 105_000 + 5_000 under 1_000_000.
    await gate_capability(payload, BillingUnit.VN_BDS_AGGREGATE_QUERY, ctx)

    # Sanity: balance not yet changed.
    assert db_user.credit_micros_balance == 1_000_000


@pytest.mark.asyncio
async def test_charge_aggregate_bills_output_cost(
    db_session, db_workspace, db_user, monkeypatch
):
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    output = _fake_aggregate_output(
        items=[
            VnBdsAggregatedListing(
                canonical_id="abc",
                source_ids={"batdongsan": 1, "chotot_bds": 2},
                sources=["batdongsan", "chotot_bds"],
                source_count=2,
                confidence_score=0.9,
            )
        ],
        cost=12_000,
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.VN_BDS_AGGREGATE_QUERY, ctx)

    assert charged == 12_000
    assert db_user.credit_micros_balance == 1_000_000 - 12_000

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "vn_bds_aggregate_query",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].cost_micros == 12_000
    assert rows[0].user_id == db_user.id


@pytest.mark.asyncio
async def test_executor_provenance_in_listing():
    async def fake_aggregate(payload: VnBdsAggregateInput) -> VnBdsAggregateOutput:
        listing = VnBdsAggregatedListing(
            canonical_id="abc",
            source_ids={"batdongsan": 1},
            sources=["batdongsan"],
            source_count=1,
            confidence_score=0.5,
            provenance=VnBdsProvenance(
                source_input=payload.model_dump(exclude_unset=True)
            ),
        )
        return VnBdsAggregateOutput(items=[listing])

    execute = build_aggregate_executor(aggregate_fn=fake_aggregate)
    output = await execute(VnBdsAggregateInput(city="Hà Nội"))

    assert output.total_items == 1
    assert output.items[0].provenance.source_capability == "vn_bds.aggregate"
    assert output.items[0].provenance.source_input is not None
    assert output.items[0].provenance.source_input["city"] == "Hà Nội"
