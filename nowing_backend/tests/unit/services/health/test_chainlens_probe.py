"""Unit tests for ChainLensHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.health.probes.chainlens_probe import ChainLensHealthProbe


@pytest.mark.asyncio
async def test_chainlens_probe_healthy() -> None:
    probe = ChainLensHealthProbe()
    assert probe.service_id == "chainlens/research"

    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "version": "1.0.0"}
    mock_client.get.return_value = mock_resp

    with patch("app.services.health.probes.chainlens_probe.httpx.AsyncClient") as mock_cls, \
         patch("app.services.health.probes.chainlens_probe.config.CHAINLENS_API_KEY", "mock-key"):
        mock_cls.return_value.__aenter__.return_value = mock_client

        result = await probe.probe()
        assert result.service_id == "chainlens/research"
        assert result.status == "healthy"
        assert result.metadata["configured"] is True
