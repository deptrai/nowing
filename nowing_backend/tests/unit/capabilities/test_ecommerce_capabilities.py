"""Unit tests for Ecommerce Capabilities and MCP Tool Catalog (Story 17.2 / AD-EC-5, AD-EC-6)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.capabilities.core.types import CapabilityContext
from app.capabilities.ecommerce.price_history.definition import (
    ECOMMERCE_TRACK_PRICE_HISTORY,
)
from app.capabilities.ecommerce.price_history.schemas import (
    EcommercePriceHistoryInput,
    EcommercePriceHistoryOutput,
)
from app.capabilities.ecommerce.search.definition import ECOMMERCE_SEARCH_PRODUCTS
from app.capabilities.ecommerce.search.schemas import (
    EcommerceSearchInput,
    EcommerceSearchOutput,
)
from app.mcp_tools import MCP_TOOL_CATALOG, McpToolGroup
from app.proprietary.platforms.shopee.schemas import ShopeeProduct, ShopeeSearchResponse

pytestmark = pytest.mark.unit


def test_mcp_tool_catalog_contains_ecommerce_tools() -> None:
    """Check that nowing_ecommerce_search_products and track_price_history are registered."""
    search_tools = [
        t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_ecommerce_search_products"
    ]
    assert len(search_tools) == 1
    assert search_tools[0]["group"] == McpToolGroup.SCRAPER

    track_tools = [
        t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_ecommerce_track_price_history"
    ]
    assert len(track_tools) == 1
    assert track_tools[0]["group"] == McpToolGroup.SCRAPER


@pytest.mark.asyncio
async def test_ecommerce_search_products_executor() -> None:
    """Capability executor for ecommerce.search_products."""
    mock_product = ShopeeProduct(
        item_id=19283746501,
        shop_id=88231245,
        title="Chuột Không Dây Logitech M331 Silent Plus",
        current_price=Decimal("329000.00"),
        original_price=Decimal("399000.00"),
        discount_percent=18,
        historical_sold=4500,
        rating_star=4.89,
        rating_count=400,
        stock=150,
        status="in_stock",
        image_url="https://cf.shopee.vn/file/vn-11134207-7qukw-lj8192837.jpg",
        product_url="https://shopee.vn/product/88231245/19283746501",
        shop_name="Logitech Official Store",
        shop_location="TP. Hồ Chí Minh",
        brand="Logitech",
    )
    mock_response = ShopeeSearchResponse(
        items=[mock_product],
        total_count=1,
        has_more=False,
    )

    with patch(
        "app.capabilities.ecommerce.search.executor.ShopeeScraper.search_products",
        new=AsyncMock(return_value=mock_response),
    ):
        input_payload = EcommerceSearchInput(
            keyword="Logitech M331",
            min_price=Decimal("200000.00"),
            max_price=Decimal("400000.00"),
            limit=10,
        )
        output: EcommerceSearchOutput = await ECOMMERCE_SEARCH_PRODUCTS.executor(input_payload)

        assert output.total_count == 1
        assert len(output.items) == 1
        item = output.items[0]
        assert item.item_id == 19283746501
        assert item.current_price == Decimal("329000.00")
        assert item.original_price == Decimal("399000.00")
        assert item.discount_percent == 18


@pytest.mark.asyncio
async def test_ecommerce_track_price_history_executor() -> None:
    """Capability executor for ecommerce.track_price_history with DB recording."""
    mock_product = ShopeeProduct(
        item_id=19283746501,
        shop_id=88231245,
        title="Chuột Không Dây Logitech M331 Silent Plus",
        current_price=Decimal("329000.00"),
        original_price=Decimal("399000.00"),
        discount_percent=18,
        historical_sold=4500,
        rating_star=4.89,
        rating_count=400,
        stock=150,
        status="in_stock",
        image_url="https://cf.shopee.vn/file/vn-11134207-7qukw-lj8192837.jpg",
        product_url="https://shopee.vn/product/88231245/19283746501",
        shop_name="Logitech Official Store",
        shop_location="TP. Hồ Chí Minh",
        brand="Logitech",
    )

    mock_session = AsyncMock()
    # Mock finding existing product in DB
    mock_db_product = MagicMock()
    mock_db_product.id = 1
    mock_db_product.item_id = 19283746501
    mock_db_product.shop_id = 88231245
    mock_db_product.current_price = Decimal("350000.00")  # Old price
    mock_db_product.price_history = []

    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    ctx = CapabilityContext(
        session=mock_session,
        workspace_id=1,
    )

    with patch(
        "app.capabilities.ecommerce.price_history.executor.ShopeeScraper.get_product_detail",
        new=AsyncMock(return_value=mock_product),
    ), patch(
        "app.capabilities.ecommerce.price_history.executor.record_or_get_price_history",
        new=AsyncMock(return_value=(
            mock_product,
            [
                {"price": Decimal("350000.00"), "recorded_at": "2026-06-01T00:00:00Z"},
                {"price": Decimal("329000.00"), "recorded_at": "2026-08-15T00:00:00Z"},
            ],
            [Decimal("350000.00"), Decimal("329000.00")],
        )),
    ):
        input_payload = EcommercePriceHistoryInput(
            item_id=19283746501,
            shop_id=88231245,
        )
        output: EcommercePriceHistoryOutput = await ECOMMERCE_TRACK_PRICE_HISTORY.executor(
            input_payload, ctx=ctx
        )

        assert output.product.item_id == 19283746501
        assert output.current_price == Decimal("329000.00")
        assert len(output.price_history) == 2
        assert len(output.sparkline_points) == 2


def test_ecommerce_search_input_validation() -> None:
    """Test min_price <= max_price and non-empty keyword validation."""
    with pytest.raises(ValueError, match="cannot exceed max_price"):
        EcommerceSearchInput(
            keyword="Laptop",
            min_price=Decimal("50000000.00"),
            max_price=Decimal("10000000.00"),
        )

    with pytest.raises(ValueError, match="cannot be empty"):
        EcommerceSearchInput(
            keyword="   ",
        )

