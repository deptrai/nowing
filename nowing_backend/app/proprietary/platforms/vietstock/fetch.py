"""Fetch Vietstock stock quotes and financial statements.

Demo mode is the default because Vietstock endpoints are not publicly
documented and require an anti-forgery token from the site. Set
``VIETSTOCK_DEMO_MODE=false`` to hit the live POST APIs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from app.config import config

from .schemas import VietstockScrapeInput

logger = logging.getLogger(__name__)

# Default Vietstock endpoints discovered by real browser traffic.
_QUOTE_URL = "https://finance.vietstock.vn/company/tradinginfo"
_FINANCIAL_URL = "https://finance.vietstock.vn/data/financeinfo"
_REFRESH_URL = "https://finance.vietstock.vn"

# Bounded retry/backoff for transient 429 responses.
_MAX_429_RETRIES = 2
_BACKOFF_BASE_S = 1.0

# Headers that mimic a real browser so the data endpoints return JSON.
_VIETSTOCK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://finance.vietstock.vn/",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://finance.vietstock.vn",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Process-local rate-limit state. Default 20 req/min -> 1 request every 3 s.
_throttle_lock = asyncio.Lock()
_last_request_at: float | None = None

# Mutable process-local cookie jar.
# ponytail: process-local jar is sufficient for demo and single-credential
# deployments. Replace with ScraperPlatformAccountRotator when admin-managed
# cookie pools are required (see Story 15.2 review, deferred).
_session_cookie: str | None = None


class VietstockRateLimitedError(RuntimeError):
    """Raised when Vietstock returns 429."""


class VietstockAccessBlockedError(RuntimeError):
    """Raised when Vietstock blocks or returns an unexpected error."""


class VietstockDecodeError(ValueError):
    """Raised when a Vietstock response cannot be decoded as JSON."""


class VietstockAuthRefreshError(RuntimeError):
    """Raised when cookie-based auth cannot be refreshed."""


def _rate_limit_interval() -> float:
    """Seconds between requests for the configured per-process rate limit."""
    rate = getattr(config, "VIETSTOCK_RATE_LIMIT_RPS", 1 / 3)
    rps = float(rate) if rate is not None else 1 / 3
    rps = max(0.0, rps)
    return 1.0 / max(rps, 1e-6)


async def _throttle() -> None:
    """Wait until at least the rate-limit interval has passed.

    Uses a process-local lock so concurrent coroutines share one throttle.
    """
    global _last_request_at

    async with _throttle_lock:
        now = time.perf_counter()
        if _last_request_at is not None:
            wait = max(0.0, _rate_limit_interval() - (now - _last_request_at))
            if wait:
                logger.debug("vietstock throttle: sleeping %.2f s", wait)
                await asyncio.sleep(wait)
        _last_request_at = time.perf_counter()


def _timeout() -> float:
    timeout = getattr(config, "VIETSTOCK_TIMEOUT_S", 15.0)
    return float(timeout) if timeout is not None else 15.0


def _demo_mode() -> bool:
    return bool(getattr(config, "VIETSTOCK_DEMO_MODE", True))


def _quote_url() -> str:
    return getattr(config, "VIETSTOCK_QUOTE_URL", _QUOTE_URL)


def _financial_url() -> str:
    return getattr(config, "VIETSTOCK_FINANCIAL_URL", _FINANCIAL_URL)


def _get_cookie() -> str | None:
    """Return the current process-local cookie or the env cookie."""
    if _session_cookie:
        return _session_cookie
    cookie = getattr(config, "VIETSTOCK_SESSION_COOKIE", "")
    return cookie or None


def _set_cookie(value: str | None) -> None:
    """Update the process-local cookie."""
    global _session_cookie
    _session_cookie = value or None


# Anti-forgery token cache. The token is embedded in every Vietstock page
# and is required for POSTing to the data endpoints.
_verification_token: str | None = None


async def _get_verification_token() -> str:
    """Fetch and cache a fresh ``__RequestVerificationToken`` and session cookie.

    Vietstock inlines the token in the HTML of the landing page and also sets
    a ``__RequestVerificationToken`` cookie that must accompany POSTs. We
    request the landing page, extract both, and cache them process-locally.
    """
    global _verification_token, _session_cookie

    if _verification_token:
        return _verification_token

    await _throttle()
    headers = _VIETSTOCK_HEADERS.copy()
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    async with httpx.AsyncClient(
        timeout=_timeout(),
        headers=headers,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(_REFRESH_URL)
        except httpx.TimeoutException as exc:
            raise VietstockAuthRefreshError(
                f"timeout fetching verification token from {_REFRESH_URL}"
            ) from exc
        except httpx.ConnectError as exc:
            raise VietstockAuthRefreshError(
                f"cannot connect to {_REFRESH_URL} for token"
            ) from exc

    if resp.status_code >= 400:
        raise VietstockAuthRefreshError(
            f"token fetch failed: {_REFRESH_URL} returned {resp.status_code}"
        )

    token = _extract_verification_token(resp.text)
    if not token:
        raise VietstockAuthRefreshError(
            f"no __RequestVerificationToken found in {_REFRESH_URL}"
        )

    # Persist cookies (especially __RequestVerificationToken and session) so
    # subsequent POSTs are authenticated.
    if resp.cookies:
        _session_cookie = "; ".join(
            f"{name}={value}" for name, value in resp.cookies.items()
        )
    else:
        set_cookie = resp.headers.get("set-cookie")
        if set_cookie:
            _session_cookie = set_cookie.split(";")[0].strip()

    _verification_token = token
    return token


def _extract_verification_token(html: str) -> str | None:
    """Parse a ``__RequestVerificationToken`` from an HTML page."""
    import re

    # Prefer an explicit hidden input. Vietstock omits quotes on some pages,
    # so match value both with and without surrounding quotes.
    m = re.search(
        r'<input[^>]+name=["\']?__RequestVerificationToken["\']?[^>]*>',
        html,
        re.IGNORECASE,
    )
    if m:
        value_m = re.search(r'value=["\']?([^\s"\'<>]+)', m.group(0), re.IGNORECASE)
        if value_m:
            return value_m.group(1)

    # Fallback: token assigned in inline scripts.
    m = re.search(r"__RequestVerificationToken\s*=\s*['\"]([^'\"]+)['\"]", html)
    if m:
        return m.group(1)
    return None


def _has_live_credentials() -> bool:
    """Return True when both API URLs are configured.

    The real Vietstock endpoints only require a per-request anti-forgery
    token, not a session cookie, so we only check that URLs are present.
    """
    return bool(
        _quote_url()
        and _financial_url()
    )


async def _refresh_cookie() -> str:
    """Try to obtain a fresh session cookie from Vietstock.

    The live site uses session cookies for API access. This helper makes a
    lightweight request to the landing page and extracts any ``Set-Cookie``
    headers. If no cookie is returned, auth refresh is considered failed.
    """
    url = _REFRESH_URL
    cookie = _get_cookie()
    headers = _VIETSTOCK_HEADERS.copy()
    if cookie:
        headers["Cookie"] = cookie

    await _throttle()
    async with httpx.AsyncClient(
        timeout=_timeout(),
        headers=headers,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.TimeoutException as exc:
            raise VietstockAuthRefreshError(
                f"timeout refreshing cookie from {url}"
            ) from exc
        except httpx.ConnectError as exc:
            raise VietstockAuthRefreshError(
                f"cannot connect to {url} for cookie refresh"
            ) from exc

    if resp.status_code >= 400:
        raise VietstockAuthRefreshError(
            f"cookie refresh failed: {url} returned {resp.status_code}"
        )

    if resp.cookies:
        return "; ".join(f"{name}={value}" for name, value in resp.cookies.items())

    # Fallback: parse a single Set-Cookie header if httpx did not jar it.
    set_cookie = resp.headers.get("set-cookie")
    if set_cookie:
        return set_cookie.split(";")[0].strip()

    raise VietstockAuthRefreshError(f"no session cookie returned by {url}")


async def _do_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    _refreshed: bool = False,
) -> Any:
    """Make one throttled GET and return decoded JSON.

    On 401/403, attempts one cookie refresh before giving up. On 429, applies
    bounded exponential backoff. HTML/WAF challenge pages are surfaced as
    access-blocked errors so the caller can degrade gracefully.
    """
    for attempt in range(_MAX_429_RETRIES + 1):
        await _throttle()

        cookie = _get_cookie()
        headers = _VIETSTOCK_HEADERS.copy()
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=headers,
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.TimeoutException as exc:
                raise VietstockAccessBlockedError(f"timeout for {url}") from exc
            except httpx.ConnectError as exc:
                raise VietstockAccessBlockedError(f"cannot connect to {url}") from exc

        if resp.status_code in (401, 403):
            if _refreshed:
                raise VietstockAuthRefreshError(
                    f"{url} returned {resp.status_code} after cookie refresh"
                )
            try:
                new_cookie = await _refresh_cookie()
            except VietstockAuthRefreshError as exc:
                raise VietstockAuthRefreshError(
                    f"{url} returned {resp.status_code} and auth refresh failed"
                ) from exc
            _set_cookie(new_cookie)
            return await _do_get(url, params=params, _refreshed=True)

        if resp.status_code == 429:
            if attempt < _MAX_429_RETRIES:
                backoff = _BACKOFF_BASE_S * (2**attempt)
                logger.warning(
                    "vietstock %s returned 429, backing off %.1fs before retry %d/%d",
                    url,
                    backoff,
                    attempt + 1,
                    _MAX_429_RETRIES,
                )
                await asyncio.sleep(backoff)
                continue
            raise VietstockRateLimitedError(f"{url} returned 429")

        if resp.status_code >= 500:
            raise VietstockAccessBlockedError(f"{url} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise VietstockAccessBlockedError(f"{url} returned {resp.status_code}")

        resp_headers = getattr(resp, "headers", None)
        content_type = ""
        if resp_headers is not None:
            content_type = resp_headers.get("content-type", "")
        if "html" in content_type.lower():
            raise VietstockAccessBlockedError(f"cloudflare/html response from {url}")

        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise VietstockDecodeError(f"cannot decode response from {url}") from exc

    raise VietstockRateLimitedError(f"{url} exceeded 429 retry budget")


async def _do_post(
    url: str,
    data: dict[str, Any],
    *,
    _refreshed: bool = False,
) -> Any:
    """Make one throttled POST with form-encoded data and return decoded JSON.

    The Vietstock data endpoints are POST endpoints that expect
    ``application/x-www-form-urlencoded`` bodies and a
    ``__RequestVerificationToken``. On 401/403/anti-forgery failures we fetch
    a fresh token once before giving up. On 429 we apply bounded exponential
    backoff.
    """
    token = await _get_verification_token()
    body = {**data, "__RequestVerificationToken": token}

    for attempt in range(_MAX_429_RETRIES + 1):
        await _throttle()

        headers = _VIETSTOCK_HEADERS.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        cookie = _get_cookie()
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=headers,
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.post(url, data=body)
            except httpx.TimeoutException as exc:
                raise VietstockAccessBlockedError(f"timeout for {url}") from exc
            except httpx.ConnectError as exc:
                raise VietstockAccessBlockedError(f"cannot connect to {url}") from exc

        # Anti-forgery token rejected or expired: refresh once.
        if resp.status_code in (401, 403) or "anti-forgery" in (resp.text or "").lower():
            if _refreshed:
                raise VietstockAuthRefreshError(
                    f"{url} returned {resp.status_code} after token refresh"
                )
            _verification_token = None
            try:
                new_token = await _get_verification_token()
            except VietstockAuthRefreshError as exc:
                raise VietstockAuthRefreshError(
                    f"{url} returned {resp.status_code} and token refresh failed"
                ) from exc
            body = {**data, "__RequestVerificationToken": new_token}
            return await _do_post(url, data, _refreshed=True)

        if resp.status_code == 429:
            if attempt < _MAX_429_RETRIES:
                backoff = _BACKOFF_BASE_S * (2**attempt)
                logger.warning(
                    "vietstock %s returned 429, backing off %.1fs before retry %d/%d",
                    url,
                    backoff,
                    attempt + 1,
                    _MAX_429_RETRIES,
                )
                await asyncio.sleep(backoff)
                continue
            raise VietstockRateLimitedError(f"{url} returned 429")

        if resp.status_code >= 500:
            raise VietstockAccessBlockedError(f"{url} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise VietstockAccessBlockedError(f"{url} returned {resp.status_code}")

        resp_headers = getattr(resp, "headers", None)
        content_type = ""
        if resp_headers is not None:
            content_type = resp_headers.get("content-type", "")
        if "html" in content_type.lower():
            raise VietstockAccessBlockedError(f"cloudflare/html response from {url}")

        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise VietstockDecodeError(f"cannot decode response from {url}") from exc

    raise VietstockRateLimitedError(f"{url} exceeded 429 retry budget")


def _demo_quote(symbol: str) -> dict[str, Any]:
    """Return a stable synthetic quote for tests and demos."""
    seed = symbol.upper()
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def digit(i: int) -> int:
        return int(digest[i : i + 6], 16)

    close = 50_000 + (digit(0) % 100_000)
    change = (digit(6) % 5_000) - 2_500
    current = close + change
    volume = 100_000 + (digit(12) % 5_000_000)

    return {
        "symbol": seed,
        "name": f"Công ty {seed}",
        "exchange": "HOSE",
        "current_price": current / 1000.0,
        "open_price": (close - (digit(18) % 1_000)) / 1000.0,
        "high": (close + (digit(24) % 1_000)) / 1000.0,
        "low": (close - (digit(30) % 1_000)) / 1000.0,
        "close": close / 1000.0,
        "volume": volume,
        "change": change / 1000.0,
        "change_percent": (change / close) * 100,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "key_ratios": {
            "pe": 10.0 + (digit(36) % 20),
            "pb": 1.0 + (digit(42) % 3),
            "roe": digit(48) % 30,
            "roa": (digit(54) % 30) / 10.0,
        },
        "source_url": _quote_url(),
    }


def _demo_financials(symbol: str) -> dict[str, Any]:
    """Return stable synthetic financial reports for tests and demos."""
    periods = ["Q4-2025", "Q1-2026", "Q2-2026", "Q3-2026"]
    return {
        "balance_sheet": {
            "periods": periods,
            "items": [
                {
                    "code": "270",
                    "name": "Tổng tài sản",
                    "values": [1000, 1100, 1150, 1200],
                },
                {"code": "300", "name": "Nợ phải trả", "values": [400, 420, 430, 440]},
                {
                    "code": "400",
                    "name": "Vốn chủ sở hữu",
                    "values": [600, 680, 720, 760],
                },
            ],
            "key_metrics": {
                "tong_tai_san": [1000, 1100, 1150, 1200],
                "no_phai_tra": [400, 420, 430, 440],
                "von_chu_so_huu": [600, 680, 720, 760],
            },
            "unit": "tỷ VND",
            "source_url": _financial_url(),
        },
        "income_statement": {
            "periods": periods,
            "items": [
                {
                    "code": "10",
                    "name": "Doanh thu thuần",
                    "values": [500, 550, 600, 650],
                },
                {"code": "20", "name": "Lợi nhuận gộp", "values": [150, 170, 190, 210]},
                {
                    "code": "60",
                    "name": "Lợi nhuận sau thuế",
                    "values": [50, 60, 70, 80],
                },
            ],
            "key_metrics": {
                "doanh_thu_thuan": [500, 550, 600, 650],
                "loi_nhuan_gop": [150, 170, 190, 210],
                "loi_nhuan_sau_thue": [50, 60, 70, 80],
            },
            "unit": "tỷ VND",
            "source_url": _financial_url(),
        },
        "cash_flow": {
            "periods": periods,
            "items": [
                {
                    "code": "HDKD_20",
                    "name": "Lưu chuyển tiền thuần từ HĐKD",
                    "values": [40, 45, 50, 55],
                },
                {
                    "code": "HDTC_42",
                    "name": "Tiền và tương đương tiền cuối kỳ",
                    "values": [120, 130, 140, 150],
                },
            ],
            "key_metrics": {
                "luu_chuyen_tu_hdkd": [40, 45, 50, 55],
                "tien_cuoi_ky": [120, 130, 140, 150],
            },
            "unit": "tỷ VND",
            "source_url": _financial_url(),
        },
    }


async def fetch_quote(symbol: str) -> dict[str, Any]:
    """Return a raw quote dict for *symbol*."""
    if _demo_mode():
        return _demo_quote(symbol)

    if not _has_live_credentials():
        raise VietstockAuthRefreshError(
            "missing_credentials: VIETSTOCK_QUOTE_URL and VIETSTOCK_FINANCIAL_URL are required"
        )

    url = _quote_url()
    raw = await _do_post(url, {"code": symbol.upper(), "s": "0", "t": ""})

    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        raise VietstockDecodeError(f"quote response for {symbol} is not a JSON object")

    return raw


async def _fetch_financial_info(symbol: str) -> Any:
    """Fetch the consolidated financial statement from the configured endpoint.

    Vietstock's ``financeinfo`` endpoint with ``ReportType=BCTQ`` returns the
    balance sheet, income statement, and key ratios in a single payload.
    """
    url = _financial_url()
    return await _do_post(
        url,
        {
            "Code": symbol.upper(),
            "Page": "1",
            "PageSize": "4",
            "ReportTermType": "2",
            "ReportType": "BCTQ",
            "Unit": "1",
        },
    )


async def fetch_financials(symbol: str) -> dict[str, Any]:
    """Return raw balance-sheet/income/cash-flow dicts for *symbol*."""
    if _demo_mode():
        return _demo_financials(symbol)

    if not _has_live_credentials():
        raise VietstockAuthRefreshError(
            "missing_credentials: VIETSTOCK_QUOTE_URL and VIETSTOCK_FINANCIAL_URL are required"
        )

    raw = await _fetch_financial_info(symbol)
    return {
        "balance_sheet": raw,
        "income_statement": raw,
        "cash_flow": raw,
    }


async def fetch_vietstock(input_model: VietstockScrapeInput) -> dict[str, Any]:
    """Fetch all requested Vietstock data and return a flat raw envelope."""
    quote = await fetch_quote(input_model.symbol)
    financials = None
    if input_model.include_financials:
        financials = await fetch_financials(input_model.symbol)
    return {
        "quote": quote,
        "financials": financials,
    }
