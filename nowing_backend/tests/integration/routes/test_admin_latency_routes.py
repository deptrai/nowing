"""Integration test T8.6: p50/p95 latency endpoint.

Seeds ``TokenUsage`` rows with known ``e2e_ms`` / ``resolved_mode`` values,
calls ``GET /admin/metrics/deep-research-latency?mode=balanced&p=0.95``, and
asserts the returned percentiles match the expected values.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import TokenUsage, User, get_async_session
from app.users import get_auth_context

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def admin_client(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    admin = User(
        id=uuid.uuid4(),
        email="admin@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(admin)
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(admin)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


async def _seed_usage(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    user_id: uuid.UUID,
    resolved_mode: str,
    e2e_ms: int,
    ttfb_ms: int | None = None,
) -> TokenUsage:
    usage = TokenUsage(
        workspace_id=workspace_id,
        user_id=user_id,
        usage_type="deep_research",
        call_details={
            "resolved_mode": resolved_mode,
            "mode_requested": resolved_mode,
            "e2e_ms": e2e_ms,
            "ttfb_ms": ttfb_ms,
        },
        resolved_mode=resolved_mode,
        mode_requested=resolved_mode,
        e2e_ms=e2e_ms,
        ttfb_ms=ttfb_ms,
        cost_micros=0,
    )
    db_session.add(usage)
    await db_session.flush()
    return usage


@pytest.mark.asyncio
async def test_p50_p95_endpoint_returns_expected_percentiles(
    admin_client, db_session, db_user, db_workspace
):
    """Seed 20 rows of balanced-mode e2e_ms [100..2000 step 100]; assert p50/p95."""
    # 20 rows: 100, 200, ..., 2000 -> p50 = 1050 (median of 20 = avg of 10th, 11th),
    # p95 ≈ 1905 (linear interpolation in percentile_cont).
    for i in range(1, 21):
        await _seed_usage(
            db_session,
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            resolved_mode="balanced",
            e2e_ms=i * 100,
            ttfb_ms=i * 10,
        )

    resp = await admin_client.get(
        "/api/v1/admin/metrics/deep-research-latency",
        params={"metric": "e2e", "mode": "balanced", "window_days": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric"] == "e2e"
    assert len(body["percentiles"]) == 1
    pct = body["percentiles"][0]
    assert pct["mode"] == "balanced"
    assert pct["samples"] == 20
    # percentile_cont(0.5) over [100..2000 step 100] = 1050.0
    assert pct["p50"] == pytest.approx(1050.0, abs=1.0)
    # percentile_cont(0.95) over the same set ≈ 1905.0
    assert pct["p95"] == pytest.approx(1905.0, abs=1.0)


@pytest.mark.asyncio
async def test_p50_p95_endpoint_rejects_invalid_mode(admin_client):
    """P3: invalid mode returns 400."""
    resp = await admin_client.get(
        "/api/v1/admin/metrics/deep-research-latency",
        params={"mode": "invalid_mode"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_p50_p95_endpoint_returns_both_percentiles(
    admin_client, db_session, db_user, db_workspace
):
    """P1 regression: both p50 and p95 must be returned (no overwrite)."""
    for i in range(1, 11):
        await _seed_usage(
            db_session,
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            resolved_mode="speed",
            e2e_ms=i * 100,
        )

    resp = await admin_client.get(
        "/api/v1/admin/metrics/deep-research-latency",
        params={"metric": "e2e", "mode": "speed", "p": 0.5},
    )
    assert resp.status_code == 200
    body = resp.json()
    pct = body["percentiles"][0]
    # p50 and p95 must differ — the old bug overwrote p95 with p50 when p=0.5.
    assert pct["p50"] != pct["p95"]
    assert pct["p50"] < pct["p95"]
