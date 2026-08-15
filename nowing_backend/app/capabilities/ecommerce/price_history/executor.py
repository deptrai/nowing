"""Executor for ``ecommerce.track_price_history`` capability."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core.types import CapabilityContext
from app.capabilities.ecommerce.price_history.schemas import (
    EcommercePriceHistoryInput,
    EcommercePriceHistoryOutput,
    PriceSnapshot,
)
from app.capabilities.ecommerce.search.schemas import EcommerceProductItem
from app.proprietary.platforms.shopee.models import (
    EcommercePriceHistory,
    EcommerceProduct,
)
from app.proprietary.platforms.shopee.normalizer import extract_ids_from_url
from app.proprietary.platforms.shopee.schemas import ShopeeProduct
from app.proprietary.platforms.shopee.scraper import ShopeeScraper

logger = logging.getLogger(__name__)

ExecutorFn = Callable[..., Awaitable[EcommercePriceHistoryOutput]]


def _resolve_ids(payload: EcommercePriceHistoryInput) -> tuple[int | None, int | None]:
    """Resolve (shop_id, item_id) from explicit params, external ID, or URL."""
    shop_id = payload.shop_id if (payload.shop_id is not None and payload.shop_id > 0) else None
    item_id = payload.item_id if (payload.item_id is not None and payload.item_id > 0) else None

    if (item_id is None or shop_id is None) and payload.url:
        u_shop_id, u_item_id = extract_ids_from_url(payload.url)
        if u_shop_id is not None and u_item_id is not None:
            shop_id = shop_id or u_shop_id
            item_id = item_id or u_item_id

    if (item_id is None or shop_id is None) and payload.external_product_id:
        ext = payload.external_product_id.strip()
        if "_" in ext:
            parts = ext.split("_", 1)
            with contextlib.suppress(ValueError):
                shop_id = shop_id or int(parts[0])
                item_id = item_id or int(parts[1])
        else:
            with contextlib.suppress(ValueError):
                item_id = item_id or int(ext)

    return shop_id, item_id


async def record_or_get_price_history(
    session: AsyncSession,
    product: ShopeeProduct,
    item_id: int,
    shop_id: int,
) -> tuple[ShopeeProduct, list[dict[str, Any]], list[Decimal]]:
    """Persist/update product and append time-series price point if changed."""
    now = datetime.now(UTC)

    # 1. Look up existing product
    stmt = select(EcommerceProduct).where(
        EcommerceProduct.platform == "shopee",
        EcommerceProduct.item_id == item_id,
        EcommerceProduct.shop_id == shop_id,
    )
    result = await session.execute(stmt)
    db_product = result.scalars().first()

    if db_product is None:
        try:
            async with session.begin_nested():
                db_product = EcommerceProduct(
                    platform="shopee",
                    item_id=item_id,
                    shop_id=shop_id,
                    shop_name=product.shop_name,
                    shop_location=product.shop_location,
                    title=product.title,
                    brand=product.brand,
                    current_price=product.current_price,
                    original_price=product.original_price,
                    discount_percent=product.discount_percent,
                    historical_sold=product.historical_sold,
                    rating_star=product.rating_star,
                    rating_count=product.rating_count,
                    stock=product.stock,
                    status=product.status,
                    image_url=product.image_url,
                    product_url=product.product_url,
                    raw_specs=product.raw_specs,
                )
                session.add(db_product)
                await session.flush()

                # Add initial price history snapshot
                history_row = EcommercePriceHistory(
                    product_id=db_product.id,
                    price=product.current_price,
                    recorded_at=now,
                )
                session.add(history_row)
                await session.flush()
        except Exception:
            # Concurrent worker already inserted product; re-query
            result = await session.execute(stmt)
            db_product = result.scalars().first()

    if db_product is not None:
        # Update mutable fields
        db_product.title = product.title
        db_product.brand = product.brand or db_product.brand
        db_product.shop_name = product.shop_name or db_product.shop_name
        db_product.shop_location = product.shop_location or db_product.shop_location
        db_product.product_url = product.product_url or db_product.product_url
        db_product.current_price = product.current_price
        db_product.original_price = product.original_price
        db_product.discount_percent = product.discount_percent
        db_product.historical_sold = product.historical_sold
        db_product.rating_star = product.rating_star
        db_product.rating_count = product.rating_count
        db_product.stock = product.stock
        db_product.status = product.status
        db_product.image_url = product.image_url
        db_product.raw_specs = product.raw_specs
        db_product.updated_at = now

        # Check last recorded price in history
        last_hist_stmt = (
            select(EcommercePriceHistory)
            .where(EcommercePriceHistory.product_id == db_product.id)
            .order_by(EcommercePriceHistory.recorded_at.desc())
            .limit(1)
        )
        last_hist_res = await session.execute(last_hist_stmt)
        last_hist = last_hist_res.scalars().first()

        if last_hist is None or last_hist.price != product.current_price:
            new_hist = EcommercePriceHistory(
                product_id=db_product.id,
                price=product.current_price,
                recorded_at=now,
            )
            session.add(new_hist)
            await session.flush()

    # Query 90-day history
    ninety_days_ago = now - timedelta(days=90)
    all_hist_stmt = (
        select(EcommercePriceHistory)
        .where(
            EcommercePriceHistory.product_id == db_product.id,
            EcommercePriceHistory.recorded_at >= ninety_days_ago,
        )
        .order_by(EcommercePriceHistory.recorded_at.asc())
        .limit(200)
    )
    all_hist_res = await session.execute(all_hist_stmt)
    history_records = list(all_hist_res.scalars().all())

    # If no records in 90 days, fetch the last known price before 90 days as baseline
    if not history_records:
        baseline_stmt = (
            select(EcommercePriceHistory)
            .where(
                EcommercePriceHistory.product_id == db_product.id,
                EcommercePriceHistory.recorded_at < ninety_days_ago,
            )
            .order_by(EcommercePriceHistory.recorded_at.desc())
            .limit(1)
        )
        baseline_res = await session.execute(baseline_stmt)
        baseline_row = baseline_res.scalars().first()
        if baseline_row is not None:
            history_records.append(baseline_row)

    snapshots: list[dict[str, Any]] = []
    sparkline: list[Decimal] = []

    for h in history_records:
        rec_dt = h.recorded_at
        if hasattr(rec_dt, "tzinfo") and rec_dt.tzinfo is None:
            rec_dt = rec_dt.replace(tzinfo=UTC)
        rec_time_str = rec_dt.isoformat() if hasattr(rec_dt, "isoformat") else str(rec_dt)
        snapshots.append({"price": h.price, "recorded_at": rec_time_str})
        sparkline.append(h.price)

    if not snapshots:
        snapshots.append({"price": product.current_price, "recorded_at": now.isoformat()})
        sparkline.append(product.current_price)

    return product, snapshots, sparkline


    return product, snapshots, sparkline


def build_track_price_history_executor(
    *, scraper_factory: Callable[[], ShopeeScraper] | None = None
) -> ExecutorFn:
    """Factory creating an executor for tracking Shopee price history."""
    make_scraper = scraper_factory or ShopeeScraper

    async def _execute(
        payload: EcommercePriceHistoryInput,
        ctx: CapabilityContext | None = None,
    ) -> EcommercePriceHistoryOutput:
        shop_id, item_id = _resolve_ids(payload)
        if item_id is None or shop_id is None:
            raise ValueError(
                "Must provide valid item_id and shop_id, or a valid Shopee product URL."
            )

        async with make_scraper() as scraper:
            product = await scraper.get_product_detail(item_id=item_id, shop_id=shop_id)

        if ctx is not None and ctx.session is not None:
            _, raw_snapshots, sparkline = await record_or_get_price_history(
                ctx.session, product, item_id, shop_id
            )
        else:
            now_iso = datetime.now(UTC).isoformat()
            raw_snapshots = [{"price": product.current_price, "recorded_at": now_iso}]
            sparkline = [product.current_price]

        prices = [s["price"] for s in raw_snapshots]
        min_price = min(prices)
        max_price = max(prices)
        current_price = product.current_price

        # Compute 90d change percentage
        first_price = prices[0]
        if first_price > Decimal("0"):
            change_pct = float(((current_price - first_price) / first_price) * Decimal("100"))
            change_pct = round(change_pct, 2)
        else:
            change_pct = 0.0

        snapshots = [
            PriceSnapshot(price=s["price"], recorded_at=str(s["recorded_at"]))
            for s in raw_snapshots
        ]

        item_summary = EcommerceProductItem(
            item_id=product.item_id,
            shop_id=product.shop_id,
            title=product.title,
            name=product.name,
            brand=product.brand,
            current_price=product.current_price,
            original_price=product.original_price,
            discount_percent=product.discount_percent,
            historical_sold=product.historical_sold,
            rating_star=product.rating_star,
            rating_count=product.rating_count,
            stock=product.stock,
            status=product.status,
            image_url=product.image_url,
            product_url=product.product_url,
            shop_name=product.shop_name,
            shop_location=product.shop_location,
            raw_specs=product.raw_specs,
        )

        return EcommercePriceHistoryOutput(
            product=item_summary,
            price_history=snapshots,
            min_price=min_price,
            max_price=max_price,
            current_price=current_price,
            price_change_percentage_90d=change_pct,
            sparkline_points=sparkline,
        )

    return _execute
