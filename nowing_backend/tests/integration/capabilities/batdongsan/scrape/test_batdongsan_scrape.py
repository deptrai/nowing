"""Integration tests for ``batdongsan.scrape`` (Story 10.1).

Default run replays the recorded ``p_sync`` envelope through the full
scraper pipeline and verifies billing against a real Postgres session.
Set ``SCRAPE_LIVE=1`` to additionally hit the real mobile API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select

from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import TokenUsage
from app.proprietary.platforms.batdongsan.schemas import (
    BatdongsanScrapeInput,
    BatdongsanScrapeOutput,
)
from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan

pytestmark = [pytest.mark.integration]

_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "unit/platforms/batdongsan/fixtures/sample_p_sync.json"
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


async def _fixture_fetcher(_payload: dict) -> dict:
    """Replay the recorded envelope for page 1; end pagination afterwards."""
    if _payload.get("page", 1) > 1:
        return {"data": [], "m": None}
    return _load_fixture()


@pytest.mark.asyncio
async def test_recorded_fixture_roundtrip_typed_listings():
    """AC-1/AC-2/AC-3: fixture replay yields typed listings with parsed fields."""
    output = await scrape_batdongsan(
        BatdongsanScrapeInput(listing_type="buy", city="HN", max_items=10),
        fetch_fn=_fixture_fetcher,
    )

    assert output.degraded is False
    assert output.total_items == 2
    assert len(output.items) == 2

    first = output.items[0]
    assert first.listing_id == 46122640
    assert first.title == "Bán nhà riêng tại Ba Đình"
    assert first.price == "19.8 Tỷ"
    assert first.area == "75 m²"
    assert first.district == "Ba Đình"
    assert first.city == "Hà Nội"
    assert first.post_date == "31/07/2026"
    assert first.thumbnail_url.startswith("https://file4.batdongsan.com.vn/")
    assert first.detail_url.startswith("https://batdongsan.com.vn/")


@pytest.mark.asyncio
async def test_recorded_fixture_billing_only_charges_parsed_items(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-4: charge only items parsed successfully, at BATDONGSAN_ITEM rate."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3500)
    db_user.credit_micros_balance = 1_000_000

    output = BatdongsanScrapeOutput(
        items=list((await _fixture_fetcher({}))["data"]),
        total_items=2,
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)

    charged = await charge_capability(output, BillingUnit.BATDONGSAN_ITEM, ctx)

    assert charged == 2 * 3500
    assert db_user.credit_micros_balance == 1_000_000 - 2 * 3500

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id == db_workspace.id,
                    TokenUsage.usage_type == "batdongsan_item",
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
    reason="set SCRAPE_LIVE=1 to hit the real batdongsan.com.vn API",
)
@pytest.mark.asyncio
async def test_live_scrape_against_real_api():
    """AC-1/AC-5: real API call returns listings or a typed degradation.

    The live ``p_sync`` response no longer reliably includes the ``url`` field,
    so ``detail_url`` is constructed from ``listing_id``, city and title when
    ``resolve_phones=True``; the web-listing resolver only runs if construction
    leaves gaps.
    """
    output = await scrape_batdongsan(
        BatdongsanScrapeInput(
            listing_type="buy",
            city="HN",
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
            "unknown",
        }
    else:
        assert output.total_items >= 0
        for item in output.items:
            assert item.listing_id is not None
            assert item.title
