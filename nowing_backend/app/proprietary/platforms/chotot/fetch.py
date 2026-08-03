"""Fetch Chợ Tốt Nhà BĐS listings from the public gateway API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.config import config
from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

GATEWAY_ORIGIN = "https://gateway.chotot.com"
LISTING_URL = "https://gateway.chotot.com/v1/public/ad-listing"
REGIONS_URL = "https://gateway.chotot.com/v1/public/web-proxy-api/loadRegions"

_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_BLOCK_STATUSES = frozenset({403, 429})
_5XX = frozenset(range(500, 600))
_MAX_ROTATIONS = 3


class ChototBdsAccessBlockedError(RuntimeError):
    """Raised when Chợ Tốt blocks anonymous access."""


class ChototBdsRateLimitedError(RuntimeError):
    """Raised when Chợ Tốt returns 429."""


class ChototBdsDecodeError(ValueError):
    """Raised when the gateway response cannot be parsed."""


def _retry_delay(attempt: int) -> float:
    base = max(0.5, getattr(config, "CHOTOT_BDS_RETRY_BACKOFF_BASE_S", 0.5))
    return base * (2**attempt)


def _build_listing_params(
    *,
    region_v2: int,
    area_v2: int | None,
    cg: int,
    listing_type: str,
    page: int,
    page_size: int,
    min_price: int | None,
    max_price: int | None,
    min_area: int | None,
    max_area: int | None,
) -> dict[str, Any]:
    st = "s" if listing_type == "buy" else "u"
    params: dict[str, Any] = {
        "region_v2": region_v2,
        "cg": cg,
        "limit": page_size,
        "o": (page - 1) * page_size,
        "w": 1,
        "st": st,
    }
    if area_v2 is not None:
        params["area_v2"] = area_v2
    if min_price is not None or max_price is not None:
        lo = min_price if min_price is not None else ""
        hi = max_price if max_price is not None else ""
        params["price"] = f"{lo}-{hi}"
    if min_area is not None or max_area is not None:
        lo = min_area if min_area is not None else ""
        hi = max_area if max_area is not None else ""
        params["size"] = f"{lo}-{hi}"
    return params


def _raise_for_status(status: int, url: str) -> None:
    if status == 429:
        raise ChototBdsRateLimitedError(f"{url} returned 429")
    if status in _BLOCK_STATUSES | _5XX:
        raise ChototBdsAccessBlockedError(f"{url} returned {status}")
    if status != 200:
        raise ChototBdsAccessBlockedError(f"{url} returned {status}")


def _decode(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ChototBdsDecodeError("response is not valid UTF-8") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChototBdsDecodeError("response is not valid JSON") from exc


async def fetch_listings(
    *,
    region_v2: int,
    area_v2: int | None,
    cg: int,
    listing_type: str,
    page: int,
    page_size: int = 20,
    min_price: int | None = None,
    max_price: int | None = None,
    min_area: int | None = None,
    max_area: int | None = None,
) -> dict[str, Any]:
    """GET the gateway ad-listing endpoint and return the decoded JSON."""
    params = _build_listing_params(
        region_v2=region_v2,
        area_v2=area_v2,
        cg=cg,
        listing_type=listing_type,
        page=page,
        page_size=page_size,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
    )
    url = LISTING_URL

    for attempt in range(_MAX_ROTATIONS + 1):
        try:
            started = time.perf_counter()
            page_obj = await AsyncFetcher.get(
                url,
                params=params,
                headers={
                    "User-Agent": _MOBILE_USER_AGENT,
                    "Accept": "application/json",
                },
                proxy=get_proxy_url(),
                timeout=30,
            )
            fetch_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[chotot_bds][perf] url=%s status=%s fetch_ms=%.1f",
                url,
                page_obj.status,
                fetch_ms,
            )

            if page_obj.status == 200:
                return _decode(page_obj.body)

            _raise_for_status(page_obj.status, url)
        except ChototBdsDecodeError:
            raise
        except ChototBdsRateLimitedError:
            if attempt < _MAX_ROTATIONS:
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except ChototBdsAccessBlockedError:
            if attempt < _MAX_ROTATIONS:
                logger.warning(
                    "Chotot BĐS block on %s, rotating proxy (attempt %s/%s)",
                    url,
                    attempt + 1,
                    _MAX_ROTATIONS,
                )
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise
        except Exception as exc:
            logger.warning("Chotot BĐS GET %s failed: %s", url, exc)
            if attempt >= _MAX_ROTATIONS:
                raise ChototBdsAccessBlockedError(
                    f"{url} failed after {_MAX_ROTATIONS} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt))

    raise ChototBdsAccessBlockedError(f"{url} exhausted all retries")


_REGIONS_CACHE: dict[str, Any] | None = None


async def load_regions() -> dict[str, Any]:
    """Load the public region/area lookup table and cache it in-process."""
    global _REGIONS_CACHE
    if _REGIONS_CACHE is not None:
        return _REGIONS_CACHE

    for attempt in range(_MAX_ROTATIONS + 1):
        try:
            page = await AsyncFetcher.get(
                REGIONS_URL,
                headers={
                    "User-Agent": _MOBILE_USER_AGENT,
                    "Accept": "application/json",
                },
                proxy=get_proxy_url(),
                timeout=30,
            )
            if page.status == 200:
                _REGIONS_CACHE = _decode(page.body)
                return _REGIONS_CACHE
            _raise_for_status(page.status, REGIONS_URL)
        except Exception as exc:
            logger.warning("Chotot loadRegions failed: %s", exc)
            if attempt >= _MAX_ROTATIONS:
                raise ChototBdsAccessBlockedError(
                    f"{REGIONS_URL} failed after {_MAX_ROTATIONS} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt))

    raise ChototBdsAccessBlockedError(f"{REGIONS_URL} exhausted all retries")
