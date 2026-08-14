"""Integration tests for ``chotot.scrape`` across non-BĐS verticals (Story 10.6).

Default run replays recorded ad-listing envelopes through the full scraper
pipeline and verifies billing against a real Postgres session.
Set ``SCRAPE_LIVE=1`` to additionally hit the real Chotot gateway.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import TokenUsage
from app.proprietary.platforms.chotot.schemas import ChototScrapeInput
from app.proprietary.platforms.chotot.scraper import scrape_chotot

pytestmark = [pytest.mark.integration]

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[4] / "unit/platforms/chotot/fixtures"
)


def _load_fixture(name: str) -> dict:
    return json.loads(
        (_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
    )


async def _fixture_regions() -> dict[str, Any]:
    """Return a canned region/area table so tests never hit the network."""
    return {
        "regionFollowId": {
            "entities": {
                "regions": {
                    "13000": {
                        "id": 13000,
                        "name": "Tp Hồ Chí Minh",
                        "area": {
                            "13108": {"id": 13108, "name": "Quận Bình Tân"},
                            "13109": {"id": 13109, "name": "Quận 7"},
                            "13110": {"id": 13110, "name": "Quận 1"},
                        },
                    },
                    "13020": {
                        "id": 13020,
                        "name": "Hà Nội",
                        "area": {
                            "13021": {"id": 13021, "name": "Quận Cầu Giấy"},
                        },
                    },
                }
            }
        }
    }


async def _fixture_fetcher(**_payload: Any) -> dict:
    """Replay a recorded envelope based on the requested category.

    ``scrape_chotot`` passes the full page payload; we ignore everything
    except ``page`` and ``category`` so the test stays hermetic.
    """
    if _payload.get("page", 1) > 1:
        return {"ads": [], "total": 0}

    category = _payload.get("category", "bds")
    mapping = {
        "cars": "vehicles",
        "motorbikes": "motorbikes",
        "jobs": "jobs",
        "electronics": "electronics",
        "bds": "sample_ad_listing",
    }
    name = mapping.get(category, "sample_ad_listing")
    return _load_fixture(name)


@pytest.mark.asyncio
async def test_recorded_fixture_roundtrip_cars():
    """AC-1/AC-4/AC-8: fixture replay yields typed vehicle listings."""
    output = await scrape_chotot(
        ChototScrapeInput(
            category="cars",
            listing_type="sell",
            city="ho chi minh",
            district="Quận 7",
            max_items=10,
        ),
        fetch_fn=_fixture_fetcher,
        regions_fn=_fixture_regions,
    )

    assert output.degraded is False
    assert output.total_items == 1
    assert len(output.items) == 1

    first = output.items[0]
    assert first.listing_id == 177832100
    assert first.title == "Toyota Camry 2.5G 2020 màu đen"
    assert first.price_value == 820_000_000
    assert first.city == "Tp Hồ Chí Minh"
    assert first.district == "Quận 7"
    assert first.thumbnail_url.startswith("https://")
    assert first.detail_url == "https://xe.chotot.com/177832100.htm"
    assert first.category == "cars"
    assert first.attributes["make"] == "Toyota"
    assert first.attributes["model"] == "Camry"
    assert first.attributes["year"] == 2020


@pytest.mark.asyncio
async def test_recorded_fixture_roundtrip_jobs():
    """AC-1/AC-4/AC-9: fixture replay yields typed job listings."""
    output = await scrape_chotot(
        ChototScrapeInput(
            category="jobs",
            listing_type="sell",
            city="ho chi minh",
            district="Quận 1",
            max_items=10,
        ),
        fetch_fn=_fixture_fetcher,
        regions_fn=_fixture_regions,
    )

    assert output.degraded is False
    assert output.total_items == 1
    assert len(output.items) == 1

    first = output.items[0]
    assert first.listing_id == 177832200
    assert first.category == "jobs"
    assert first.detail_url == "https://vieclamtot.com/177832200.htm"
    assert first.attributes["salary_min"] == 20_000_000
    assert first.attributes["salary_max"] == 30_000_000
    assert first.attributes["company_name"] == "TechVN"


@pytest.mark.asyncio
async def test_recorded_fixture_roundtrip_electronics():
    """AC-1/AC-4/AC-10: fixture replay yields typed electronics listings."""
    output = await scrape_chotot(
        ChototScrapeInput(
            category="electronics",
            listing_type="sell",
            city="hanoi",
            district="Quận Cầu Giấy",
            max_items=10,
        ),
        fetch_fn=_fixture_fetcher,
        regions_fn=_fixture_regions,
    )

    assert output.degraded is False
    assert output.total_items == 1
    assert len(output.items) == 1

    first = output.items[0]
    assert first.listing_id == 177832300
    assert first.category == "electronics"
    assert first.city == "Hà Nội"
    assert first.district == "Quận Cầu Giấy"
    assert first.detail_url == "https://www.chotot.com/177832300.htm"
    assert first.attributes["brand"] == "Apple"
    assert first.attributes["model"] == "iPhone 14 Pro Max"


@pytest.mark.asyncio
async def test_degrades_on_unsupported_category():
    """AC-3: an unsupported category returns a degraded output without crashing."""
    output = await scrape_chotot(
        ChototScrapeInput(
            category="spaceships",
            listing_type="sell",
            city="hanoi",
            max_items=10,
        ),
        fetch_fn=_fixture_fetcher,
        regions_fn=_fixture_regions,
    )

    assert output.degraded is True
    assert output.items == []
    assert output.total_items == 0
    assert "category_not_supported" in (output.degradation_reason or "")


@pytest.mark.asyncio
async def test_recorded_fixture_billing_only_charges_parsed_cars(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-11: unknown categories are not billed; known categories are."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "CHOTOT_SCRAPE_MICROS_PER_ITEM", 3500)
    db_user.credit_micros_balance = 1_000_000

    output = await scrape_chotot(
        ChototScrapeInput(
            category="cars",
            listing_type="sell",
            city="ho chi minh",
            district="Quận 7",
            max_items=10,
        ),
        fetch_fn=_fixture_fetcher,
        regions_fn=_fixture_regions,
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHOTOT_ITEM, ctx)

    assert charged == 1 * 3500
    assert db_user.credit_micros_balance == 1_000_000 - 1 * 3500

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "chotot_item",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].cost_micros == 1 * 3500
    assert rows[0].user_id == db_user.id


@pytest.mark.skipif(
    os.getenv("SCRAPE_LIVE") != "1",
    reason="set SCRAPE_LIVE=1 to hit the real chotot.com gateway",
)
@pytest.mark.asyncio
async def test_live_scrape_cars_against_real_api():
    """AC-1/AC-5: real API call returns car listings or a typed degradation."""
    output = await scrape_chotot(
        ChototScrapeInput(
            category="cars",
            listing_type="sell",
            city="ho chi minh",
            max_pages=1,
            max_items=5,
        )
    )

    if output.degraded:
        assert output.degradation_reason in {
            "api_error",
            "rate_limited",
            "decode_error",
            "empty",
            "bot_detected",
            "layout_changed",
            "unknown",
        }
    else:
        assert output.total_items >= 0
        for item in output.items:
            assert item.listing_id is not None
            assert item.title
            assert item.detail_url
