"""Fetch CafeF stock quote, financials, and news.

Demo mode is the default because CafeF does not publish a stable, documented
public quote/news endpoint. Set ``CAFEF_DEMO_MODE=FALSE`` and provide live
endpoints via env to hit the real CafeF APIs.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import re
import time
from typing import Any

import httpx

from app.config import config

from .schemas import CafeFScrapeInput

logger = logging.getLogger(__name__)

# CafeF does not publish a stable quote API. We use the price-history Ajax
# endpoint that backs https://cafef.vn/du-lieu/lich-su-giao-dich-<symbol>-1.chn.
# It returns the most recent close/open/high/low/volume for a symbol.
_QUOTE_URL = (
    "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?"
    "ExchangeType={exchange}&Symbol={symbol}&StartDate={start_date}&"
    "EndDate={end_date}&PageIndex=1&PageSize=1"
)

# Market-news RSS for the "Thị trường chứng khoán" category. We fetch it and
# optionally filter by the requested symbol.
_NEWS_URL = "https://cafef.vn/thi-truong-chung-khoan.rss"

_FINANCIAL_BASE = "https://apiweb.cafef.vn/api"
_BALANCE_ENDPOINT = "{base}/v2/BCTC/GetReportCDKT"
_INCOME_ENDPOINT = "{base}/v1/BCTC/GetReportDetail"
_CASH_ENDPOINT = "{base}/v1/BCTC/GetReportLCTT"

# Bounded retry/backoff for transient 429 responses.
_MAX_429_RETRIES = 2
_BACKOFF_BASE_S = 1.0

# Headers that help avoid WAF/Cloudflare blocks on CafeF endpoints.
_CAFEF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Nowing/1.0)",
    "Accept": "application/json",
    "Referer": "https://cafef.vn/",
}

# Process-local rate-limit state. 20 req/min -> 1 request every 3 s.
_throttle_lock = asyncio.Lock()
_last_request_at: float | None = None


class CafeFRateLimitedError(RuntimeError):
    """Raised when CafeF returns 429."""


class CafeFAccessBlockedError(RuntimeError):
    """Raised when CafeF blocks or returns an unexpected error."""


class CafeFDecodeError(ValueError):
    """Raised when a CafeF response cannot be decoded as JSON."""


def _rate_limit_interval() -> float:
    """Seconds between requests for the configured per-process rate limit."""
    rps = float(getattr(config, "CAFEF_RATE_LIMIT_RPS", 1 / 3))
    return 1.0 / max(rps, 1e-6)


async def _throttle() -> None:
    """Wait until at least ``_rate_limit_interval`` has passed since the
    previous request start. This keeps the average request rate under the
    20 req/min envelope without needing a token-bucket dependency.
    """
    global _last_request_at

    async with _throttle_lock:
        now = time.perf_counter()
        if _last_request_at is not None:
            wait = max(0.0, _rate_limit_interval() - (now - _last_request_at))
            if wait:
                logger.debug("cafef throttle: sleeping %.2f s", wait)
                await asyncio.sleep(wait)
        _last_request_at = time.perf_counter()


def _timeout() -> float:
    return float(getattr(config, "CAFEF_TIMEOUT_S", 15.0))


def _quote_date_range(days: int = 30) -> tuple[str, str]:
    """Return (start, end) formatted as M/D/YYYY for the CafeF Ajax endpoint."""
    today = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(hours=7)
    start = today - datetime.timedelta(days=days)
    return start.strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")


def _quote_url(symbol: str, exchange: str = "HOSE") -> str:
    custom = getattr(config, "CAFEF_QUOTE_URL", "")
    template = custom or _QUOTE_URL
    start_date, end_date = _quote_date_range()
    return template.format(
        exchange=exchange,
        symbol=symbol.upper(),
        start_date=start_date,
        end_date=end_date,
    )


def _news_url(symbol: str, max_news: int) -> str:
    custom = getattr(config, "CAFEF_NEWS_URL", "")
    template = custom or _NEWS_URL
    if "{symbol}" in template or "{max_news}" in template:
        return template.format(symbol=symbol.upper(), max_news=max(max_news, 0))
    return template


def _financial_base() -> str:
    return getattr(config, "CAFEF_FINANCIAL_BASE_URL", "") or _FINANCIAL_BASE


def _report_url(report_type: str) -> str:
    base = _financial_base()
    if report_type == "balance_sheet":
        return _BALANCE_ENDPOINT.format(base=base)
    if report_type == "income_statement":
        return _INCOME_ENDPOINT.format(base=base)
    if report_type == "cash_flow":
        return _CASH_ENDPOINT.format(base=base)
    raise CafeFDecodeError(f"unknown report type {report_type}")


def _demo_quote(symbol: str) -> dict[str, Any]:
    """Return a stable synthetic quote for tests and demos."""
    seed = symbol.upper()
    # Deterministic but arbitrary numbers so the same symbol is stable.
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
            "eps": (digit(48) % 5_000) / 1000.0,
            "roe": (digit(54) % 30) / 100.0,
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
                {"code": "270", "name": "Tổng tài sản", "values": [1000, 1100, 1150, 1200]},
                {"code": "300", "name": "Nợ phải trả", "values": [400, 420, 430, 440]},
                {"code": "400", "name": "Vốn chủ sở hữu", "values": [600, 680, 720, 760]},
            ],
            "key_metrics": {
                "tong_tai_san": [1000, 1100, 1150, 1200],
                "no_phai_tra": [400, 420, 430, 440],
                "von_chu_so_huu": [600, 680, 720, 760],
            },
            "unit": "tỷ VND",
            "source_url": _report_url("balance_sheet")
            + f"?symbol={symbol.upper()}&pageIndex=1&pageSize=4&reportType=ALL&TypeTime=QUY",
        },
        "income_statement": {
            "periods": periods,
            "items": [
                {"code": "10", "name": "Doanh thu thuần", "values": [500, 550, 600, 650]},
                {"code": "20", "name": "Lợi nhuận gộp", "values": [150, 170, 190, 210]},
                {"code": "60", "name": "Lợi nhuận sau thuế", "values": [50, 60, 70, 80]},
            ],
            "key_metrics": {
                "doanh_thu_thuan": [500, 550, 600, 650],
                "loi_nhuan_gop": [150, 170, 190, 210],
                "loi_nhuan_sau_thue": [50, 60, 70, 80],
            },
            "unit": "tỷ VND",
            "source_url": _report_url("income_statement")
            + f"?symbol={symbol.upper()}&pageIndex=1&pageSize=4&reportType=KQKD&TypeTime=QUY",
        },
        "cash_flow": {
            "periods": periods,
            "items": [
                {"code": "HDKD_20", "name": "Lưu chuyển tiền thuần từ HĐKD", "values": [40, 45, 50, 55]},
                {"code": "HDTC_42", "name": "Tiền và tương đương tiền cuối kỳ", "values": [120, 130, 140, 150]},
            ],
            "key_metrics": {
                "luu_chuyen_tu_hdkd": [40, 45, 50, 55],
                "tien_cuoi_ky": [120, 130, 140, 150],
            },
            "unit": "tỷ VND",
            "source_url": _report_url("cash_flow")
            + f"?symbol={symbol.upper()}&pageIndex=1&pageSize=4&reportType=ALL&TypeTime=QUY",
        },
    }


def _demo_news(symbol: str, max_news: int) -> list[dict[str, Any]]:
    """Return stable synthetic news for tests and demos."""
    max_news = min(max(max_news, 0), 10)
    today = time.strftime("%Y-%m-%d")
    return [
        {
            "title": f"{symbol.upper()} công bố kết quả kinh doanh quý {i + 1}",
            "url": f"https://cafef.vn/news/{symbol.lower()}-{i + 1}.chn",
            "published_at": today,
            "summary": f"Doanh nghiệp {symbol.upper()} ghi nhận tăng trưởng ổn định.",
            "source": "cafef",
            "symbol": symbol.upper(),
        }
        for i in range(max_news)
    ]


def _parse_price_history(raw: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Extract the most recent OHLCV row from a CafeF PriceHistory response.

    If the payload is already a normalized quote dict (e.g. from tests or a
    custom CAFEF_QUOTE_URL), return it as-is so the parser can still consume it.
    """
    if not isinstance(raw, dict):
        return None

    # Already a normalized quote dict (demo, custom URL, unit-test fixture).
    if "Data" not in raw and any(k in raw for k in ("current_price", "price", "GiaDongCua")):
        return raw

    data = raw.get("Data") or {}
    rows = data.get("Data") or []
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None

    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    def _parse_change(raw_change: str | None) -> tuple[float | None, float | None]:
        if not raw_change:
            return None, None
        # Example: "-0,20 (-0,34%)" or "+0,60 (+1,01%)"
        # The comma is the decimal separator in Vietnamese locale.
        m = re.search(r"([-\d,]+)\s*\(([+-]?[\d,]+)%\)", raw_change)
        if not m:
            return None, None
        change = _float(m.group(1).replace(",", "."))
        change_percent = _float(m.group(2).replace(",", "."))
        return change, change_percent

    raw_change = row.get("ThayDoi")
    change, change_percent = _parse_change(raw_change)

    return {
        "symbol": symbol.upper(),
        "name": None,
        "exchange": row.get("Exchange") or "HOSE",
        "current_price": _float(row.get("GiaDongCua")),
        "open_price": _float(row.get("GiaMoCua")),
        "high": _float(row.get("GiaCaoNhat")),
        "low": _float(row.get("GiaThapNhat")),
        "close": _float(row.get("GiaDongCua")),
        "volume": _float(row.get("KhoiLuongKhopLenh")),
        "change": change,
        "change_percent": change_percent,
        "timestamp": row.get("Ngay"),
        "key_ratios": {},
        "source_url": None,
    }


def _parse_rss_news(xml_text: str, symbol: str | None, max_news: int) -> list[dict[str, Any]]:
    """Parse CafeF market-news RSS and optionally filter by symbol."""
    items: list[dict[str, Any]] = []
    try:
        import xml.etree.ElementTree as ET

        # Strip namespacing for simple parsing.
        root = ET.fromstring(xml_text)
    except Exception:
        return items

    channel = root.find("channel")
    if channel is None:
        return items

    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        desc_el = item.find("description")

        title = (title_el.text or "").strip() if title_el is not None and title_el.text else ""
        link = (link_el.text or "").strip() if link_el is not None and link_el.text else ""
        published = (pub_el.text or "").strip() if pub_el is not None and pub_el.text else ""
        description = (desc_el.text or "").strip() if desc_el is not None and desc_el.text else ""

        # Extract a plain-text summary from CDATA/description.
        summary = re.sub(r"<[^>]+>", "", description).strip()

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "published_at": published,
                "summary": summary,
                "source": "cafef",
                "symbol": symbol.upper() if symbol else None,
            }
        )

    if symbol:
        sym = symbol.upper()
        filtered = [it for it in items if sym in (it["title"] + it.get("summary", "")).upper()]
        if filtered:
            items = filtered

    return items[:max_news]


async def _do_get(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make one throttled GET and return the decoded JSON envelope.

    Follows redirects, sends browser-like headers, and performs bounded
    exponential backoff on 429. HTML challenge pages (e.g. Cloudflare)
    are surfaced as access-blocked errors so the caller can degrade
    gracefully instead of paying for empty JSON.
    """
    for attempt in range(_MAX_429_RETRIES + 1):
        await _throttle()
        async with httpx.AsyncClient(
            timeout=_timeout(),
            headers=_CAFEF_HEADERS,
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.TimeoutException as exc:
                raise CafeFAccessBlockedError(f"timeout for {url}") from exc
            except httpx.ConnectError as exc:
                raise CafeFAccessBlockedError(f"cannot connect to {url}") from exc

        if resp.status_code == 429:
            if attempt < _MAX_429_RETRIES:
                backoff = _BACKOFF_BASE_S * (2 ** attempt)
                logger.warning(
                    "cafef %s returned 429, backing off %.1fs before retry %d/%d",
                    url,
                    backoff,
                    attempt + 1,
                    _MAX_429_RETRIES,
                )
                await asyncio.sleep(backoff)
                continue
            raise CafeFRateLimitedError(f"{url} returned 429")

        if resp.status_code in (403, 451):
            raise CafeFAccessBlockedError(f"{url} returned {resp.status_code}")
        if resp.status_code >= 500:
            raise CafeFAccessBlockedError(f"{url} returned {resp.status_code}")
        if resp.status_code != 200:
            raise CafeFAccessBlockedError(f"{url} returned {resp.status_code}")

        # Cloudflare/WAF may return a 200 HTML challenge page. Do not try to
        # parse it as JSON; treat it the same as an access-blocked response.
        resp_headers = getattr(resp, "headers", None)
        content_type = ""
        if resp_headers is not None:
            content_type = resp_headers.get("content-type", "")
        if "html" in content_type.lower():
            raise CafeFAccessBlockedError(f"cloudflare/html response from {url}")

        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise CafeFDecodeError(f"cannot decode response from {url}") from exc


async def fetch_quote(symbol: str) -> dict[str, Any]:
    """Return a raw quote dict for *symbol*."""
    if getattr(config, "CAFEF_DEMO_MODE", False):
        return _demo_quote(symbol)

    # Try HOSE, then HNX, then UPCOM. The first exchange with data wins.
    for exchange in ("HOSE", "HNX", "UPCOM"):
        url = _quote_url(symbol, exchange=exchange)
        try:
            raw = await _do_get(url)
        except CafeFAccessBlockedError:
            continue
        parsed = _parse_price_history(raw, symbol)
        if parsed is not None:
            return parsed

    raise CafeFAccessBlockedError(f"no price history found for {symbol} on any exchange")


async def _fetch_report(
    report_type: str,
    symbol: str,
    report_param: str,
    type_time: str = "QUY",
    page_size: int = 4,
) -> dict[str, Any]:
    url = _report_url(report_type)
    params = {
        "symbol": symbol.upper(),
        "pageIndex": 1,
        "pageSize": page_size,
        "reportType": report_param,
        "TypeTime": type_time,
    }
    return await _do_get(url, params=params)


async def fetch_financials(symbol: str, *, page_size: int = 4) -> dict[str, Any]:
    """Return raw balance-sheet/income/cash-flow dicts for *symbol*."""
    if getattr(config, "CAFEF_DEMO_MODE", False):
        return _demo_financials(symbol)

    balance, income, cash = await asyncio.gather(
        _fetch_report("balance_sheet", symbol, "ALL", page_size=page_size),
        _fetch_report("income_statement", symbol, "KQKD", page_size=page_size),
        _fetch_report("cash_flow", symbol, "ALL", page_size=page_size),
    )
    return {
        "balance_sheet": balance,
        "income_statement": income,
        "cash_flow": cash,
    }


async def fetch_news(symbol: str | None, *, max_news: int = 10) -> list[dict[str, Any]]:
    """Return a list of raw news article dicts for *symbol*."""
    if symbol is None:
        return []
    if getattr(config, "CAFEF_DEMO_MODE", False):
        return _demo_news(symbol, max_news)

    url = _news_url(symbol or "", max_news)
    await _throttle()
    async with httpx.AsyncClient(
        timeout=_timeout(),
        headers=_CAFEF_HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.TimeoutException as exc:
            raise CafeFAccessBlockedError(f"timeout for {url}") from exc
        except httpx.ConnectError as exc:
            raise CafeFAccessBlockedError(f"cannot connect to {url}") from exc

    if resp.status_code == 429:
        raise CafeFRateLimitedError(f"{url} returned 429")
    if resp.status_code >= 400:
        raise CafeFAccessBlockedError(f"{url} returned {resp.status_code}")

    return _parse_rss_news(resp.text, symbol, max(max_news, 0))


async def fetch_cafef(input_model: CafeFScrapeInput) -> dict[str, Any]:
    """Fetch all requested CafeF data and return a flat raw envelope."""
    quote = await fetch_quote(input_model.symbol)
    financials = None
    if input_model.include_financials:
        financials = await fetch_financials(input_model.symbol)
    news: list[dict[str, Any]] = []
    if input_model.include_news:
        news = await fetch_news(input_model.symbol, max_news=input_model.max_news)
    return {
        "quote": quote,
        "financials": financials,
        "news": news,
    }
