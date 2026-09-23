"""Unit tests for ProxyHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.health.probes.proxy_probe import ProxyHealthProbe


@pytest.mark.asyncio
async def test_proxy_probe_healthy() -> None:
    probe = ProxyHealthProbe()
    assert probe.service_id == "proxy/dataimpulse"

    mock_telemetry_service = AsyncMock()
    mock_telemetry_service.get_proxy_health.return_value = {
        "status": "healthy",
        "latency_ms": 250,
        "consecutive_failures": 0,
        "provider": "dataimpulse",
        "error": None,
        "success_rate": 100.0,
    }

    with patch("app.services.health.probes.proxy_probe.AdminTelemetryService", return_value=mock_telemetry_service):
        result = await probe.probe()
        assert result.service_id == "proxy/dataimpulse"
        assert result.status == "healthy"
        assert result.latency_ms == 250
