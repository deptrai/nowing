"""Integration tests for chainlens gap-fill cost allocation (Story 20.2 AC-3)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.capabilities.chainlens.research.schemas import ResearchOutput
from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import TokenUsage
from app.services.token_tracking_service import UsageType

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_charge_capability_records_gap_fill_cost_allocation(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-3: one total debit, three TokenUsage rows (search/gap-fill/scraper)."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    output = ResearchOutput.model_construct(
        status="insufficient_evidence",
        answer="",
        gap_fill_needed=True,
        suggested_domains=["batdongsan"],
        cost_micros=100_000,
        cost_basis="actual",
        resolved_mode="balanced",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert charged == 100_000
    assert db_user.credit_micros_balance == 1_000_000 - 100_000

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type.in_(
                        [
                            UsageType.DEEP_RESEARCH,
                            UsageType.CHAINLENS_GAP_FILL,
                            UsageType.CHAINLENS_INGEST,
                        ]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    by_type = {r.usage_type: r for r in rows}
    assert set(by_type.keys()) == {
        UsageType.DEEP_RESEARCH,
        UsageType.CHAINLENS_GAP_FILL,
        UsageType.CHAINLENS_INGEST,
    }
    assert by_type[UsageType.DEEP_RESEARCH].cost_micros == 50_000
    assert by_type[UsageType.CHAINLENS_GAP_FILL].cost_micros == 30_000
    assert by_type[UsageType.CHAINLENS_INGEST].cost_micros == 20_000

    # Verify the total is exactly the single debit.
    total_recorded = (
        await db_session.execute(
            select(func.sum(TokenUsage.cost_micros)).where(
                TokenUsage.workspace_id == db_workspace.id
            )
        )
    ).scalar() or 0
    assert total_recorded == 100_000


@pytest.mark.asyncio
async def test_charge_capability_uses_exact_cost_breakdown(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-3: when the engine returns per-operation costs, record them exactly."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    output = ResearchOutput.model_construct(
        status="insufficient_evidence",
        answer="",
        gap_fill_needed=True,
        suggested_domains=["batdongsan"],
        cost_micros=60_000,
        cost_basis="actual",
        resolved_mode="balanced",
        cost_breakdown={
            "search_micros": 20_000,
            "gap_fill_micros": 25_000,
            "scraper_micros": 15_000,
            "scraper_id": "batdongsan",
        },
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert charged == 60_000

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                )
            )
        )
        .scalars()
        .all()
    )
    by_type = {r.usage_type: r for r in rows}
    assert by_type[UsageType.DEEP_RESEARCH].cost_micros == 20_000
    assert by_type[UsageType.CHAINLENS_GAP_FILL].cost_micros == 25_000
    assert by_type[UsageType.CHAINLENS_INGEST].cost_micros == 15_000
    assert (
        by_type[UsageType.CHAINLENS_INGEST].call_details["scraper_id"] == "batdongsan"
    )
