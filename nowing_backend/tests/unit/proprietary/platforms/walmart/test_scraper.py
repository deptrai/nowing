"""Unit tests for ``app.proprietary.platforms.walmart`` scraper (Story 2.7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.proprietary.platforms.walmart.fetch import _is_blocked
from app.proprietary.platforms.walmart.scraper import (
    _extract_next_data,
    _extract_product_id,
    _parse_product_page,
    _parse_reviews_page,
    _parse_search_page,
    scrape_walmart,
    scrape_walmart_reviews,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _search_html() -> str:
    return _load("search-page.html")


def _product_html() -> str:
    return _load("product-page.html")


def _reviews_json() -> Any:
    return json.loads(_load("reviews.json"))


class TestUrlParsing:
    """AC-1: extract product ids from Walmart URLs."""

    def test_extracts_id_from_ip_slug_url(self):
        assert (
            _extract_product_id(
                "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704"
            )
            == "553491704"
        )

    def test_extracts_id_from_bare_ip_url(self):
        assert _extract_product_id("https://www.walmart.com/ip/553491704") == "553491704"

    def test_extracts_id_from_dp_url(self):
        assert (
            _extract_product_id(
                "https://www.walmart.com/dp/Ozark-Trail-4-Person-Dome-Tent/553491704"
            )
            == "553491704"
        )


class TestBlockDetection:
    """AC-3: detects anti-bot interstitials."""

    def test_detects_robot_or_human(self):
        assert _is_blocked(
            '<html><body>robot or human<br><div class="px-captcha"></div></body></html>', 200
        )

    def test_detects_block_status_codes(self):
        assert _is_blocked("ok", 412)
        assert _is_blocked("ok", 429)
        assert _is_blocked("ok", 503)

    def test_healthy_page_not_blocked(self):
        assert not _is_blocked(_product_html(), 200)


class TestNextDataExtraction:
    """AC-2: pulls the Next.js hydration JSON."""

    def test_extracts_product_next_data(self):
        data = _extract_next_data(_product_html())
        assert data is not None
        product = data["props"]["pageProps"]["initialData"]["data"]["product"]
        assert product["itemId"] == "553491704"


class TestProductParser:
    """AC-2: maps product JSON to normalized fields."""

    def test_parses_product_page(self):
        product = _parse_product_page(_product_html(), "https://www.walmart.com/ip/553491704")
        assert product is not None
        assert product["id"] == "walmart:553491704"
        assert product["title"] == "Ozark Trail 4-Person Dome Tent"
        assert product["price"] == 49.97
        assert product["price_raw"] == "$49.97"
        assert product["currency"] == "USD"
        assert product["rating"] == 4.2
        assert product["seller"] == "Walmart"
        assert product["availability"] == "IN_STOCK"
        assert product["product_url"] == "https://www.walmart.com/ip/553491704"
        assert product["image_url"] == "https://i5.walmartimages.com/ozark-tent.jpg"
        assert product["source"] == "walmart"
        assert product["is_active"] is True

    def test_includes_review_summary(self):
        product = _parse_product_page(_product_html(), "https://www.walmart.com/ip/553491704")
        assert product is not None
        assert len(product["review_summary"]) == 2
        review = product["review_summary"][0]
        assert "Great tent" in review["text"]
        assert review["rating"] == 5
        assert review["verified"] is True


class TestSearchParser:
    """AC-1: maps search HTML cards to normalized fields."""

    def test_parses_search_cards(self):
        cards = _parse_search_page(
            _search_html(), "https://www.walmart.com/search?q=tent&page=1"
        )
        assert len(cards) == 2

    def test_maps_required_fields(self):
        cards = _parse_search_page(
            _search_html(), "https://www.walmart.com/search?q=tent&page=1"
        )
        item = cards[0]
        assert item["id"] == "walmart:553491704"
        assert item["title"] == "Ozark Trail 4-Person Dome Tent"
        assert item["price"] == 49.97
        assert item["price_raw"] == "$49.97"
        assert item["currency"] == "USD"
        assert item["rating"] == 4.2
        assert item["source"] == "walmart"
        assert "/ip/Ozark-Trail-4-Person-Dome-Tent/553491704" in item["product_url"]
        assert item["image_url"] == "https://i5.walmartimages.com/ozark-tent.jpg"


class TestReviewsParser:
    """AC-2: maps review JSON to normalized review items."""

    def test_parses_reviews_from_json(self):
        html = f"""<!doctype html>
<html><body>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(_reviews_json())}</script>
</body></html>"""
        reviews = _parse_reviews_page(html, "https://www.walmart.com/reviews/product/553491704")
        assert len(reviews) == 2
        assert reviews[0]["rating"] == 5
        assert "heavy rain" in reviews[0]["text"]
        assert reviews[0]["verified"] is True
        assert reviews[1]["rating"] == 3


class TestScraperOrchestration:
    """AC-1/AC-2: public scraper entry points."""

    @pytest.mark.asyncio
    async def test_scrape_product_by_url(self, monkeypatch):
        async def _fake_fetch(url: str) -> str:
            return _product_html()

        monkeypatch.setattr(
            "app.proprietary.platforms.walmart.scraper._fetch_html", _fake_fetch
        )

        out = await scrape_walmart(
            {"url": "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704"}
        )

        assert out["degraded"] is False
        assert out["total_items"] == 1
        item = out["items"][0]
        assert item["title"] == "Ozark Trail 4-Person Dome Tent"
        assert item["seller"] == "Walmart"
        assert len(item["review_summary"]) == 2

    @pytest.mark.asyncio
    async def test_scrape_search_by_keyword(self, monkeypatch):
        async def _fake_fetch(url: str) -> str:
            return _search_html()

        monkeypatch.setattr(
            "app.proprietary.platforms.walmart.scraper._fetch_html", _fake_fetch
        )

        out = await scrape_walmart({"keyword": "tent", "max_items": 2, "max_reviews": 0})

        assert out["degraded"] is False
        assert out["total_items"] == 2
        assert out["items"][0]["title"] == "Ozark Trail 4-Person Dome Tent"

    @pytest.mark.asyncio
    async def test_scrape_reviews_by_url(self, monkeypatch):
        product_html = _product_html()
        reviews_payload = _reviews_json()
        reviews_html = f"""<!doctype html>
<html><body>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(reviews_payload)}</script>
</body></html>"""

        async def _fake_fetch(url: str) -> str:
            if "/reviews/product/" in url:
                return reviews_html
            return product_html

        monkeypatch.setattr(
            "app.proprietary.platforms.walmart.scraper._fetch_html", _fake_fetch
        )

        out = await scrape_walmart_reviews(
            {"url": "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704"}
        )

        assert out["degraded"] is False
        assert out["total_items"] == 2
        assert out["items"][0]["verified"] is True


class TestScraperFailureModes:
    """AC-3: degrades gracefully on block/empty."""

    @pytest.mark.asyncio
    async def test_degrades_on_empty(self, monkeypatch):
        async def _fake_fetch(url: str) -> str:
            return ""

        monkeypatch.setattr(
            "app.proprietary.platforms.walmart.scraper._fetch_html", _fake_fetch
        )

        out = await scrape_walmart(
            {"url": "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704"}
        )

        assert out["degraded"] is True
        assert out["degradation_reason"] == "product_not_found"

    @pytest.mark.asyncio
    async def test_degrades_on_blocked(self, monkeypatch):
        async def _fake_fetch(url: str) -> str:
            return "<html><body>robot or human</body></html>"

        monkeypatch.setattr(
            "app.proprietary.platforms.walmart.scraper._fetch_html", _fake_fetch
        )

        out = await scrape_walmart(
            {"url": "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704"}
        )

        assert out["degraded"] is True
        assert out["degradation_reason"] == "product_not_found"
