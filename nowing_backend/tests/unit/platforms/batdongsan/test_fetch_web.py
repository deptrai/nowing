"""Offline tests for the Batdongsan web SSR fetcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.proprietary.platforms.batdongsan.fetch import (
    CITY_SLUGS,
    BatdongsanAccessBlockedError,
    build_web_listings_url,
    fetch_web_listings,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_sleep(mocker):
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_city_slugs_contains_known_codes():
    assert CITY_SLUGS["HN"] == "ha-noi"
    assert CITY_SLUGS["SG"] == "tp-hcm"
    assert CITY_SLUGS["BTH"] == "binh-thuan"
    assert CITY_SLUGS["TTH"] == "hue"


def test_build_web_listings_url_buy():
    assert (
        build_web_listings_url("buy", "binh-thuan", 1)
        == "https://batdongsan.com.vn/ban-nha-dat-binh-thuan"
    )
    assert (
        build_web_listings_url("buy", "binh-thuan", 3)
        == "https://batdongsan.com.vn/ban-nha-dat-binh-thuan/p3"
    )


def test_build_web_listings_url_rent():
    assert (
        build_web_listings_url("rent", "ha-noi", 1)
        == "https://batdongsan.com.vn/nha-dat-cho-thue-ha-noi"
    )


@pytest.mark.asyncio
async def test_fetch_web_listings_returns_data(mocker):
    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
    mock_page = mocker.MagicMock()
    mock_page.status = 200
    mock_page.body = html
    mock_get = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_get.return_value = mock_page

    result = await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})

    assert isinstance(result, dict)
    assert len(result["data"]) == 2
    assert result["data"][0]["id"] == 45972873
    assert (
        result["data"][0]["title"]
        == "Bán nhà hẻm 222/20 Thủ Khoa Huân, phường Phú Thủy, DT 102.7m2"
    )
    assert result["data"][0]["price"] == "3,4 tỷ"
    assert result["data"][0]["area"] == "102,7 m²"
    assert result["data"][0]["address"] == "TP. Phan Thiết (P. Phú Thủy mới)"
    assert result["data"][0]["room"] == 2
    assert result["m"] is None  # < 20 items → no more


@pytest.mark.asyncio
async def test_fetch_web_listings_unknown_city_returns_empty(mocker):
    mock_get = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )

    result = await fetch_web_listings({"ptype": 38, "city": "ZZZ", "page": 1})

    assert result == {"data": [], "m": None}
    mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_web_listings_403_raises_blocked(mocker):
    mock_page = mocker.MagicMock()
    mock_page.status = 403
    mock_page.body = b""
    mock_get = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_page.status = 403
    mock_get.return_value = mock_page
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")

    with pytest.raises(BatdongsanAccessBlockedError):
        await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})


@pytest.mark.asyncio
async def test_fetch_web_listings_rotates_on_403_then_succeeds(mocker):
    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
    blocked = mocker.MagicMock()
    blocked.status = 403
    blocked.body = b""
    ok = mocker.MagicMock()
    ok.status = 200
    ok.body = html
    mock_get = mocker.patch(
        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
        new_callable=mocker.AsyncMock,
    )
    mock_get.side_effect = [blocked, ok]
    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")

    result = await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})

    assert len(result["data"]) == 2
    assert mock_get.await_count == 2
