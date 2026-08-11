"""Offline tests for the Chotot BĐS fetcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.chotot.fetch import (
    ChototBdsAccessBlockedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    fetch_listings,
)

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> dict:
    return json.loads(
        (_FIXTURE_DIR / "sample_ad_listing.json").read_text(encoding="utf-8")
    )


def test_decode_returns_empty_for_empty_data():
    from app.proprietary.platforms.chotot.fetch import _decode

    result = _decode(json.dumps({"ads": [], "total": 0}).encode())
    assert result["ads"] == []


def test_decode_raises_for_invalid_json():
    from app.proprietary.platforms.chotot.fetch import _decode

    with pytest.raises(ChototBdsDecodeError):
        _decode(b"not-valid-json")


@pytest.mark.asyncio
async def test_fetch_listings_returns_data(mocker):
    sample = _load_sample()

    mock_page = mocker.MagicMock()
    mock_page.status = 200
    mock_page.body = json.dumps(sample).encode()
    mock_get = mocker.patch(
        "app.proprietary.platforms.chotot.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_get.return_value = mock_page

    result = await fetch_listings(
        region_v2=13000,
        area_v2=None,
        category="bds",
        property_type="house",
        listing_type="buy",
        page=1,
    )

    assert isinstance(result, dict)
    assert "ads" in result
    assert len(result["ads"]) == 2
    mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_listings_429_raises_rate_limited(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 429
    mock_page.body = b""
    mock_get = mocker.patch(
        "app.proprietary.platforms.chotot.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_get.return_value = mock_page
    mocker.patch("app.proprietary.platforms.chotot.fetch.asyncio.sleep")

    with pytest.raises(ChototBdsRateLimitedError):
        await fetch_listings(
            region_v2=13000,
            area_v2=None,
            category="bds",
            property_type="house",
            listing_type="buy",
            page=1,
        )


@pytest.mark.asyncio
async def test_fetch_listings_403_raises_blocked(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 403
    mock_page.body = b""
    mock_get = mocker.patch(
        "app.proprietary.platforms.chotot.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_get.return_value = mock_page
    mocker.patch("app.proprietary.platforms.chotot.fetch.asyncio.sleep")

    with pytest.raises(ChototBdsAccessBlockedError):
        await fetch_listings(
            region_v2=13000,
            area_v2=None,
            category="bds",
            property_type="house",
            listing_type="buy",
            page=1,
        )
