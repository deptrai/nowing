"""Offline tests for the Chotot BĐS fetcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.chotot.fetch import (
    CategoryConfigError,
    ChototBdsAccessBlockedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    fetch_listings,
    get_category_config,
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


def test_get_category_config_returns_correct_cg_for_known_slugs():
    assert get_category_config("bds")["cg"] == 1000
    assert get_category_config("cars")["cg"] == 2010
    assert get_category_config("jobs")["cg"] == 13000
    assert get_category_config("electronics")["cg"] == 5000


def test_get_category_config_accepts_raw_numeric_cg():
    cfg = get_category_config("12345")
    assert cfg["cg"] == 12345
    assert cfg["detail_origin"] == "https://www.chotot.com"
    assert cfg["supported_listing_types"] == {"sell": "s"}


def test_get_category_config_raises_for_unsupported_slug():
    with pytest.raises(CategoryConfigError, match="category_not_supported: unknown"):
        get_category_config("unknown")


def test_resolve_st_maps_listing_type_to_gateway_st():
    from app.proprietary.platforms.chotot.fetch import _resolve_st

    assert _resolve_st("bds", "sell") == "s"
    assert _resolve_st("bds", "rent") == "u"
    assert _resolve_st("bds", "want_to_buy") == "s"
    assert _resolve_st("cars", "sell") == "s"
    assert _resolve_st("cars", "rent") == "s"  # falls back to default


def test_build_detail_url_uses_category_origin():
    from app.proprietary.platforms.chotot.parsers import _build_detail_url

    assert _build_detail_url(177832100, "cars") == "https://xe.chotot.com/177832100.htm"
    assert _build_detail_url(177832101, "motorbikes") == "https://xe.chotot.com/177832101.htm"
    assert _build_detail_url(177832200, "jobs") == "https://vieclamtot.com/177832200.htm"
    assert _build_detail_url(177832300, "electronics") == "https://www.chotot.com/177832300.htm"
    assert _build_detail_url(133886560, "bds") == "https://www.nhatot.com/133886560.htm"


def test_build_listing_params_uses_cg_and_st():
    from app.proprietary.platforms.chotot.fetch import _build_listing_params

    params = _build_listing_params(
        region_v2=13000,
        area_v2=None,
        category="cars",
        listing_type="sell",
        page=1,
        page_size=20,
        min_price=None,
        max_price=None,
        min_area=None,
        max_area=None,
    )
    assert params["cg"] == 2010
    assert params["st"] == "s"
    assert params["w"] == 1
    assert params["o"] == 0


def test_build_listing_params_bds_property_type_overrides_cg():
    from app.proprietary.platforms.chotot.fetch import _build_listing_params

    params = _build_listing_params(
        region_v2=13000,
        area_v2=None,
        category="bds",
        listing_type="rent",
        page=1,
        page_size=20,
        min_price=None,
        max_price=None,
        min_area=None,
        max_area=None,
        property_type="apartment",
    )
    assert params["cg"] == 1010
    assert params["st"] == "u"
