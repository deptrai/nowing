"""Fetch and decode the Batdongsan mobile API response."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import zlib
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.config import config
from app.utils.proxy import get_proxy_url

from .parsers import parse_web_listings

logger = logging.getLogger(__name__)

API_ORIGIN = "https://batdongsan.com.vn"
API_HOST = "apimap.batdongsan.com.vn"
P_SYNC_URL = "https://apimap.batdongsan.com.vn/api/p_sync"
MOBILE_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G9500 Build/R16NW)"

# The mobile endpoint rarely blocks, but a 429 can still happen. Stay sticky for
# sequential page fetches; rotate on hard blocks.
_BLOCK_STATUSES = frozenset({403, 429})
_MAX_ROTATIONS = 3
_MAX_DECODED_BYTES = 50 * 1024 * 1024


class BatdongsanDecodeError(ValueError):
    """Raised when the obfuscated response cannot be decoded."""


class BatdongsanAccessBlockedError(RuntimeError):
    """Raised when Batdongsan blocks anonymous access."""


class BatdongsanRateLimitedError(RuntimeError):
    """Raised when Batdongsan returns 429."""


def _nibble_swap(data: bytes) -> bytes:
    """Swap the high and low nibble of each byte (self-inverse)."""
    return bytes(((b & 0x0F) << 4) | (b >> 4) for b in data)


def decode_response(raw: bytes) -> dict[str, Any]:
    """Decode the obfuscated ``p_sync`` response.

    Pipeline: gzip (optional) → base64 → nibble-swap → Latin-1 JSON.
    """
    if len(raw) > _MAX_DECODED_BYTES:
        raise BatdongsanDecodeError("response exceeds size cap")
    if raw[:2] == b"\x1f\x8b":
        # ``gzip.decompress`` gained ``max_length`` only in Python 3.13; use a
        # zlib decompressobj so the output stays bounded on 3.12 as well.
        try:
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = decompressor.decompress(raw, _MAX_DECODED_BYTES + 1)
        except Exception as exc:
            raise BatdongsanDecodeError("failed to decompress gzip layer") from exc
        if len(raw) > _MAX_DECODED_BYTES or decompressor.unconsumed_tail:
            raise BatdongsanDecodeError("gzip layer exceeds size cap")

    try:
        decoded = base64.b64decode(raw)
    except Exception as exc:
        raise BatdongsanDecodeError("failed to base64-decode response") from exc

    swapped = _nibble_swap(decoded)
    try:
        text = swapped.decode("latin-1")
    except Exception as exc:
        raise BatdongsanDecodeError(
            "failed to latin-1 decode nibble-swapped bytes"
        ) from exc

    try:
        return json.loads(text)
    except Exception as exc:
        raise BatdongsanDecodeError(
            "failed to parse JSON from decoded response"
        ) from exc


def _raise_for_status(status: int, url: str) -> None:
    if status == 429:
        raise BatdongsanRateLimitedError(f"{url} returned 429")
    if status in {403, *range(500, 600)}:
        raise BatdongsanAccessBlockedError(f"{url} returned {status}")
    if status != 200:
        raise BatdongsanAccessBlockedError(f"{url} returned {status}")


async def fetch_listings(payload: dict[str, Any]) -> dict[str, Any]:
    """POST to ``p_sync`` and return the decoded JSON envelope."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": API_ORIGIN,
        "Accept": "application/json",
        "User-Agent": MOBILE_USER_AGENT,
        "Host": API_HOST,
    }

    for attempt in range(_MAX_ROTATIONS + 1):
        try:
            started = time.perf_counter()
            page = await AsyncFetcher.post(
                P_SYNC_URL,
                data=payload,
                headers=headers,
                proxy=get_proxy_url(),
                stealthy_headers=True,
                timeout=30,
            )
            fetch_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[batdongsan][perf] url=%s status=%s fetch_ms=%.1f",
                P_SYNC_URL,
                page.status,
                fetch_ms,
            )

            if page.status == 200:
                return decode_response(page.body)

            _raise_for_status(page.status, P_SYNC_URL)
        except BatdongsanDecodeError:
            raise
        except BatdongsanRateLimitedError:
            if attempt < _MAX_ROTATIONS:
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except BatdongsanAccessBlockedError:
            if attempt < _MAX_ROTATIONS:
                logger.warning(
                    "Batdongsan block on %s, rotating proxy (attempt %s/%s)",
                    P_SYNC_URL,
                    attempt + 1,
                    _MAX_ROTATIONS,
                )
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except Exception as exc:
            logger.warning("Batdongsan POST %s failed: %s", P_SYNC_URL, exc)
            if attempt >= _MAX_ROTATIONS:
                raise BatdongsanAccessBlockedError(
                    f"{P_SYNC_URL} failed after {_MAX_ROTATIONS} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt))

    raise BatdongsanAccessBlockedError(f"{P_SYNC_URL} exhausted all retries")


def _retry_delay(attempt: int) -> float:
    """Exponential backoff for retry attempts, with a floor of 0.5s."""
    base = max(0.5, getattr(config, "BATDONGSAN_RETRY_BACKOFF_BASE_S", 0.5))
    return base * (2**attempt)


WEB_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

CITY_SLUGS: dict[str, str] = {
    "AG": "an-giang",
    "BD": "binh-duong",
    "BDI": "binh-dinh",
    "BG": "bac-giang",
    "BK": "bac-kan",
    "BL": "bac-lieu",
    "BN": "bac-ninh",
    "BP": "binh-phuoc",
    "BT": "ben-tre",
    "BTH": "binh-thuan",
    "CB": "cao-bang",
    "CM": "ca-mau",
    "CT": "can-tho",
    "DI": "dien-bien",
    "DKL": "dak-lak",
    "DN": "da-nang",
    "DNO": "dak-nong",
    "DT": "dong-thap",
    "GL": "gia-lai",
    "HD": "hai-duong",
    "HG": "ha-giang",
    "HN": "ha-noi",
    "HP": "hai-phong",
    "HT": "ha-tinh",
    "HUG": "hau-giang",
    "HY": "hung-yen",
    "KH": "khanh-hoa",
    "KG": "kien-giang",
    "KT": "kon-tum",
    "LA": "long-an",
    "LB": "long-bien",
    "LC": "lao-cai",
    "LCH": "lai-chau",
    "LD": "lam-dong",
    "LS": "lang-son",
    "NA": "nghe-an",
    "NB": "ninh-binh",
    "ND": "nam-dinh",
    "NT": "ninh-thuan",
    "PT": "phu-tho",
    "PY": "phu-yen",
    "QB": "quang-binh",
    "QN": "quang-ninh",
    "QNG": "quang-ngai",
    "QT": "quang-tri",
    "SG": "tp-hcm",
    "SL": "son-la",
    "ST": "soc-trang",
    "TB": "thai-binh",
    "TG": "tien-giang",
    "TH": "thanh-hoa",
    "TN": "thai-nguyen",
    "TQ": "tuyen-quang",
    "TV": "tra-vinh",
    "TTH": "hue",
    "VL": "vinh-long",
    "VT": "ba-ria-vung-tau",
    "YB": "yen-bai",
}


def build_web_listings_url(listing_type: str, slug: str, page: int) -> str:
    """Build the SSR URL for a city-level buy/rent listing page."""
    if listing_type == "buy":
        path = f"/ban-nha-dat-{slug}"
    else:
        path = f"/nha-dat-cho-thue-{slug}"
    if page > 1:
        path = f"{path}/p{page}"
    return f"{API_ORIGIN}{path}"


async def fetch_web_listings(payload: dict[str, Any]) -> dict[str, Any]:
    """GET the SSR web page and parse listing cards.

    Returns an envelope shaped like the mobile ``p_sync`` response
    (``{"data": [...], "m": "ok" | None}``) so the scraper can treat
    both fetchers uniformly.
    """
    city_code = payload.get("city", "")
    slug = CITY_SLUGS.get(city_code)
    if not slug:
        return {"data": [], "m": None}

    listing_type = "rent" if payload.get("ptype") == 49 else "buy"
    page = int(payload.get("page", 1))
    url = build_web_listings_url(listing_type, slug, page)

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "User-Agent": WEB_USER_AGENT,
    }

    for attempt in range(_MAX_ROTATIONS + 1):
        try:
            started = time.perf_counter()
            resp = await AsyncFetcher.get(
                url,
                headers=headers,
                proxy=get_proxy_url(),
                stealthy_headers=True,
                timeout=30,
            )
            fetch_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[batdongsan][perf][web] url=%s status=%s fetch_ms=%.1f",
                url,
                resp.status,
                fetch_ms,
            )

            if resp.status == 200:
                body = resp.body
                if isinstance(body, bytes):
                    body = body.decode("utf-8", errors="replace")
                items = parse_web_listings(body)
                more = "ok" if len(items) >= 20 else None
                return {"data": items, "m": more}

            _raise_for_status(resp.status, url)
        except BatdongsanDecodeError:
            raise
        except BatdongsanRateLimitedError:
            if attempt < _MAX_ROTATIONS:
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except BatdongsanAccessBlockedError:
            if attempt < _MAX_ROTATIONS:
                logger.warning(
                    "Batdongsan web block on %s, rotating (attempt %s/%s)",
                    url,
                    attempt + 1,
                    _MAX_ROTATIONS,
                )
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except Exception as exc:
            logger.warning("Batdongsan web GET %s failed: %s", url, exc)
            if attempt >= _MAX_ROTATIONS:
                raise BatdongsanAccessBlockedError(
                    f"{url} failed after {_MAX_ROTATIONS} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt))

    raise BatdongsanAccessBlockedError(f"{url} exhausted all retries")
