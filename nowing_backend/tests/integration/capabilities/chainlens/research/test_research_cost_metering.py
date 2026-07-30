"""Integration tests for chainlens.research cost metering (Story 9.2)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.capabilities.chainlens.research.schemas import ResearchOutput
from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import TokenUsage, User
from app.services.etl_credit_service import InsufficientCreditsError

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_charge_capability_records_deep_research_token_usage_with_actual_cost(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-2 P6: real cost_micros debits wallet and writes TokenUsage usage_type=deep_research."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    output = ResearchOutput.model_construct(
        status="complete",
        answer="A complete answer.",
        cost_micros=12_300,
        cost_basis="actual",
        resolved_mode="quality",
        tokens_total=1_280,
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert charged == 12_300
    assert db_user.credit_micros_balance == 1_000_000 - 12_300

    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == "deep_research",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    usage = rows[0]
    assert usage.cost_micros == 12_300
    assert usage.user_id == db_user.id
    assert usage.workspace_id == db_workspace.id
    assert usage.call_details["cost_basis"] == "actual"
    assert usage.call_details["resolved_mode"] == "quality"
    assert usage.call_details["tokens_total"] == 1_280


@pytest.mark.asyncio
async def test_charge_capability_fallback_to_flat_rate_when_no_actual_cost(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
    caplog,
):
    """AC-3 P6: missing cost_micros falls back to CHAINLENS_QUERY_MICROS_PER_CALL with warning."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "CHAINLENS_QUERY_MICROS_PER_CALL", 5_000)
    db_user.credit_micros_balance = 1_000_000

    output = ResearchOutput(
        status="complete",
        answer="A complete answer.",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert charged == 5_000
    assert db_user.credit_micros_balance == 1_000_000 - 5_000

    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == "deep_research",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    usage = rows[0]
    assert usage.cost_micros == 5_000
    assert usage.call_details["cost_basis"] == "fallback"
    assert any("fallback" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_charge_capability_records_usage_without_debit_when_billing_disabled(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-2 P6: billing disabled -> TokenUsage row exists, wallet unchanged."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", False)
    db_user.credit_micros_balance = 1_000_000

    output = ResearchOutput.model_construct(
        status="complete",
        answer="A complete answer.",
        cost_micros=12_300,
        cost_basis="actual",
        resolved_mode="quality",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert charged == 0
    assert db_user.credit_micros_balance == 1_000_000

    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == "deep_research",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].cost_micros == 12_300


@pytest.mark.asyncio
async def test_charge_capability_raises_when_actual_cost_exceeds_balance(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-2 P6: post-charge balance check fails before debit; row rolled back."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 10_000

    output = ResearchOutput.model_construct(
        status="complete",
        answer="A complete answer.",
        cost_micros=12_300,
        cost_basis="actual",
        resolved_mode="quality",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    with pytest.raises(InsufficientCreditsError):
        await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    assert db_user.credit_micros_balance == 10_000
    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
            )
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_aggregate_deep_research_cost_per_mode(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-4 P6: TokenUsage rows for deep_research can be aggregated by resolved_mode."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 10_000_000

    modes_and_costs = [
        ("balanced", 4_800),
        ("balanced", 5_200),
        ("quality", 10_500),
        ("deep", 16_400),
    ]
    for resolved_mode, cost in modes_and_costs:
        output = ResearchOutput.model_construct(
            status="complete",
            answer=f"Answer for {resolved_mode}.",
            cost_micros=cost,
            cost_basis="actual",
            resolved_mode=resolved_mode,
        )
        ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
        await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    mode_expr = TokenUsage.call_details["resolved_mode"].astext.label("mode")
    rows = (
        await db_session.execute(
            select(
                mode_expr,
                func.avg(TokenUsage.cost_micros).label("avg"),
                func.min(TokenUsage.cost_micros).label("min"),
                func.max(TokenUsage.cost_micros).label("max"),
            )
            .where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == "deep_research",
            )
            .group_by(mode_expr)
        )
    ).all()

    by_mode = {r.mode: r for r in rows}
    assert set(by_mode.keys()) == {"balanced", "quality", "deep"}
    assert by_mode["balanced"].avg == 5_000.0
    assert by_mode["balanced"].min == 4_800
    assert by_mode["balanced"].max == 5_200
    assert by_mode["quality"].avg == 10_500.0
    assert by_mode["deep"].avg == 16_400.0
