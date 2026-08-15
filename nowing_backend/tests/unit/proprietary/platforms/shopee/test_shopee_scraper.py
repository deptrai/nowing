"""Unit tests for Shopee Vietnam Fast JSON Scraper (Story 17.2 / AD-EC-1, AD-EC-4)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.proprietary.platforms.shopee.scraper import (
    ShopeeBlockedError,
    ShopeeRateLimitedError,
    ShopeeScraper,
    ShopeeScraperError,
)

pytestmark = pytest.mark.unit


_SAMPLE_SEARCH_RESPONSE = {
    "error": None,
    "error_msg": None,
    "total_count": 120,
    "items": [
        {
            "item_basic": {
                "itemid": 19283746501,
                "shopid": 88231245,
                "name": "Chuột Không Dây Logitech M331 Silent Plus Chính Hãng",
                "price": 32900000000,
                "price_before_discount": 39900000000,
                "raw_discount": 18,
                "historical_sold": 4500,
                "item_rating": {"rating_star": 4.89, "rating_count": [10, 2, 5, 20, 400]},
                "stock": 150,
                "status": 1,
                "image": "vn-11134207-7qukw-lj8192837.jpg",
                "shop_location": "TP. Hồ Chí Minh",
                "brand": "Logitech",
            }
        },
        {
            "item_basic": {
                "itemid": 19283746502,
                "shopid": 88231245,
                "name": "Bàn Phím Cơ Không Dây Logitech K380 Multi-Device",
                "price": 59900000000,
                "price_before_discount": 69900000000,
                "raw_discount": 14,
                "historical_sold": 8200,
                "item_rating": {"rating_star": 4.92, "rating_count": [5, 1, 3, 30, 800]},
                "stock": 80,
                "status": 1,
                "image": "vn-11134207-7qukw-lj8192838.jpg",
                "shop_location": "Hà Nội",
                "brand": "Logitech",
            }
        },
    ],
}

_SAMPLE_ITEM_DETAIL_RESPONSE = {
    "error": None,
    "error_msg": None,
    "data": {
        "itemid": 19283746501,
        "shopid": 88231245,
        "name": "Chuột Không Dây Logitech M331 Silent Plus Chính Hãng",
        "description": "Chuột Logitech M331 Silent kết nối không dây 2.4GHz pin 24 tháng.",
        "price": 32900000000,
        "price_before_discount": 39900000000,
        "raw_discount": 18,
        "historical_sold": 4500,
        "item_rating": {"rating_star": 4.89, "rating_count": [10, 2, 5, 20, 400]},
        "stock": 150,
        "status": 1,
        "image": "vn-11134207-7qukw-lj8192837.jpg",
        "shop_location": "TP. Hồ Chí Minh",
        "brand": "Logitech",
        "models": [
            {"name": "Đen", "price": 32900000000, "stock": 50},
            {"name": "Xám", "price": 32900000000, "stock": 50},
            {"name": "Đỏ", "price": 32900000000, "stock": 50},
        ],
    },
}


class TestShopeeScraperSearch:
    """Test search endpoint /api/v4/search/search_items."""

    @pytest.mark.asyncio
    async def test_search_items_success(self):
        scraper = ShopeeScraper()
        mock_response = httpx.Response(
            status_code=200,
            json=_SAMPLE_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://shopee.vn/api/v4/search/search_items"),
        )

        with patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            result = await scraper.search_products(keyword="Logitech M331", limit=10)

            assert mock_get.called
            call_kwargs = mock_get.call_args.kwargs
            assert "headers" in call_kwargs
            assert call_kwargs["headers"].get("X-Shopee-Language") == "vi"
            assert "User-Agent" in call_kwargs["headers"]

            assert result.total_count == 120
            assert len(result.items) == 2

            item = result.items[0]
            assert item.item_id == 19283746501
            assert item.shop_id == 88231245
            assert item.title == "Chuột Không Dây Logitech M331 Silent Plus Chính Hãng"
            assert item.current_price == Decimal("329000.00")
            assert item.original_price == Decimal("399000.00")
            assert item.discount_percent == 18
            assert item.historical_sold == 4500
            assert item.rating_star == 4.89
            assert item.status == "in_stock"

    @pytest.mark.asyncio
    async def test_search_items_with_price_range(self):
        scraper = ShopeeScraper()
        mock_response = httpx.Response(
            status_code=200,
            json=_SAMPLE_SEARCH_RESPONSE,
            request=httpx.Request("GET", "https://shopee.vn/api/v4/search/search_items"),
        )

        with patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)) as mock_get:
            await scraper.search_products(
                keyword="Logitech",
                min_price=Decimal("100000.00"),
                max_price=Decimal("500000.00"),
            )

            call_params = mock_get.call_args.kwargs["params"]
            assert "price_min" in call_params
            assert "price_max" in call_params


class TestShopeeScraperItemDetail:
    """Test item detail endpoint /api/v4/item/get."""

    @pytest.mark.asyncio
    async def test_get_item_detail_success(self):
        scraper = ShopeeScraper()
        mock_response = httpx.Response(
            status_code=200,
            json=_SAMPLE_ITEM_DETAIL_RESPONSE,
            request=httpx.Request("GET", "https://shopee.vn/api/v4/item/get"),
        )

        with patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)):
            item = await scraper.get_product_detail(item_id=19283746501, shop_id=88231245)

            assert item is not None
            assert item.item_id == 19283746501
            assert item.shop_id == 88231245
            assert item.current_price == Decimal("329000.00")
            assert item.original_price == Decimal("399000.00")
            assert item.stock == 150
            assert item.raw_specs.get("brand") == "Logitech"


class TestShopeeScraperResilienceAndErrorHandling:
    """Test HTTP status code handling, retries, and exceptions."""

    @pytest.mark.asyncio
    async def test_rate_limited_429_raises_error(self):
        scraper = ShopeeScraper(max_retries=1)
        mock_response = httpx.Response(
            status_code=429,
            text="Too Many Requests",
            request=httpx.Request("GET", "https://shopee.vn/api/v4/search/search_items"),
        )

        with (
            patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)),
            pytest.raises(ShopeeRateLimitedError),
        ):
            await scraper.search_products(keyword="test")

    @pytest.mark.asyncio
    async def test_bot_detected_403_raises_error(self):
        scraper = ShopeeScraper(max_retries=1)
        mock_response = httpx.Response(
            status_code=403,
            text="Access Denied / Bot Detection",
            request=httpx.Request("GET", "https://shopee.vn/api/v4/search/search_items"),
        )

        with (
            patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)),
            pytest.raises(ShopeeBlockedError),
        ):
            await scraper.search_products(keyword="test")

    @pytest.mark.asyncio
    async def test_server_error_500_raises_scraper_error(self):
        scraper = ShopeeScraper(max_retries=1)
        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://shopee.vn/api/v4/search/search_items"),
        )

        with (
            patch.object(scraper._client, "get", new=AsyncMock(return_value=mock_response)),
            pytest.raises(ShopeeScraperError),
        ):
            await scraper.search_products(keyword="test")
