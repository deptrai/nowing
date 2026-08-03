"""Fetch Muaban.net BĐS listing pages and extract the embedded Next.js data."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import config
from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

ORIGIN = "https://muaban.net"


try:
    from scrapling.engines._browsers._stealth import AsyncStealthySession
except Exception as exc:  # pragma: no cover - defensive for non-browser envs
    AsyncStealthySession = None
    logger.warning("Muaban BĐS could not import AsyncStealthySession: %s", exc)


class MuabanBdsAccessBlockedError(RuntimeError):
    """Raised when Muaban.net blocks access (Cloudflare/403/500)."""


class MuabanBdsDecodeError(ValueError):
    """Raised when a page response cannot be parsed."""


class MuabanBdsRateLimitedError(RuntimeError):
    """Raised when Muaban.net returns 429."""


_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _page_delay() -> float:
    return max(0.0, getattr(config, "MUABAN_BDS_PAGE_DELAY_S", 1.0))


def _decode_html(html: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise MuabanBdsDecodeError("__NEXT_DATA__ not found in response")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise MuabanBdsDecodeError("__NEXT_DATA__ is not valid JSON") from exc


def extract_next_data(html: str | bytes) -> dict[str, Any]:
    """Parse the Next.js payload out of a Muaban HTML response."""
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return _decode_html(html)


async def fetch_page(
    url: str,
    *,
    session: Any | None = None,
    timeout: int = 45_000,
    solve_cloudflare: bool = True,
) -> dict[str, Any]:
    """Fetch one Muaban page and return the decoded ``__NEXT_DATA__`` JSON.

    ``session`` is an optional pre-opened ``AsyncStealthySession``.  When
    omitted, a temporary session is opened and closed for this one request.
    """
    proxy = get_proxy_url()
    extra_headers = {
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
    }

    own_session = False
    if session is None:
        if AsyncStealthySession is None:
            raise MuabanBdsAccessBlockedError(
                "AsyncStealthySession unavailable; Muaban requires a browser"
            )
        session = AsyncStealthySession(
            headless=True,
            solve_cloudflare=solve_cloudflare,
            real_chrome=True,
            proxy=proxy,
            disable_resources=True,
            extra_headers=extra_headers,
        )
        own_session = True
        await session.start()

    try:
        started = time.perf_counter()
        response = await session.fetch(url, timeout=timeout)
        fetch_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[muaban_bds][perf] url=%s status=%s fetch_ms=%.1f",
            url,
            response.status,
            fetch_ms,
        )

        if response.status == 429:
            raise MuabanBdsRateLimitedError(f"{url} returned 429")
        if response.status in {403, 503, 504} | set(range(500, 600)):
            raise MuabanBdsAccessBlockedError(f"{url} returned {response.status}")

        try:
            body = response.body
        except AttributeError:
            body = response.text.encode("utf-8", errors="replace")

        if response.status == 404:
            return {"notFound": True}

        return extract_next_data(body)
    finally:
        if own_session and hasattr(session, "close"):
            try:
                await session.close()
            except Exception as close_exc:
                logger.warning("Muaban session close failed: %s", close_exc)
