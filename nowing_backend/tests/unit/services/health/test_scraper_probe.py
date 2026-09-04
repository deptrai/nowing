"""Unit tests for ScraperHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.scraper_probe import ScraperHealthProbe


@pytest.mark.asyncio
async def test_scraper_probe_not_configured_when_capability_missing() -> None:
    probe = ScraperHealthProbe(
        platform="unknown_platform",
        service_name="Unknown Scraper",
    )
    assert probe.service_id == "scraper/unknown_platform"
    assert probe.category == "scraper"

    with patch.object(probe, "_is_cap_registered", return_value=False):
        result = await probe.probe()
        assert result.status == "not_configured"
        assert "Register" in (result.suggested_action or "")
        assert result.metadata["capability_registered"] is False


@pytest.mark.asyncio
async def test_scraper_probe_healthy() -> None:
    probe = ScraperHealthProbe(
        platform="tiktok",
        service_name="TikTok Video Scraper",
        display_group="Social Networks",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=mock_resp)

    with patch.object(probe, "_is_cap_registered", return_value=True), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.service_id == "scraper/tiktok"
        assert result.status == "healthy"
        assert result.error_rate_15m == 0.0
        assert result.metadata["platform"] == "tiktok"


@pytest.mark.asyncio
async def test_scraper_probe_degraded_on_403() -> None:
    probe = ScraperHealthProbe(
        platform="tiktok",
        service_name="TikTok Video Scraper",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=mock_resp)

    with patch.object(probe, "_is_cap_registered", return_value=True), \
         patch("app.utils.proxy.get_active_provider", return_value=None), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "degraded"
        assert "403" in (result.last_error or "")
