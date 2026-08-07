"""Integration tests for Usage & Credit Dashboard (Story 8.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytestmark = [pytest.mark.integration]

BASE = "/api/v1/usage"


@pytest.mark.asyncio
async def test_usage_summary_returns_balance_and_totals(
    client,
    db_user,
    db_workspace,
    seed_token_usage,
):
    """GET /usage/summary returns current balance, reserved, totals and breakdowns."""
    now = datetime.now(UTC)
    start = now - timedelta(days=7)
    end = now + timedelta(hours=1)

    db_user.credit_micros_balance = 5_500_000
    db_user.credit_micros_reserved = 200_000

    await seed_token_usage(
        usage_type="chat",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_micros=1500,
        created_at=now - timedelta(days=1),
    )
    await seed_token_usage(
        usage_type="image_generation",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_micros=500,
        model_breakdown={
            "openai/dall-e-3": {
                "model": "openai/dall-e-3",
                "model_ref": "openai/dall-e-3",
                "model_id": "dall-e-3",
                "display_name": "DALL-E 3",
                "provider": "openai",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_micros": 500,
            }
        },
        created_at=now - timedelta(days=1),
    )

    resp = await client.get(
        f"{BASE}/summary",
        params={
            "workspace_id": db_workspace.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_balance_micros"] == 5_500_000
    assert body["reserved_micros"] == 200_000
    assert body["total_tokens"] == 30
    assert body["total_cost_micros"] == 2000

    by_usage_type = {item["key"]: item for item in body["by_usage_type"]}
    assert by_usage_type["chat"]["total_tokens"] == 30
    assert by_usage_type["chat"]["cost_micros"] == 1500
    assert by_usage_type["image_generation"]["cost_micros"] == 500

    by_model = {item["key"]: item for item in body["by_model"]}
    assert by_model["openai/gpt-4"]["total_tokens"] == 30
    assert by_model["openai/gpt-4"]["cost_micros"] == 1500

    by_provider = {item["key"]: item for item in body["by_provider"]}
    assert by_provider["openai"]["total_tokens"] == 30
    assert by_provider["openai"]["cost_micros"] == 2000


@pytest.mark.asyncio
async def test_usage_summary_filters_by_date_range(
    client,
    db_workspace,
    seed_token_usage,
):
    """Summary only aggregates TokenUsage rows within the requested date range."""
    now = datetime.now(UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=100,
        cost_micros=5000,
        created_at=now - timedelta(days=60),
    )
    await seed_token_usage(
        usage_type="chat",
        total_tokens=25,
        cost_micros=1000,
        created_at=now - timedelta(days=5),
    )

    start = (now - timedelta(days=30)).isoformat()
    end = (now + timedelta(hours=1)).isoformat()

    resp = await client.get(
        f"{BASE}/summary",
        params={
            "workspace_id": db_workspace.id,
            "start_date": start,
            "end_date": end,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 25
    assert body["total_cost_micros"] == 1000


@pytest.mark.asyncio
async def test_usage_summary_rejects_missing_workspace_id(client):
    """workspace_id query param is required."""
    resp = await client.get(f"{BASE}/summary")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_usage_summary_rejects_invalid_date_range(client, db_workspace):
    """start_date must not be after end_date."""
    now = datetime.now(UTC)
    start = now + timedelta(days=1)
    end = now - timedelta(days=1)

    resp = await client.get(
        f"{BASE}/summary",
        params={
            "workspace_id": db_workspace.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_non_member_cannot_access_summary(client_as_other, db_workspace):
    """A user without workspace membership is denied."""
    resp = await client_as_other.get(
        f"{BASE}/summary",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_time_series_returns_daily_points(
    client,
    db_workspace,
    seed_token_usage,
):
    """GET /usage/time-series returns cost/tokens grouped by day."""
    now = datetime.now(UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=10,
        cost_micros=100,
        created_at=now - timedelta(days=2),
    )
    await seed_token_usage(
        usage_type="chat",
        total_tokens=20,
        cost_micros=200,
        created_at=now - timedelta(days=1),
    )

    start = (now - timedelta(days=7)).isoformat()
    end = (now + timedelta(hours=1)).isoformat()

    resp = await client.get(
        f"{BASE}/time-series",
        params={
            "workspace_id": db_workspace.id,
            "granularity": "day",
            "start_date": start,
            "end_date": end,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["granularity"] == "day"
    assert isinstance(body["points"], list)

    # Points for the two seeded days should exist and total to seeded values.
    totals = {p["period"]: p for p in body["points"]}
    assert any(
        point["total_tokens"] == 10 and point["cost_micros"] == 100
        for point in totals.values()
    )
    assert any(
        point["total_tokens"] == 20 and point["cost_micros"] == 200
        for point in totals.values()
    )


@pytest.mark.asyncio
async def test_usage_time_series_rejects_unknown_granularity(
    client,
    db_workspace,
):
    """Granularity must be one of day, week, month."""
    resp = await client.get(
        f"{BASE}/time-series",
        params={
            "workspace_id": db_workspace.id,
            "granularity": "hour",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_usage_transactions_returns_purchases_and_incentives(
    client,
    db_user,
    seed_credit_purchase,
    seed_incentive_task,
):
    """GET /usage/transactions returns unified credit purchase and incentive history."""
    await seed_credit_purchase(
        quantity=5,
        credit_micros_granted=5_000_000,
    )
    await seed_incentive_task(
        task_type="GITHUB_STAR",
        credit_micros_awarded=1_000_000,
    )

    resp = await client.get(f"{BASE}/transactions")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["transactions"], list)

    types = {t["type"] for t in body["transactions"]}
    assert "credit_purchase" in types
    assert "incentive" in types

    # Transactions should be sorted by created_at desc.
    timestamps = [t["created_at"] for t in body["transactions"]]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_usage_transactions_includes_page_purchases(
    client,
    db_user,
    seed_page_purchase,
):
    """GET /usage/transactions includes legacy PagePurchase entries as micros."""
    await seed_page_purchase(
        pages_granted=100,
        amount_total=1000,  # cents -> $10.00 -> 10_000_000 micros
    )

    resp = await client.get(f"{BASE}/transactions")

    assert resp.status_code == 200
    body = resp.json()
    page_purchases = [t for t in body["transactions"] if t["type"] == "page_purchase"]
    assert len(page_purchases) == 1
    assert page_purchases[0]["amount_micros"] == 10_000_000


@pytest.mark.asyncio
async def test_non_member_cannot_access_time_series(client_as_other, db_workspace):
    """A user without workspace membership is denied for /time-series."""
    resp = await client_as_other.get(
        f"{BASE}/time-series",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_routes_reject_pat(client_as_pat, db_workspace):
    """PAT-authenticated requests are rejected because endpoints require a session."""
    resp = await client_as_pat.get(
        f"{BASE}/summary",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 403

    resp = await client_as_pat.get(f"{BASE}/transactions")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_usage_summary_empty_workspace(client, db_workspace):
    """Summary returns zeros and empty breakdowns when no usage exists."""
    resp = await client.get(
        f"{BASE}/summary",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 0
    assert body["total_cost_micros"] == 0
    assert body["by_usage_type"] == []
    assert body["by_model"] == []
    assert body["by_provider"] == []


@pytest.mark.asyncio
async def test_usage_time_series_empty_workspace(client, db_workspace):
    """Time-series returns an empty points list when no usage exists."""
    resp = await client.get(
        f"{BASE}/time-series",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["granularity"] == "day"
    assert body["points"] == []


@pytest.mark.asyncio
async def test_usage_transactions_empty(client):
    """Transactions returns an empty list with total 0 when no history exists."""
    resp = await client.get(f"{BASE}/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["transactions"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_usage_summary_model_breakdown_null_and_empty(
    client,
    db_workspace,
    seed_token_usage,
):
    """Null or empty model_breakdown does not crash breakdown queries."""
    now = datetime.now(UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=10,
        cost_micros=1000,
        model_breakdown=None,
        created_at=now - timedelta(days=1),
    )
    await seed_token_usage(
        usage_type="image_generation",
        total_tokens=5,
        cost_micros=500,
        model_breakdown={},
        created_at=now - timedelta(days=1),
    )

    resp = await client.get(
        f"{BASE}/summary",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 15
    assert body["total_cost_micros"] == 1500
    assert body["by_model"] == []
    assert body["by_provider"] == []


@pytest.mark.asyncio
async def test_usage_summary_model_breakdown_malformed(
    client,
    db_workspace,
    seed_token_usage,
):
    """Malformed model_breakdown values are treated as 0 instead of crashing."""
    now = datetime.now(UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=1,
        cost_micros=100,
        model_breakdown={
            "custom-model": {
                "provider": "openai",
                "total_tokens": "not-a-number",
                "cost_micros": "also-bad",
            }
        },
        created_at=now - timedelta(days=1),
    )

    resp = await client.get(
        f"{BASE}/summary",
        params={"workspace_id": db_workspace.id},
    )
    assert resp.status_code == 200
    body = resp.json()

    by_model = {item["key"]: item for item in body["by_model"]}
    assert by_model["custom-model"]["total_tokens"] == 0
    assert by_model["custom-model"]["cost_micros"] == 0

    by_provider = {item["key"]: item for item in body["by_provider"]}
    assert by_provider["openai"]["total_tokens"] == 0
    assert by_provider["openai"]["cost_micros"] == 0


@pytest.mark.asyncio
async def test_usage_time_series_week_calendar_format(
    client,
    db_workspace,
    seed_token_usage,
):
    """Week granularity uses calendar week (YYYY-WW), not ISO week."""
    # 2023-12-31 is a Sunday: calendar week 2023-53, ISO week 2023-52.
    start = datetime(2023, 12, 31, 12, tzinfo=UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=100,
        cost_micros=1000,
        created_at=start,
    )

    resp = await client.get(
        f"{BASE}/time-series",
        params={
            "workspace_id": db_workspace.id,
            "granularity": "week",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["granularity"] == "week"
    assert len(body["points"]) == 1
    assert body["points"][0]["period"] == "2023-53"


@pytest.mark.asyncio
async def test_usage_time_series_month(
    client,
    db_workspace,
    seed_token_usage,
):
    """Month granularity groups usage by YYYY-MM."""
    start = datetime(2024, 1, 15, 12, tzinfo=UTC)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=50,
        cost_micros=500,
        created_at=start,
    )
    await seed_token_usage(
        usage_type="chat",
        total_tokens=25,
        cost_micros=250,
        created_at=start + timedelta(days=5),
    )

    resp = await client.get(
        f"{BASE}/time-series",
        params={
            "workspace_id": db_workspace.id,
            "granularity": "month",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=10)).isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["granularity"] == "month"
    assert len(body["points"]) == 1
    assert body["points"][0]["period"] == "2024-01"
    assert body["points"][0]["total_tokens"] == 75
    assert body["points"][0]["cost_micros"] == 750


@pytest.mark.asyncio
async def test_usage_summary_start_equals_end(client, db_workspace, seed_token_usage):
    """A one-day range is valid and returns data for that day."""
    now = datetime.now(UTC)
    day = now - timedelta(days=2)

    await seed_token_usage(
        usage_type="chat",
        total_tokens=10,
        cost_micros=100,
        created_at=day,
    )

    resp = await client.get(
        f"{BASE}/summary",
        params={
            "workspace_id": db_workspace.id,
            "start_date": day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "end_date": day.replace(hour=23, minute=59, second=59, microsecond=0).isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 10
    assert body["total_cost_micros"] == 100


@pytest.mark.asyncio
async def test_usage_summary_future_dates(client, db_workspace):
    """Future date ranges return empty usage without error."""
    now = datetime.now(UTC)
    start = now + timedelta(days=10)
    end = now + timedelta(days=20)

    resp = await client.get(
        f"{BASE}/summary",
        params={
            "workspace_id": db_workspace.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 0
    assert body["total_cost_micros"] == 0


@pytest.mark.asyncio
async def test_usage_summary_workspace_id_zero(client):
    """workspace_id must be >= 1."""
    resp = await client.get(f"{BASE}/summary", params={"workspace_id": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_usage_transactions_pagination(
    client,
    db_user,
    seed_credit_purchase,
    seed_incentive_task,
):
    """Pagination returns the requested slice and correct total."""
    for i in range(3):
        await seed_credit_purchase(
            quantity=1,
            credit_micros_granted=1_000_000,
            created_at=datetime.now(UTC) - timedelta(hours=i),
        )

    resp = await client.get(f"{BASE}/transactions", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["transactions"]) == 2
    assert body["total"] == 3

    resp = await client.get(f"{BASE}/transactions", params={"limit": 2, "offset": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert body["transactions"] == []
    assert body["total"] == 3
