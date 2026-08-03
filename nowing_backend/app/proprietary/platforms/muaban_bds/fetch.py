"""Fetch Muaban.net BĐS listing pages and extract the embedded Next.js data."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import config
from app.services.scraper_platform_account_service import cookie_string_to_dict
from app.utils.proxy import get_proxy_url

try:
    from scrapling.fetchers import AsyncFetcher
except Exception:  # pragma: no cover - defensive for minimal envs
    AsyncFetcher = None

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


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


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

def _extract_detail_phone(next_data: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Pull phone fields from a Muaban detail ``__NEXT_DATA__`` payload."""
    page_props = next_data.get("props", {}).get("pageProps", {})
    classified = page_props.get("classified") or page_props.get("estateSell") or page_props.get("estateRent") or {}
    if not isinstance(classified, dict):
        return None, None, None
    phone = _normalize_whitespace(classified.get("phone"))
    phone_display = _normalize_whitespace(classified.get("phone_display"))
    phone_enc = _normalize_whitespace(classified.get("phone_enc"))
    return phone, phone_display, phone_enc


async def fetch_detail_phone(
    session: Any,
    detail_url: str,
    *,
    credentials: dict[str, Any] | None = None,
    timeout: int = 45_000,
    solve_cloudflare: bool = True,
) -> tuple[str | None, str | None, str | None]:
    """Fetch a Muaban detail page and return the best phone info available.

    The full phone number is served by a server-side API call that is
    protected by Cloudflare and, in practice, requires an authenticated
    session.  We attempt it best-effort but fall back to ``phone_display``
    (the masked number) when the API does not cooperate.
    """
    page_data = await fetch_page(
        detail_url,
        session=session,
        timeout=timeout,
        solve_cloudflare=solve_cloudflare,
    )
    if page_data.get("notFound") or not isinstance(page_data, dict):
        return None, None, None

    phone, phone_display, phone_enc = _extract_detail_phone(page_data)
    if phone:
        return phone, phone_display, phone_enc

    # Best-effort attempt to decrypt the phone server-side.
    if phone_enc and AsyncFetcher is not None:
        try:
            listing_id = page_data.get("props", {}).get("pageProps", {}).get("classified", {}).get("id")
            payload = {
                "id": listing_id,
                "phone_enc": phone_enc,
                "site_id": 1,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": detail_url,
            }
            fetch_kwargs: dict[str, Any] = {"timeout": 20}
            if credentials:
                token = credentials.get("token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                cookie_string = credentials.get("cookies")
                if cookie_string:
                    fetch_kwargs["cookies"] = cookie_string_to_dict(cookie_string)
            res = await AsyncFetcher.post(
                "https://muaban.net/api/v1/phone/show",
                json=payload,
                headers=headers,
                **fetch_kwargs,
            )
            if res.status == 200:
                try:
                    data = json.loads(res.body.decode("utf-8"))
                    full = _normalize_whitespace(data.get("phone"))
                    if full:
                        return full, phone_display, phone_enc
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            else:
                logger.info(
                    "Muaban phone API returned %s for %s; full phone unavailable without auth",
                    res.status,
                    detail_url,
                )
        except Exception as exc:
            logger.debug("Muaban phone API attempt failed for %s: %s", detail_url, exc)

    return phone or phone_display or None, phone_display, phone_enc
