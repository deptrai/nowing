"""Walmart-specific HTTP fetching helpers.

These live in a dedicated module so the main scraper does not need to import
``app.proprietary.web_crawler`` at the top level, which would create a
circular import during the capability registry bootstrap.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from scrapling.fetchers import StealthyFetcher

from app.config import config
from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

_MAX_PROXY_ATTEMPTS = 3

_BLOCK_MARKERS = (
    "robot or human",
    "px-captcha",
    "/blocked",
    "perimeterx",
    "please verify you are a human",
    "access denied",
    "blocked",
)


def _looks_like_html(content: str | None) -> bool:
    if not content:
        return False
    sample = content[:5000].lower()
    return "<!doctype" in sample or "<html" in sample or "__next_data__" in sample


def _is_blocked(html: str | None, status: int | None) -> bool:
    """Detect Walmart anti-bot interstitials."""
    if status in {202, 412, 429, 503}:
        return True
    text = (html or "").lower()[:200_000]
    return any(marker in text for marker in _BLOCK_MARKERS)


async def _stealthy_fetch_html(url: str) -> str | None:
    """Fetch raw HTML with StealthyFetcher, rotating proxies on block."""
    from app.proprietary.web_crawler.stealth import (
        build_stealthy_kwargs,
        get_stealth_config,
    )

    kwargs: dict[str, Any] = {
        "headless": True,
        "network_idle": True,
        "block_ads": True,
        "solve_cloudflare": True,
        "proxy": None,
    }
    kwargs.update(build_stealthy_kwargs(get_stealth_config()))

    for attempt in range(1, _MAX_PROXY_ATTEMPTS + 1):
        kwargs["proxy"] = get_proxy_url()
        try:
            page = await asyncio.to_thread(StealthyFetcher.fetch, url, **kwargs)
        except Exception as exc:
            logger.warning("Walmart StealthyFetcher attempt %s failed: %s", attempt, exc)
            if attempt == _MAX_PROXY_ATTEMPTS:
                return None
            continue

        html = getattr(page, "html_content", None) or ""
        status = int(getattr(page, "status", 0) or 0)
        if not _is_blocked(html, status):
            return html

        logger.info("Walmart blocked on attempt %s for %s; rotating proxy", attempt, url)
        if attempt < _MAX_PROXY_ATTEMPTS:
            await asyncio.sleep(config.WALMART_PAGE_DELAY_S)

    return None


async def _fetch_html(url: str) -> str | None:
    """Fetch page HTML, preferring the crawler and falling back to StealthyFetcher."""
    from app.proprietary.web_crawler.connector import WebCrawlerConnector

    connector = WebCrawlerConnector()
    outcome = await connector.crawl_url(url)
    if outcome.status == "success" and outcome.result:
        content = outcome.result.get("content") or ""
        if _looks_like_html(content) and not _is_blocked(content, None):
            return content

    return await _stealthy_fetch_html(url)
