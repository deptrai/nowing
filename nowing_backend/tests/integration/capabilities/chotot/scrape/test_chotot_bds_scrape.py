"""Integration tests for ``chotot_bds.scrape`` (Story 10.2).

Default run replays the recorded ad-listing envelope through the full
scraper pipeline and verifies billing against a real Postgres session.
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
from app.proprietary.platforms.chotot.parsers import parse_listings
from app.proprietary.platforms.chotot.schemas import (
    ChototBdsScrapeInput,
    ChototBdsScrapeOutput,
)
from app.proprietary.platforms.chotot.scraper import scrape_chotot_bds

pytestmark = [pytest.mark.integration]

_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "unit/platforms/chotot/fixtures/sample_ad_listing.json"
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


async def _fixture_fetcher(**_payload: Any) -> dict:
    """Replay the recorded envelope for page 1; end pagination afterwards."""
    if _payload.get("page", 1) > 1:
        return {"ads": [], "total": 0}
    return _load_fixture()


@pytest.mark.asyncio
async def test_recorded_fixture_roundtrip_typed_listings():
    """AC-1/AC-2/AC-3: fixture replay yields typed listings with parsed fields."""
    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(listing_type="buy", city="ho chi minh", max_items=10),
        fetch_fn=_fixture_fetcher,
    )

    assert output.degraded is False
    assert output.total_items == 2
    assert len(output.items) == 2

    first = output.items[0]
    assert first.listing_id == 133886560
    assert first.title
    assert first.price_raw
    assert first.district == "Quận Bình Tân"
    assert first.city == "Tp Hồ Chí Minh"
    assert first.thumbnail_url.startswith("https://")
    assert first.detail_url.startswith("https://www.nhatot.com/")


@pytest.mark.asyncio
async def test_recorded_fixture_billing_only_charges_parsed_items(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-4: charge only items parsed successfully, at CHOTOT_BDS_ITEM rate."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM", 3500)
    db_user.credit_micros_balance = 1_000_000

    output = ChototBdsScrapeOutput(
        items=parse_listings(_load_fixture()["ads"]),
        total_items=2,
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.CHOTOT_BDS_ITEM, ctx)

    assert charged == 2 * 3500
    assert db_user.credit_micros_balance == 1_000_000 - 2 * 3500

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "chotot_bds_item",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].cost_micros == 2 * 3500
    assert rows[0].user_id == db_user.id


@pytest.mark.skipif(
    os.getenv("SCRAPE_LIVE") != "1",
    reason="set SCRAPE_LIVE=1 to hit the real chotot.com gateway",
)
@pytest.mark.asyncio
async def test_live_scrape_against_real_api():
    """AC-1/AC-5: real API call returns listings or a typed degradation."""
    output = await scrape_chotot_bds(
        ChototBdsScrapeInput(
            listing_type="buy",
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
