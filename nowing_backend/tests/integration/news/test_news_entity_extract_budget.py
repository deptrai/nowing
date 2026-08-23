"""Integration tests for the news entity extraction cost-control gate."""

from __future__ import annotations

import importlib
import inspect

import pytest
from sqlalchemy import select

from app.config import config
from app.db import TokenUsage, Workspace, WorkspaceLimit
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.workspace_limits import ResolvedWorkspaceLimits

pytestmark = [pytest.mark.integration]


def _call(fn, **kwargs):
    """Call ``fn`` with only the kwargs it accepts (tolerates ``**kwargs``)."""
    sig = inspect.signature(fn)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(**kwargs)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(**accepted)


async def test_news_entity_extraction_cost_control_gate(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """The gate reads workspace_limits and TokenUsage; record_* writes TokenUsage."""
    try:
        budget_mod = importlib.import_module("app.services.news.extract_budget")
    except ModuleNotFoundError as exc:
        pytest.fail(f"not implemented: {exc}")

    # RED guards: workspace_limits table must have the new columns.
    missing_cols = [
        col
        for col in (
            "news_entity_extraction_item_cap",
            "news_entity_extraction_spend_cap_micros",
            "news_entity_extraction_wallet_pre_check",
        )
        if col not in WorkspaceLimit.__table__.columns
    ]
    if missing_cols:
        pytest.fail(f"not implemented: workspace_limits missing columns {missing_cols}")

    # RED guards: ResolvedWorkspaceLimits must expose the new fields.
    missing_attrs = [
        attr
        for attr in (
            "news_entity_extraction_item_cap",
            "news_entity_extraction_spend_cap_micros",
            "news_entity_extraction_wallet_pre_check",
        )
        if not hasattr(ResolvedWorkspaceLimits, attr)
    ]
    if missing_attrs:
        pytest.fail(f"not implemented: ResolvedWorkspaceLimits missing {missing_attrs}")

    # RED guard: UsageType must know about entity extraction.
    if not hasattr(UsageType, "ENTITY_EXTRACTION"):
        pytest.fail("not implemented: UsageType.ENTITY_EXTRACTION missing")

    check_gate = getattr(budget_mod, "check_news_entity_extraction_allowed", None)
    record_extraction = getattr(budget_mod, "record_news_entity_extraction", None)
    if check_gate is None:
        pytest.fail("not implemented: check_news_entity_extraction_allowed missing")
    if record_extraction is None:
        pytest.fail("not implemented: record_news_entity_extraction missing")

    # Configure the global cost-control knobs.
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS", 0)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 10_000_000)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW", "day")
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_MAX", 0)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS", 3600)

    # Seed a workspace limit with a 1 USD spend cap and wallet pre-check off.
    limit = WorkspaceLimit(
        workspace_id=db_workspace.id,
        news_entity_extraction_item_cap=10,
        news_entity_extraction_spend_cap_micros=1_000_000,
        news_entity_extraction_wallet_pre_check=False,
    )
    db_session.add(limit)
    await db_session.flush()

    # With no entity-extraction TokenUsage, the gate should allow.
    result = await _call(
        check_gate,
        session=db_session,
        workspace=db_workspace,
        workspace_id=db_workspace.id,
        attributed_user_id=db_user.id,
        user_id=db_user.id,
    )
    assert result.allowed is True, f"expected allowed, got {result.reason}"

    # Seed a TokenUsage row that exceeds the 1 USD cap.
    entity_usage = UsageType.ENTITY_EXTRACTION
    await record_token_usage(
        db_session,
        usage_type=entity_usage,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        cost_micros=2_000_000,
        total_tokens=100,
    )
    await db_session.flush()

    # The gate should now block on budget.
    result = await _call(
        check_gate,
        session=db_session,
        workspace=db_workspace,
        workspace_id=db_workspace.id,
        attributed_user_id=db_user.id,
        user_id=db_user.id,
    )
    assert result.allowed is False
    assert result.reason == "budget_exceeded"

    # DB state: the TokenUsage row is read back.
    result = await db_session.execute(
        select(TokenUsage).where(
            TokenUsage.workspace_id == db_workspace.id,
            TokenUsage.usage_type == entity_usage,
        )
    )
    usage_rows = result.scalars().all()
    assert len(usage_rows) == 1
    assert usage_rows[0].cost_micros == 2_000_000
    assert usage_rows[0].total_tokens == 100

    # DB state: the workspace limit override is read back.
    result = await db_session.execute(
        select(WorkspaceLimit).where(WorkspaceLimit.workspace_id == db_workspace.id)
    )
    limit_row = result.scalar_one()
    assert limit_row.news_entity_extraction_spend_cap_micros == 1_000_000
    assert limit_row.news_entity_extraction_item_cap == 10
    assert limit_row.news_entity_extraction_wallet_pre_check is False

    # record_news_entity_extraction should write a new TokenUsage row.
    workspace2 = Workspace(name="News Budget Test 2", user_id=db_user.id)
    db_session.add(workspace2)
    await db_session.flush()
    limit2 = WorkspaceLimit(
        workspace_id=workspace2.id,
        news_entity_extraction_item_cap=1,
        news_entity_extraction_spend_cap_micros=10_000_000,
        news_entity_extraction_wallet_pre_check=False,
    )
    db_session.add(limit2)
    await db_session.flush()

    await _call(
        record_extraction,
        session=db_session,
        workspace=workspace2,
        workspace_id=workspace2.id,
        attributed_user_id=db_user.id,
        user_id=db_user.id,
        cost_micros=500_000,
        total_tokens=50,
    )
    await db_session.flush()

    result = await db_session.execute(
        select(TokenUsage).where(
            TokenUsage.workspace_id == workspace2.id,
            TokenUsage.usage_type == entity_usage,
        )
    )
    rows2 = result.scalars().all()
    assert len(rows2) == 1
    assert rows2[0].cost_micros == 500_000
    assert rows2[0].total_tokens == 50
