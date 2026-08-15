"""Shopee Vietnam Fast JSON In-House Scraper (Story 17.2 / AD-EC-1, AD-EC-4)."""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import quote_plus

import httpx

from .normalizer import (
    normalize_discount,
    normalize_price,
    normalize_product_url,
    normalize_rating,
)
from .schemas import ShopeeProduct, ShopeeSearchResponse

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
_SHOPEE_SEARCH_API = "https://shopee.vn/api/v4/search/search_items"
_SHOPEE_ITEM_GET_API = "https://shopee.vn/api/v4/item/get"


class ShopeeScraperError(Exception):
    """Base exception for Shopee scraping failures."""


class ShopeeRateLimitedError(ShopeeScraperError):
    """Raised when Shopee responds with HTTP 429 Rate Limit."""


class ShopeeBlockedError(ShopeeScraperError):
    """Raised when Shopee detects bot activity or returns HTTP 403."""


class ShopeeNotFoundError(ShopeeScraperError):
    """Raised when a product or endpoint returns 404 or empty data."""


class ShopeeScraper:
    """Fast JSON API Scraper for Shopee Vietnam without headless browsers."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        proxy_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.proxy_url = proxy_url
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                proxy=self.proxy_url,
            )
            self._owns_client = True

    async def close(self) -> None:
        """Close internal HTTP client if owned."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> ShopeeScraper:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _build_headers(self, custom_referer: str | None = None) -> dict[str, str]:
        """Construct realistic stealth headers imitating browser requests."""
        return {
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Shopee-Language": "vi",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": custom_referer or "https://shopee.vn/",
            "Sec-Ch-Ua": '"Chromium";v="127", "Not)A;Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    async def _send_request(
        self,
        url: str,
        params: dict[str, Any],
        referer: str | None = None,
    ) -> dict[str, Any]:
        """Send HTTP GET with exponential backoff for rate limits and transient errors."""
        headers = self._build_headers(referer)
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError as json_err:
                        # Could be HTML anti-bot challenge (Cloudflare/Datadome)
                        if "html" in response.text.lower() or "challenge" in response.text.lower():
                            if attempt == self.max_retries - 1:
                                raise ShopeeBlockedError("Shopee returned HTML antibot challenge page.") from json_err
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        raise ShopeeScraperError(f"Failed to parse JSON response: {json_err}") from json_err

                if response.status_code == 404:
                    raise ShopeeNotFoundError(f"Shopee endpoint returned 404 Not Found: {url}")

                if response.status_code == 429:
                    if attempt == self.max_retries - 1:
                        raise ShopeeRateLimitedError("Shopee rate limit exceeded (HTTP 429).")
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue

                if response.status_code == 403:
                    if attempt == self.max_retries - 1:
                        raise ShopeeBlockedError("Shopee blocked access / bot detected (HTTP 403).")
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue

                if response.status_code in (500, 502, 503, 504):
                    if attempt == self.max_retries - 1:
                        raise ShopeeScraperError(
                            f"Shopee server error HTTP {response.status_code}: {response.text[:200]}"
                        )
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue

                raise ShopeeScraperError(
                    f"Unexpected Shopee HTTP status {response.status_code}: {response.text[:200]}"
                )

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_error = net_err
                if attempt == self.max_retries - 1:
                    raise ShopeeScraperError(f"Network failure connecting to Shopee: {net_err}") from net_err
                await asyncio.sleep(0.5 * (2**attempt))


        if last_error:
            raise ShopeeScraperError(f"Shopee request failed: {last_error}") from last_error
        raise ShopeeScraperError("Shopee request failed with unknown error.")

    async def search_products(
        self,
        keyword: str,
        *,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ShopeeSearchResponse:
        """Search products using Shopee internal Fast JSON API (/api/v4/search/search_items)."""
        params: dict[str, Any] = {
            "by": "relevancy",
            "keyword": keyword,
            "limit": limit,
            "newest": offset,
            "order": "desc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }

        if min_price is not None and min_price > Decimal("0"):
            params["price_min"] = int(
                (min_price * Decimal("100000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        if max_price is not None and max_price > Decimal("0"):
            params["price_max"] = int(
                (max_price * Decimal("100000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )

        clean_keyword = keyword.strip()
        data = await self._send_request(
            _SHOPEE_SEARCH_API,
            params=params,
            referer=f"https://shopee.vn/search?keyword={quote_plus(clean_keyword)}",
        )

        raw_items = data.get("items") or []
        products: list[ShopeeProduct] = []

        for item_wrapper in raw_items:
            item_basic = item_wrapper.get("item_basic") or item_wrapper
            if not item_basic or "itemid" not in item_basic:
                continue

            item_id = item_basic["itemid"]
            shop_id = item_basic.get("shopid", 0)
            title = item_basic.get("name", "")
            raw_price = item_basic.get("price")
            raw_orig_price = item_basic.get("price_before_discount")

            current_price = normalize_price(raw_price) or Decimal("0.00")
            original_price = normalize_price(raw_orig_price)
            discount_pct = normalize_discount(
                current_price, original_price, item_basic.get("raw_discount")
            )

            rating_data = item_basic.get("item_rating") or {}
            rating_star = normalize_rating(rating_data.get("rating_star"))
            rating_counts = rating_data.get("rating_count")
            if isinstance(rating_counts, list):
                rating_count = sum(
                    int(x) for x in rating_counts if x is not None and str(x).isdigit()
                )
            else:
                rating_count = int(rating_counts or 0)

            stock = item_basic.get("stock", 0)
            status_code = item_basic.get("status", 1)
            status = "in_stock" if (stock > 0 and status_code == 1) else "out_of_stock"

            image_id = item_basic.get("image")
            image_url = f"https://cf.shopee.vn/file/{image_id}" if image_id else None
            product_url = normalize_product_url(shop_id, item_id, title)

            products.append(
                ShopeeProduct(
                    item_id=item_id,
                    shop_id=shop_id,
                    title=title,
                    name=title,
                    brand=item_basic.get("brand"),
                    current_price=current_price,
                    original_price=original_price,
                    discount_percent=discount_pct,
                    historical_sold=item_basic.get("historical_sold", 0),
                    rating_star=rating_star,
                    rating_count=rating_count,
                    stock=stock,
                    status=status,
                    image_url=image_url,
                    product_url=product_url,
                    shop_location=item_basic.get("shop_location"),
                    raw_specs=item_basic,
                )
            )

        total_count = data.get("total_count") if data.get("total_count") is not None else len(products)
        has_more = (offset + limit) < total_count

        return ShopeeSearchResponse(
            items=products,
            total_count=total_count,
            has_more=has_more,
        )

    async def get_product_detail(self, item_id: int, shop_id: int) -> ShopeeProduct:
        """Fetch full product details from Shopee internal API (/api/v4/item/get)."""
        params = {"itemid": item_id, "shopid": shop_id}
        data = await self._send_request(
            _SHOPEE_ITEM_GET_API,
            params=params,
            referer=f"https://shopee.vn/product/{shop_id}/{item_id}",
        )

        item_data = data.get("data") or {}
        if not item_data or "itemid" not in item_data:
            raise ShopeeNotFoundError(f"Shopee product {item_id} (shop: {shop_id}) not found.")

        title = item_data.get("name", "")
        raw_price = item_data.get("price")
        raw_orig_price = item_data.get("price_before_discount")

        current_price = normalize_price(raw_price) or Decimal("0.00")
        original_price = normalize_price(raw_orig_price)
        discount_pct = normalize_discount(
            current_price, original_price, item_data.get("raw_discount")
        )

        rating_data = item_data.get("item_rating") or {}
        rating_star = normalize_rating(rating_data.get("rating_star"))
        rating_counts = rating_data.get("rating_count")
        if isinstance(rating_counts, list):
            rating_count = sum(
                int(x) for x in rating_counts if x is not None and str(x).isdigit()
            )
        else:
            rating_count = int(rating_counts or 0)

        stock = item_data.get("stock", 0)
        status_code = item_data.get("status", 1)
        status = "in_stock" if (stock > 0 and status_code == 1) else "out_of_stock"

        image_id = item_data.get("image")
        image_url = f"https://cf.shopee.vn/file/{image_id}" if image_id else None
        product_url = normalize_product_url(shop_id, item_id, title)

        return ShopeeProduct(
            item_id=item_id,
            shop_id=shop_id,
            title=title,
            name=title,
            brand=item_data.get("brand"),
            current_price=current_price,
            original_price=original_price,
            discount_percent=discount_pct,
            historical_sold=item_data.get("historical_sold", 0),
            rating_star=rating_star,
            rating_count=rating_count,
            stock=stock,
            status=status,
            image_url=image_url,
            product_url=product_url,
            shop_location=item_data.get("shop_location"),
            raw_specs=item_data,
        )
