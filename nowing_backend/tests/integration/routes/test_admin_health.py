"""Integration tests for /api/v1/admin/telemetry/health/* (Story 25.7)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.admin_health import AdminHealthAlert, AdminHealthHistory
from app.services.health.probe_base import HealthResult

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_admin_health_overview_shape(admin_client: AsyncClient) -> None:
    """GET /health/overview returns aggregated overview."""
    res = await admin_client.get("/api/v1/admin/telemetry/health/overview")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "overall_status" in data
    assert "total_monitored" in data
    assert "status_counts" in data
    assert "categories" in data
    assert "registered_categories" in data


@pytest.mark.asyncio
async def test_admin_health_categories_list(admin_client: AsyncClient) -> None:
    """GET /health/categories returns registered health probe categories."""
    res = await admin_client.get("/api/v1/admin/telemetry/health/categories")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 0
    for item in data["items"]:
        assert "key" in item
        assert "label" in item
        assert "default_interval_seconds" in item
        assert "probe_count" in item


@pytest.mark.asyncio
async def test_admin_health_statuses_list(admin_client: AsyncClient) -> None:
    """GET /health/statuses returns service status list."""
    res = await admin_client.get("/api/v1/admin/telemetry/health/statuses")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_admin_health_alerts_list(admin_client: AsyncClient) -> None:
    """GET /health/alerts returns active alerts list."""
    res = await admin_client.get("/api/v1/admin/telemetry/health/alerts")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_acknowledge_alert_success(admin_client: AsyncClient) -> None:
    """POST /health/alerts/{alert_id}/acknowledge successfully acknowledges an alert."""
    mock_alert = AdminHealthAlert(
        id=99,
        service_id="scraper/tiktok",
        status="acknowledged",
        severity="high",
        message="TikTok scraper failing",
        triggered_at=datetime.now(UTC),
        acknowledged_until=datetime.now(UTC),
    )
    with patch("app.services.health.ThirdPartyHealthService.acknowledge_alert", new_callable=AsyncMock) as mock_ack:
        mock_ack.return_value = mock_alert
        res = await admin_client.post(
            "/api/v1/admin/telemetry/health/alerts/99/acknowledge",
            json={"duration_minutes": 30},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["id"] == 99
        assert data["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_history_endpoint_success(admin_client: AsyncClient) -> None:
    """GET /health/history/{service_id} returns history records."""
    mock_histories = [
        AdminHealthHistory(
            id=1,
            service_id="infra/postgres",
            status="healthy",
            latency_ms=15,
            probe_at=datetime.now(UTC),
        )
    ]
    with patch("app.services.health.ThirdPartyHealthService.get_history", new_callable=AsyncMock) as mock_get_hist:
        mock_get_hist.return_value = mock_histories
        res = await admin_client.get("/api/v1/admin/telemetry/health/history/infra/postgres?hours=12")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["service_id"] == "infra/postgres"
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "healthy"


@pytest.mark.asyncio
async def test_admin_health_single_probe_on_demand(admin_client: AsyncClient) -> None:
    """POST /health/probe/{service_id} executes probe on demand."""
    mock_result = HealthResult(
        service_id="infra/postgres",
        service_name="PostgreSQL Database",
        category="infra",
        display_group="Infrastructure",
        status="healthy",
        latency_ms=10,
    )

    with patch("app.services.health.ThirdPartyHealthService.run_single_probe", new_callable=AsyncMock) as mock_probe:
        mock_probe.return_value = mock_result
        res = await admin_client.post("/api/v1/admin/telemetry/health/probe/infra/postgres")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["service_id"] == "infra/postgres"
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_admin_health_endpoints_require_superuser(
    client_as_regular_user: AsyncClient,
) -> None:
    """Non-superuser gets 403 on all /admin/telemetry/health/* endpoints."""
    for path in [
        "/api/v1/admin/telemetry/health/overview",
        "/api/v1/admin/telemetry/health/statuses",
        "/api/v1/admin/telemetry/health/alerts",
        "/api/v1/admin/telemetry/health/history/infra/postgres",
    ]:
        res = await client_as_regular_user.get(path)
        assert res.status_code == 403, f"{path}: {res.text}"

    res = await client_as_regular_user.get("/api/v1/admin/telemetry/health/categories")
    assert res.status_code == 403, res.text

    # POST endpoints require superuser
    res = await client_as_regular_user.post("/api/v1/admin/telemetry/health/probe/infra/postgres")
    assert res.status_code == 403, res.text

    res = await client_as_regular_user.post("/api/v1/admin/telemetry/health/alerts/1/acknowledge")
    assert res.status_code == 403, res.text
