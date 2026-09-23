"""Unit tests for InfrastructureHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.health.probes.infrastructure_probe import InfrastructureHealthProbe


@pytest.mark.asyncio
async def test_infra_postgres_probe() -> None:
    probe = InfrastructureHealthProbe(component="postgres")
    assert probe.service_id == "infra/postgres"

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_connect_cm = AsyncMock()
    mock_connect_cm.__aenter__.return_value = mock_conn

    with patch.object(probe, "probe", new_callable=AsyncMock) as mock_probe:
        from app.services.health.probe_base import HealthResult
        mock_probe.return_value = HealthResult(
            service_id="infra/postgres",
            service_name="PostgreSQL Database",
            category="infra",
            display_group="Infrastructure",
            status="healthy",
            latency_ms=15,
        )

        result = await probe.probe()
        assert result.service_id == "infra/postgres"
        assert result.status == "healthy"


@pytest.mark.asyncio
async def test_infra_redis_probe() -> None:
    probe = InfrastructureHealthProbe(component="redis")

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    with patch("app.services.health.probes.infrastructure_probe.get_redis_client", return_value=mock_redis):
        result = await probe.probe()
        assert result.service_id == "infra/redis"
        assert result.status == "healthy"
