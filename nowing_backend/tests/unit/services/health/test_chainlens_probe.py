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
    mock_resp_health = AsyncMock()
    mock_resp_health.status_code = 200
    mock_resp_search = AsyncMock()
    mock_resp_search.status_code = 200

    def _client_get(url, *args, **kwargs):
        if "/api/v1/health" in url:
            return mock_resp_health
        return mock_resp_search

    def _client_post(url, *args, **kwargs):
        return mock_resp_search

    mock_client.get.side_effect = _client_get
    mock_client.post.side_effect = _client_post

    with patch("app.services.health.probes.chainlens_probe.httpx.AsyncClient") as mock_cls, \
         patch("app.services.health.probes.chainlens_probe.config.CHAINLENS_API_KEY", "mock-key"):
        mock_cls.return_value.__aenter__.return_value = mock_client

        result = await probe.probe()
        assert result.service_id == "chainlens/research"
        assert result.status == "healthy"
        assert result.metadata["configured"] is True
