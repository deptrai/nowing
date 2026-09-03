"""Unit tests for ScraperHealthProbe."""

from __future__ import annotations

import pytest

from app.services.health.probes.scraper_probe import ScraperHealthProbe


@pytest.mark.asyncio
async def test_scraper_probe_healthy() -> None:
    probe = ScraperHealthProbe(
        platform="tiktok",
        service_name="TikTok Video Scraper",
        display_group="Social Networks",
    )
    assert probe.service_id == "scraper/tiktok"
    assert probe.category == "scraper"

    result = await probe.probe()
    assert result.service_id == "scraper/tiktok"
    assert result.status == "healthy"
    assert result.error_rate_15m == 0.0
    assert result.metadata["platform"] == "tiktok"
