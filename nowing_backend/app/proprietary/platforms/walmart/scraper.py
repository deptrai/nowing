"""Walmart product and reviews scraper.

The public site is a Next.js app, so the primary parse target is the
``__NEXT_DATA__`` JSON embedded in the HTML. Search results fall back to lxml
selectors when the JSON is not present, and StealthyFetcher is used as a
fallback when the crawler is blocked.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urljoin, urlsplit

from lxml import html as lxml_html

from app.config import config

from .fetch import _fetch_html

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.walmart.com"
_SEARCH_PATH = "/search"
_REVIEWS_PATH = "/reviews/product"

_MAX_SEARCH_PAGES = 5

_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")
_ID_RE = re.compile(r"/(?:ip|dp)/[^/]+/(\d+)")  # /ip/slug/123456789
_ID_RE_FALLBACK = re.compile(r"/(?:ip|dp)/(\d+)")  # /ip/123456789


def _degraded(reason: str, *, cost_micros: int = 0) -> dict[str, Any]:
    return {
        "items": [],
        "cost_micros": cost_micros,
        "degraded": True,
        "degradation_reason": reason,
        "total_items": 0,
    }


def _absolute(url: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    return urljoin(url, path)


def _extract_product_id(url: str) -> str | None:
    """Pull a numeric Walmart product id from a product or review URL."""
    for pattern in (_ID_RE, _ID_RE_FALLBACK):
        match = pattern.search(url)
        if match:
            return match.group(1)
    parts = urlsplit(url).path.rstrip("/").split("/")
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 8:
        return parts[-1]
    return None


def _build_search_url(keyword: str, page: int) -> str:
    return f"{_BASE_URL}{_SEARCH_PATH}?q={quote_plus(keyword)}&page={page}"


def _build_reviews_url(product_id: str, page: int) -> str:
    return f"{_BASE_URL}{_REVIEWS_PATH}/{product_id}?page={page}"


def _dig(data: Any, *keys: str) -> Any:
    """Defensive nested dict walk; returns None on any missing key."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_next_data(html: str) -> dict[str, Any] | None:
    """Parse the ``__NEXT_DATA__`` JSON blob from a Walmart page."""
    if not html:
        return None

    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start == -1:
        marker = '<script id="__NEXT_DATA__"'
        start = html.find(marker)
        if start == -1:
            return None
        tag_end = html.find(">", start)
        if tag_end == -1:
            return None
        start = tag_end + 1
    else:
        start += len(marker)

    end = html.find("</script>", start)
    if end == -1:
        return None

    blob = html[start:end].strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError as exc:
        logger.debug("Walmart __NEXT_DATA__ JSON decode failed: %s", exc)
        return None


def _price(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    text = str(value).replace(",", "")
    match = _PRICE_RE.search(text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def _currency(price_string: str | None, default: str = "USD") -> str | None:
    if not price_string:
        return default
    text = price_string.upper()
    if "$" in price_string or "USD" in text:
        return "USD"
    if "€" in price_string or "EUR" in text:
        return "EUR"
    if "£" in price_string or "GBP" in text:
        return "GBP"
    return default


def _normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    """Flatten one review object from ``__NEXT_DATA__`` into the wire shape."""
    text_parts: list[str] = []
    for key in ("reviewText", "text", "reviewTitle", "title"):
        part = review.get(key)
        if part and str(part).strip():
            text_parts.append(str(part).strip())
    text = " ".join(text_parts)

    rating = review.get("rating")
    if rating is None:
        rating = _dig(review, "overallRating", "value")
    if rating is None:
        rating = _dig(review, "ratingValue")

    verified = review.get("verifiedPurchase") or review.get("verified") or False
    date = review.get("submissionTime") or review.get("reviewDate") or review.get("date")

    return {
        "text": text,
        "rating": _price(rating),
        "date": date,
        "verified": bool(verified),
    }


def _extract_product_reviews(data: dict[str, Any], max_reviews: int) -> list[dict[str, Any]]:
    """Pull the review sample embedded in a product page payload."""
    reviews: list[dict[str, Any]] = []
    raw = _dig(data, "props", "pageProps", "initialData", "data", "reviews")
    if not isinstance(raw, dict):
        return reviews

    for key in ("reviews", "reviewList", "customerReviews", "items"):
        source = raw.get(key)
        if isinstance(source, list):
            for review in source[:max_reviews]:
                if isinstance(review, dict):
                    reviews.append(_normalize_review(review))
            break
    return reviews


def _parse_product_from_json(data: dict[str, Any], url: str) -> dict[str, Any] | None:
    """Convert the product JSON into the normalized product dict."""
    product = _dig(data, "props", "pageProps", "initialData", "data", "product")
    if not isinstance(product, dict):
        return None

    name = product.get("name")
    if not name:
        return None

    product_id = product.get("itemId") or product.get("id") or product.get("usItemId")
    price_info = product.get("priceInfo") or {}
    current_price = price_info.get("currentPrice") or {}

    price_raw = current_price.get("priceString") or current_price.get("currencyUnit")
    price_value = _price(current_price.get("price"))
    currency = _currency(
        current_price.get("priceString") or current_price.get("currencyUnit"),
        price_info.get("currencyCode") or "USD",
    )

    rating = _price(product.get("averageRating"))
    if rating is None:
        rating = _price(_dig(product, "rating", "averageRating"))

    seller = product.get("sellerName")
    if not seller:
        seller = product.get("sellerDisplayName")
    if not seller and product.get("sellerId") == "0":
        seller = "Walmart"

    availability = product.get("availabilityStatus")
    if not availability:
        availability = product.get("availability")

    image_url: str | None = None
    image_info = product.get("imageInfo") or {}
    for key in ("primaryImageUrl", "primaryImage", "thumbnailUrl", "allImages"):
        value = image_info.get(key)
        if isinstance(value, str) and value:
            image_url = value
            break
        if isinstance(value, dict) and value.get("url"):
            image_url = value["url"]
            break
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict) and first.get("url"):
                image_url = first["url"]
                break
            if isinstance(first, str):
                image_url = first
                break

    return {
        "id": f"walmart:{product_id}" if product_id else "walmart:unknown",
        "title": name,
        "price": price_value,
        "price_raw": price_raw,
        "currency": currency,
        "rating": rating,
        "seller": seller,
        "availability": availability,
        "product_url": url,
        "image_url": _absolute(url, image_url),
        "review_summary": _extract_product_reviews(data, 5),
        "source": "walmart",
        "source_url": url,
        "is_active": True,
    }


def _parse_product_html(html: str, url: str) -> dict[str, Any] | None:
    """Last-resort HTML selector parse when ``__NEXT_DATA__`` is unavailable."""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return None

    title = None
    for selector in (
        '//h1[@data-automation-id="product-title"]',
        "//h1",
        "//*[contains(@class,'prod-ProductTitle')]",
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            title = " ".join(el[0].itertext()).strip()
            if title:
                break

    if not title:
        return None

    product_id = _extract_product_id(url)
    price_text = None
    for selector in (
        '//span[@itemprop="price"]',
        '//span[@data-automation-id="product-price"]',
        "//*[contains(@class,'price-current')]",
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            price_text = " ".join(el[0].itertext()).strip()
            if price_text:
                break

    availability = None
    for selector in (
        '//span[@data-automation-id="product-availability"]',
        "//*[contains(@class,'prod-availability')]",
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            availability = " ".join(el[0].itertext()).strip()
            if availability:
                break

    seller = None
    for selector in (
        '//a[@data-automation-id="product-seller"]',
        "//*[contains(@class,'seller-name')]",
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            seller = " ".join(el[0].itertext()).strip()
            if seller:
                break

    rating = None
    for selector in (
        '//span[@data-automation-id="product-rating"]',
        "//*[contains(@class,'rating-score')]",
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            rating = _price(" ".join(el[0].itertext()))
            if rating is not None:
                break

    image_url = None
    for selector in (
        '//img[@data-automation-id="product-image"]',
        '//meta[@property="og:image"]',
    ):
        try:
            el = root.xpath(selector)
        except Exception:
            continue
        if el:
            image_url = el[0].get("src") or el[0].get("content")
            if image_url:
                break

    return {
        "id": f"walmart:{product_id}" if product_id else "walmart:unknown",
        "title": title,
        "price": _price(price_text),
        "price_raw": price_text,
        "currency": _currency(price_text),
        "rating": rating,
        "seller": seller,
        "availability": availability,
        "product_url": url,
        "image_url": _absolute(url, image_url),
        "review_summary": [],
        "source": "walmart",
        "source_url": url,
        "is_active": True,
    }


def _parse_search_from_json(data: dict[str, Any], url: str) -> list[dict[str, Any]]:
    """Parse search result items from the Next.js JSON payload."""
    items: list[dict[str, Any]] = []
    search_result = _dig(data, "props", "pageProps", "initialData", "searchResult")
    if not isinstance(search_result, dict):
        return items

    stacks = search_result.get("itemStacks") or [search_result]
    for stack in stacks:
        if not isinstance(stack, dict):
            continue
        products = stack.get("items") or []
        for product in products:
            if not isinstance(product, dict):
                continue
            if product.get("__typename") not in (None, "Product"):
                continue

            product_id = product.get("id") or product.get("itemId") or product.get("usItemId")
            name = product.get("name") or product.get("title")
            if not name:
                continue

            price_info = product.get("priceInfo") or {}
            current_price = price_info.get("currentPrice") or {}
            price_raw = current_price.get("priceString")
            price = _price(current_price.get("price"))
            currency = _currency(price_raw, price_info.get("currencyCode") or "USD")

            rating = _price(product.get("averageRating"))

            product_url = product.get("productPageUrl") or product.get("url")
            if product_url:
                product_url = _absolute(url, product_url)

            image_url = None
            image_info = product.get("imageInfo") or {}
            for key in ("thumbnailUrl", "primaryImageUrl", "primaryImage"):
                value = image_info.get(key)
                if value:
                    image_url = value
                    break

            source_url = product_url or url
            items.append(
                {
                    "id": f"walmart:{product_id}" if product_id else f"walmart:{hash(name) & 0x7FFFFFFF}",
                    "title": name,
                    "price": price,
                    "price_raw": price_raw,
                    "currency": currency,
                    "rating": rating,
                    "seller": None,
                    "availability": None,
                    "product_url": product_url,
                    "image_url": _absolute(url, image_url),
                    "review_summary": [],
                    "source": "walmart",
                    "source_url": source_url,
                    "is_active": True,
                }
            )
    return items


def _parse_search_html(html: str, url: str) -> list[dict[str, Any]]:
    """Parse search result cards with lxml selectors."""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return []

    cards = root.xpath('//div[@data-automation-id="product-tile"]')
    if not cards:
        cards = root.xpath(
            '//div[contains(@data-automation-id,"product-tile")]'
            ' | //div[contains(@class,"search-result-gridview")]'
        )

    items: list[dict[str, Any]] = []
    for card in cards:
        title_link = card.xpath('.//a[@data-automation-id="product-title"]')
        if not title_link:
            title_link = card.xpath(".//h3/a | .//h4/a")
        if not title_link:
            continue

        a = title_link[0]
        title = a.get("aria-label") or " ".join(a.itertext()).strip()
        href = a.get("href") or ""
        product_url = _absolute(url, href) if href else None
        product_id = _extract_product_id(product_url) if product_url else None

        price_text = None
        for selector in (
            './/span[@data-automation-id="product-price"]//text()',
            './/span[contains(@class,"price-current")]//text()',
            './/span[contains(@class,"price-main")]//text()',
        ):
            el = card.xpath(selector)
            if el:
                price_text = "".join(t.strip() for t in el if t.strip())
                if price_text:
                    break

        rating = None
        for selector in (
            './/span[@data-automation-id="product-rating"]//text()',
            './/span[contains(@class,"rating-score")]//text()',
        ):
            el = card.xpath(selector)
            if el:
                rating = _price("".join(t.strip() for t in el if t.strip()))
                if rating is not None:
                    break

        image_url = None
        for selector in (
            './/img[@data-automation-id="product-image"]',
            ".//img",
        ):
            el = card.xpath(selector)
            if el:
                image_url = el[0].get("src")
                if image_url:
                    break

        source_url = product_url or url
        items.append(
            {
                "id": f"walmart:{product_id}" if product_id else f"walmart:{hash(title) & 0x7FFFFFFF}",
                "title": title,
                "price": _price(price_text),
                "price_raw": price_text,
                "currency": _currency(price_text),
                "rating": rating,
                "seller": None,
                "availability": None,
                "product_url": product_url,
                "image_url": _absolute(url, image_url),
                "review_summary": [],
                "source": "walmart",
                "source_url": source_url,
                "is_active": True,
            }
        )

    return items


def _parse_search_page(html: str, url: str) -> list[dict[str, Any]]:
    """Best-effort search parse: JSON first, lxml fallback."""
    data = _extract_next_data(html)
    if data:
        items = _parse_search_from_json(data, url)
        if items:
            return items
    return _parse_search_html(html, url)


def _parse_product_page(html: str, url: str) -> dict[str, Any] | None:
    """Best-effort product parse: ``__NEXT_DATA__`` first, lxml fallback."""
    data = _extract_next_data(html)
    if data:
        product = _parse_product_from_json(data, url)
        if product:
            return product
    return _parse_product_html(html, url)


def _parse_reviews_page(html: str, url: str) -> list[dict[str, Any]]:
    """Extract review items from a dedicated reviews page."""
    data = _extract_next_data(html)
    if not data:
        return []
    return _extract_product_reviews(data, 100)


async def _scrape_product(url: str, max_reviews: int) -> dict[str, Any] | None:
    html = await _fetch_html(url)
    if not html:
        return None
    product = _parse_product_page(html, url)
    if not product:
        return None
    if max_reviews > 0 and not product.get("review_summary"):
        product_id = _extract_product_id(url)
        if product_id:
            reviews_html = await _fetch_html(_build_reviews_url(product_id, 1))
            if reviews_html:
                reviews = _parse_reviews_page(reviews_html, url)
                product["review_summary"] = reviews[:max_reviews]
    return product


async def _scrape_search(
    keyword: str,
    start_page: int,
    max_items: int,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    cost_micros = 0
    page = start_page
    pages_fetched = 0

    while len(items) < max_items and pages_fetched < _MAX_SEARCH_PAGES:
        url = _build_search_url(keyword, page)
        html = await _fetch_html(url)
        pages_fetched += 1

        if not html:
            break

        cost_micros += config.WALMART_SCRAPE_MICROS_PER_ITEM * 3
        cards = _parse_search_page(html, url)
        if not cards:
            if pages_fetched == 1:
                return _degraded("no_results_found")
            break

        for card in cards:
            if len(items) >= max_items:
                break
            cost_micros += config.WALMART_SCRAPE_MICROS_PER_ITEM
            items.append(card)
            await asyncio.sleep(config.WALMART_PAGE_DELAY_S)

        if len(cards) < 5:
            break

        page += 1

    if not items:
        return _degraded("no_results_found", cost_micros=cost_micros)

    return {
        "items": items,
        "cost_micros": cost_micros,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(items),
    }


def _is_product_url(url: str) -> bool:
    return "/ip/" in url or "/dp/" in url


async def scrape_walmart(params: dict[str, Any]) -> dict[str, Any]:
    """Public entry point for ``walmart.scrape``."""
    max_items = int(params.get("max_items", config.WALMART_MAX_ITEMS) or 0)
    if max_items <= 0:
        return _degraded("invalid_input")

    max_reviews = int(params.get("max_reviews", 5) or 0)
    url = (params.get("url") or "").strip()
    keyword = (params.get("keyword") or "").strip()

    if url and _is_product_url(url):
        product = await _scrape_product(url, max_reviews)
        if not product:
            return _degraded("product_not_found")
        cost_micros = config.WALMART_SCRAPE_MICROS_PER_ITEM
        return {
            "items": [product],
            "cost_micros": cost_micros,
            "degraded": False,
            "degradation_reason": None,
            "total_items": 1,
        }

    if not keyword:
        return _degraded("invalid_input")

    start_page = int(params.get("page", 1) or 1)
    return await _scrape_search(keyword, start_page, max_items)


async def scrape_walmart_reviews(params: dict[str, Any]) -> dict[str, Any]:
    """Public entry point for ``walmart.reviews``."""
    url = (params.get("url") or "").strip()
    if not url or not _is_product_url(url):
        return _degraded("invalid_input")

    max_reviews = int(params.get("max_reviews", config.WALMART_MAX_REVIEWS) or 0)
    if max_reviews <= 0:
        return _degraded("invalid_input")

    product_id = _extract_product_id(url)
    if not product_id:
        return _degraded("product_not_found")

    reviews: list[dict[str, Any]] = []
    cost_micros = 0
    page = 1
    empty_count = 0

    while len(reviews) < max_reviews and empty_count < 2:
        reviews_url = _build_reviews_url(product_id, page)
        html = await _fetch_html(reviews_url)
        if not html:
            break

        cost_micros += config.WALMART_REVIEW_MICROS_PER_ITEM
        page_reviews = _parse_reviews_page(html, reviews_url)
        if not page_reviews:
            empty_count += 1
            break

        for review in page_reviews:
            if len(reviews) >= max_reviews:
                break
            reviews.append(review)
            cost_micros += config.WALMART_REVIEW_MICROS_PER_ITEM

        if len(page_reviews) < 5:
            break

        page += 1
        await asyncio.sleep(config.WALMART_PAGE_DELAY_S)

    if not reviews:
        return _degraded("reviews_not_found", cost_micros=cost_micros)

    return {
        "items": reviews,
        "cost_micros": cost_micros,
        "degraded": False,
        "degradation_reason": None,
        "total_items": len(reviews),
    }
