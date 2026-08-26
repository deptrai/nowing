"""Integration tests for /api/v1/admin/telemetry/* (Story 25.4)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_admin_telemetry_llm_cost_shape(admin_client: AsyncClient) -> None:
    """AC-1: GET /llm-cost returns the expected breakdown shape."""
    res = await admin_client.get("/api/v1/admin/telemetry/llm-cost?window_hours=24")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["window_hours"] == 24
    assert "by_provider" in data
    assert "by_model" in data
    assert "by_workspace" in data
    assert "by_usage_type" in data
    assert "time_series" in data
    assert "non_llm_cost_micros" in data
    assert "billing_cost_micros" in data
    assert data["unreported_cost_rows"] >= 0


@pytest.mark.asyncio
async def test_admin_telemetry_gross_margin_shape(admin_client: AsyncClient) -> None:
    """AC-1: GET /gross-margin handles empty revenue and returns shape."""
    res = await admin_client.get("/api/v1/admin/telemetry/gross-margin?window_hours=1")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["window_hours"] == 1
    assert "overall_gross_margin" in data
    assert "worst_workspace_id" in data
    assert "worst_workspace_margin" in data
    assert "worst_model" in data
    assert "non_llm_cost_micros" in data
    assert "billing_cost_micros" in data
    assert "points" in data


@pytest.mark.asyncio
async def test_admin_telemetry_proxy_health_shape(admin_client: AsyncClient) -> None:
    """AC-2: GET /proxy-health returns a status even when not configured."""
    res = await admin_client.get("/api/v1/admin/telemetry/proxy-health")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "status" in data
    assert "provider" in data
    assert "snapshots" in data


@pytest.mark.asyncio
async def test_admin_telemetry_celery_queues_shape(admin_client: AsyncClient) -> None:
    """AC-3: GET /celery-queues returns queue telemetry (status unavailable is OK)."""
    res = await admin_client.get("/api/v1/admin/telemetry/celery-queues")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "status" in data
    assert "queues" in data
    assert "active_workers" in data


@pytest.mark.asyncio
async def test_admin_telemetry_endpoints_require_superuser(
    client_as_regular_user: AsyncClient,
) -> None:
    """AC-4: non-superuser gets 403 on all telemetry endpoints."""
    for path in [
        "/api/v1/admin/telemetry/llm-cost",
        "/api/v1/admin/telemetry/gross-margin",
        "/api/v1/admin/telemetry/proxy-health",
        "/api/v1/admin/telemetry/celery-queues",
    ]:
        res = await client_as_regular_user.get(path)
        assert res.status_code == 403, f"{path}: {res.text}"

    res = await client_as_regular_user.post(
        "/api/v1/admin/telemetry/celery-queues/celery/purge"
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_admin_telemetry_purge_rejects_unknown_queue(
    admin_client: AsyncClient,
) -> None:
    """AC-3: purge on an unknown queue returns 400."""
    res = await admin_client.post(
        "/api/v1/admin/telemetry/celery-queues/unknown-queue/purge"
    )
    assert res.status_code == 400, res.text
