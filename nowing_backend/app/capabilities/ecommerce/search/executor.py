"""Executor for ``ecommerce.search_products`` capability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.ecommerce.search.schemas import (
    EcommerceProductItem,
    EcommerceSearchInput,
    EcommerceSearchOutput,
)
from app.proprietary.platforms.shopee.scraper import ShopeeScraper

ExecutorFn = Callable[[EcommerceSearchInput], Awaitable[EcommerceSearchOutput]]


def build_search_executor(*, scraper_factory: Callable[[], ShopeeScraper] | None = None) -> ExecutorFn:
    """Factory creating an executor for searching Shopee products."""
    make_scraper = scraper_factory or ShopeeScraper

    async def _execute(payload: EcommerceSearchInput) -> EcommerceSearchOutput:
        async with make_scraper() as scraper:
            resp = await scraper.search_products(
                keyword=payload.keyword,
                min_price=payload.min_price,
                max_price=payload.max_price,
                limit=payload.limit,
                offset=payload.offset,
            )

        items = [
            EcommerceProductItem(
                item_id=p.item_id,
                shop_id=p.shop_id,
                title=p.title,
                name=p.name,
                brand=p.brand,
                current_price=p.current_price,
                original_price=p.original_price,
                discount_percent=p.discount_percent,
                historical_sold=p.historical_sold,
                rating_star=p.rating_star,
                rating_count=p.rating_count,
                stock=p.stock,
                status=p.status,
                image_url=p.image_url,
                product_url=p.product_url,
                shop_name=p.shop_name,
                shop_location=p.shop_location,
                raw_specs=p.raw_specs,
            )
            for p in resp.items
        ]

        return EcommerceSearchOutput(
            items=items,
            total_count=resp.total_count,
            has_more=resp.has_more,
        )

    return _execute
