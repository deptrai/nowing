"""Fetch Vietstock stock quotes and financial statements.

Demo mode is the default because Vietstock endpoints require a session cookie
and are not publicly documented. Set ``VIETSTOCK_DEMO_MODE=false`` and supply
``VIETSTOCK_SESSION_COOKIE`` to hit the live APIs.
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

# Defaults are placeholders; real URLs must be supplied via env vars.
_QUOTE_URL = "https://finance.vietstock.vn/api/trading/{symbol}"
_FINANCIAL_URL = (
    "https://finance.vietstock.vn/api/finance/{statement_type}?symbol={symbol}"
)
_REFRESH_URL = "https://finance.vietstock.vn"

# Bounded retry/backoff for transient 429 responses.
_MAX_429_RETRIES = 2
_BACKOFF_BASE_S = 1.0

# Headers that help avoid WAF/Cloudflare blocks.
_VIETSTOCK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Nowing/1.0)",
    "Accept": "application/json",
    "Referer": "https://finance.vietstock.vn/",
}

# Process-local rate-limit state. Default 20 req/min -> 1 request every 3 s.
_throttle_lock = asyncio.Lock()
_last_request_at: float | None = None

# Mutable process-local cookie jar.
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


def _quote_url(symbol: str) -> str:
    template = getattr(config, "VIETSTOCK_QUOTE_URL", _QUOTE_URL)
    return template.format(symbol=symbol.upper())


def _financial_url(statement_type: str, symbol: str) -> str:
    template = getattr(config, "VIETSTOCK_FINANCIAL_URL", _FINANCIAL_URL)
    return template.format(statement_type=statement_type, symbol=symbol.upper())


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
        "source_url": _quote_url(seed),
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
            "source_url": _financial_url("balance_sheet", symbol),
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
            "source_url": _financial_url("income_statement", symbol),
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
            "source_url": _financial_url("cash_flow", symbol),
        },
    }


async def fetch_quote(symbol: str) -> dict[str, Any]:
    """Return a raw quote dict for *symbol*."""
    if _demo_mode():
        return _demo_quote(symbol)

    url = _quote_url(symbol)
    raw = await _do_get(url)

    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        raise VietstockDecodeError(f"quote response for {symbol} is not a JSON object")

    return raw


async def _fetch_statement(statement_type: str, symbol: str) -> Any:
    """Fetch one financial statement from the configured endpoint."""
    url = _financial_url(statement_type, symbol)
    return await _do_get(url)


async def fetch_financials(symbol: str) -> dict[str, Any]:
    """Return raw balance-sheet/income/cash-flow dicts for *symbol*."""
    if _demo_mode():
        return _demo_financials(symbol)

    balance, income, cash = await asyncio.gather(
        _fetch_statement("balance_sheet", symbol),
        _fetch_statement("income_statement", symbol),
        _fetch_statement("cash_flow", symbol),
    )
    return {
        "balance_sheet": balance,
        "income_statement": income,
        "cash_flow": cash,
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
