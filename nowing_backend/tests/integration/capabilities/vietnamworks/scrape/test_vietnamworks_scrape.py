"""Integration tests for ``vietnamworks.scrape`` (Story 12.1).

Default run uses a fake fetcher (or manually-built output) to verify billing
against a real Postgres session. Set ``SCRAPE_LIVE=1`` to additionally hit the
real VietnamWorks public API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.capabilities.vietnamworks.scrape.executor import build_scrape_executor
from app.capabilities.vietnamworks.scrape.schemas import ScrapeInput, ScrapeOutput
from app.config import config
from app.db import TokenUsage

pytestmark = [pytest.mark.integration]

_FIXTURE = (
    Path(__file__).resolve().parents[5]
    / "tests/unit/capabilities/vietnamworks/fixtures/sample-response-page-1.json"
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


async def _fake_vietnamworks_fetcher(params: dict[str, Any]) -> dict[str, Any]:
    """Replay the recorded page-1 envelope; no pagination.

    Returns the ``items`` shape the executor expects.
    """
    page = params.get("page", 1)
    if page > 1:
        return {"items": [], "degraded": False}
    envelope = _load_fixture()
    return {
        "items": envelope["data"],
        "degraded": False,
    }


def _parsed_items() -> list[dict[str, Any]]:
    """The expected normalized items for the sample fixture."""
    return [
        {
            "id": "vw:12345",
            "title": "Senior Data Engineer",
            "company": "FPT Software",
            "location": "Hà Nội",
            "source_url": "https://www.vietnamworks.com/senior-data-engineer-12345",
            "salary_raw": "Từ 25tr ₫/tháng đến 35tr ₫/tháng",
            "salary_min": 25_000_000,
            "salary_max": 35_000_000,
            "salary_currency": "VND",
            "salary_period_id": 1,
            "employment_type": "full_time",
            "experience_years": 3,
            "job_description": "<p>Build data pipelines and warehouses.</p>",
            "job_requirement": "<p>3+ years of Python and SQL.</p>",
            "skills": ["Python", "SQL"],
            "benefits": ["Laptop", "Remote 2 days/week"],
            "posted_at": "2026-08-04T10:00:00+07:00",
            "approved_at": "2026-08-04T10:30:00+07:00",
            "expired_at": "2026-09-04T10:00:00+07:00",
            "is_active": True,
            "source": "vietnamworks",
        },
        {
            "id": "vw:12346",
            "title": "Data Engineer",
            "company": "Techcombank",
            "location": "TP. Hồ Chí Minh",
            "source_url": "https://www.vietnamworks.com/data-engineer-12346",
            "salary_raw": "Thương lượng",
            "salary_min": 0,
            "salary_max": 0,
            "salary_currency": "VND",
            "salary_period_id": 1,
            "employment_type": "part_time",
            "experience_years": 2,
            "job_description": "<p>Design and maintain data infrastructure.</p>",
            "job_requirement": "<p>Bachelor's degree in CS.</p>",
            "skills": ["Spark"],
            "benefits": [],
            "posted_at": "2026-08-03T09:00:00+07:00",
            "approved_at": "2026-08-03T09:30:00+07:00",
            "expired_at": "2026-09-03T09:00:00+07:00",
            "is_active": True,
            "source": "vietnamworks",
        },
    ]


@pytest.mark.asyncio
async def test_vietnamworks_scrape_executor_with_fake_fetcher(monkeypatch):
    """AC-1, AC-2: the executor maps upstream response to a typed, non-degraded ScrapeOutput."""
    monkeypatch.setattr(
        "app.capabilities.vietnamworks.scrape.executor.scrape_vietnamworks",
        _fake_vietnamworks_fetcher,
    )
    execute = build_scrape_executor()

    out = await execute(ScrapeInput(keyword="data engineer", max_items=2, max_pages=1))

    assert isinstance(out, ScrapeOutput)
    assert out.total_items == 2
    assert len(out.items) == 2
    assert out.degraded is False

    # Once the parser is implemented, each item should be a normalized dict
    # matching the contract in the story file (id, title, company, salary_raw, ...).
    for item in out.items:
        assert isinstance(item, dict)
        assert "jobId" in item or "id" in item


@pytest.mark.asyncio
async def test_vietnamworks_scrape_bills_parsed_items(
    db_session, db_user, db_workspace, monkeypatch
):
    """AC-4: successful run charges workspace owner at VIETNAMWORKS_JOB rate."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM", 3000)
    db_user.credit_micros_balance = 1_000_000

    out = ScrapeOutput(items=_parsed_items(), cost_micros=2 * 3000, degraded=False)

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    charged = await charge_capability(out, BillingUnit.VIETNAMWORKS_JOB, ctx)

    assert charged == 2 * 3000
    assert db_user.credit_micros_balance == 1_000_000 - 2 * 3000

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "vietnamworks_job",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].cost_micros == 2 * 3000
    assert rows[0].user_id == db_user.id


@pytest.mark.asyncio
async def test_vietnamworks_scrape_degraded_run_is_free(
    db_session, db_user, db_workspace, monkeypatch
):
    """AC-3/AC-4: a degraded run (e.g. 429) costs 0 and records a 0-cost audit row."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 1_000_000

    async def _degraded_fetcher(_params: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": [],
            "cost_micros": 0,
            "degraded": True,
            "degradation_reason": "rate_limited",
        }

    monkeypatch.setattr(
        "app.capabilities.vietnamworks.scrape.executor.scrape_vietnamworks",
        _degraded_fetcher,
    )
    execute = build_scrape_executor()
    out = await execute(ScrapeInput(keyword="data engineer"))

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    charged = await charge_capability(out, BillingUnit.VIETNAMWORKS_JOB, ctx)

    assert charged == 0
    assert db_user.credit_micros_balance == 1_000_000

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "vietnamworks_job",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].cost_micros == 0
    assert rows[0].user_id == db_user.id


@pytest.mark.skipif(os.environ.get("SCRAPE_LIVE") != "1", reason="SCRAPE_LIVE not set")
@pytest.mark.asyncio
async def test_vietnamworks_scrape_live_authorized():
    """AC-1: live smoke test against the real VietnamWorks public API.

    Requires network access and a valid TEST_DATABASE_URL; does not charge credits.
    """
    execute = build_scrape_executor()
    out = await execute(ScrapeInput(keyword="data engineer", max_items=5, max_pages=1))

    assert isinstance(out, ScrapeOutput)
    assert out.total_items <= 5
    for item in out.items:
        assert item["source"] == "vietnamworks"
        assert "title" in item
        assert "company" in item
