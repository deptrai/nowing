"""Unit tests for the Chotot BĐS scraper orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.chotot.schemas import (
    ChototBdsScrapeInput,
    ChototBdsScrapeOutput,
)
from app.proprietary.platforms.chotot.scraper import scrape_chotot_bds

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> dict:
    return json.loads(
        (_FIXTURE_DIR / "sample_ad_listing.json").read_text(encoding="utf-8")
    )


def _make_regions() -> dict[str, Any]:
    return {
        "regionFollowId": {
            "entities": {
                "regions": {
                    "13000": {
                        "id": "13000",
                        "name": "Tp Hồ Chí Minh",
                        "area": {
                            "13108": {
                                "id": "13108",
                                "name": "Quận Bình Tân",
                            }
                        },
                    },
                    "12000": {
                        "id": "12000",
                        "name": "Hà Nội",
                        "area": {},
                    },
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_scrape_collects_and_dedupes():
    sample = _load_sample()

    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        return sample

    async def fake_regions() -> dict[str, Any]:
        return _make_regions()

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="ho chi minh", property_type="house"),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert isinstance(output, ChototBdsScrapeOutput)
    assert output.total_items == 2
    assert not output.degraded


@pytest.mark.asyncio
async def test_scrape_honors_max_items_cap():
    sample = _load_sample()

    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        return sample

    async def fake_regions() -> dict[str, Any]:
        return _make_regions()

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="ho chi minh", max_items=1),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert output.total_items == 1


@pytest.mark.asyncio
async def test_scrape_returns_degraded_on_fetch_error():
    from app.proprietary.platforms.chotot.fetch import ChototBdsAccessBlockedError

    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        raise ChototBdsAccessBlockedError("blocked")

    async def fake_regions() -> dict[str, Any]:
        return _make_regions()

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="ho chi minh"),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert output.degraded is True
    assert output.total_items == 0


@pytest.mark.asyncio
async def test_scrape_dedupes_across_pages():
    sample = _load_sample()
    single = sample["ads"][0]

    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        page = kwargs["page"]
        if page == 1:
            return {"ads": sample["ads"][:1], "total": 2}
        if page == 2:
            return {"ads": [single], "total": 2}
        return {"ads": [], "total": 2}

    async def fake_regions() -> dict[str, Any]:
        return _make_regions()

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="ho chi minh", max_pages=3, max_items=5),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert output.total_items == 1
    assert not output.degraded


@pytest.mark.asyncio
async def test_scrape_handles_malformed_regions_gracefully():
    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        return _load_sample()

    async def fake_regions() -> dict[str, Any]:
        return {
            "regionFollowId": {
                "entities": {
                    "regions": {
                        "13000": {
                            "id": "13000",
                            "name": "Tp Hồ Chí Minh",
                            "area": "not-a-dict",
                        }
                    }
                }
            }
        }

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="ho chi minh", district="Quận Bình Tân"),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert output.degraded is True
    assert "invalid_input" in (output.degradation_reason or "")


@pytest.mark.asyncio
async def test_scrape_returns_degraded_for_unknown_city():
    async def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        return _load_sample()

    async def fake_regions() -> dict[str, Any]:
        return _make_regions()

    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(city="unknown city"),
        fetch_fn=fake_fetch,
        regions_fn=fake_regions,
    )

    assert output.degraded is True
    assert "invalid_input" in (output.degradation_reason or "")
