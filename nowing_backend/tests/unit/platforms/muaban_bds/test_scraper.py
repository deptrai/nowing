"""Unit tests for the Muaban BĐS scraper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput
from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _make_session_class():
    class _FakeSession:
        def __init__(self, **kwargs):
            pass

        async def start(self):
            pass

        async def close(self):
            pass

    return _FakeSession


@pytest.mark.asyncio
async def test_scrape_city_hcm(mocker):
    data = _load("hcm_city")
    mocker.patch(
        "app.proprietary.platforms.muaban_bds.scraper.fetch_page",
        return_value=data,
    )
    mocker.patch(
        "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
        _make_session_class(),
    )

    input_model = MuabanBdsScrapeInput(city="ho-chi-minh", max_items=5, max_pages=1)
    output = await scrape_muaban_bds(input_model)

    assert not output.degraded
    assert len(output.items) == 5
    assert output.total_items == 5
    assert output.items[0].city
    assert output.items[0].detail_url.startswith("https://muaban.net")


@pytest.mark.asyncio
async def test_scrape_unknown_city(mocker):
    mocker.patch(
        "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
        _make_session_class(),
    )

    input_model = MuabanBdsScrapeInput(city="unknownville", max_items=5)
    output = await scrape_muaban_bds(input_model)

    assert output.degraded
    assert "unknown_city" in output.degradation_reason


@pytest.mark.asyncio
async def test_scrape_404(mocker):
    mocker.patch(
        "app.proprietary.platforms.muaban_bds.scraper.fetch_page",
        return_value={"notFound": True},
    )
    mocker.patch(
        "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
        _make_session_class(),
    )

    input_model = MuabanBdsScrapeInput(city="ho-chi-minh", max_items=5, max_pages=2)
    output = await scrape_muaban_bds(input_model)

    assert output.degraded
    assert "not_found" in output.degradation_reason
