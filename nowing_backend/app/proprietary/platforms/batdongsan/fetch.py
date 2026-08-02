"""Fetch and decode the Batdongsan mobile API response."""

from __future__ import annotations

import base64
import gzip
import json
import logging
import time
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

API_ORIGIN = "https://batdongsan.com.vn"
API_HOST = "apimap.batdongsan.com.vn"
P_SYNC_URL = "https://apimap.batdongsan.com.vn/api/p_sync"
MOBILE_USER_AGENT = (
    "Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G9500 Build/R16NW)"
)

# The mobile endpoint rarely blocks, but a 429 can still happen. Stay sticky for
# sequential page fetches; rotate on hard blocks.
_BLOCK_STATUSES = frozenset({403, 429})
_MAX_ROTATIONS = 3


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
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except Exception as exc:
            raise BatdongsanDecodeError("failed to decompress gzip layer") from exc

    try:
        decoded = base64.b64decode(raw)
    except Exception as exc:
        raise BatdongsanDecodeError("failed to base64-decode response") from exc

    swapped = _nibble_swap(decoded)
    try:
        text = swapped.decode("latin-1")
    except Exception as exc:
        raise BatdongsanDecodeError("failed to latin-1 decode nibble-swapped bytes") from exc

    try:
        return json.loads(text)
    except Exception as exc:
        raise BatdongsanDecodeError("failed to parse JSON from decoded response") from exc


def _build_payload(input_model: Any) -> dict[str, Any]:
    """Map the scraper input to the ``p_sync`` form payload."""
    ptype = 38 if input_model.listing_type == "buy" else 49
    return {
        "ptype": ptype,
        "cate": 0,
        "city": input_model.city,
        "dist": input_model.district_id if input_model.district_id is not None else -1,
        "ward": -1,
        "street": -1,
        "room": -1,
        "direct": -1,
        "minprice": input_model.min_price if input_model.min_price is not None else 0,
        "maxprice": input_model.max_price if input_model.max_price is not None else 0,
        "minarea": input_model.min_area if input_model.min_area is not None else 0,
        "maxarea": input_model.max_area if input_model.max_area is not None else 0,
        "projectid": -1,
        "sort": 0,
        "page": getattr(input_model, "page", 1),
        "searchType": 0,
        "client": "android",
        "m": "list",
        "pagesize": 20,
    }


def _raise_for_status(status: int, url: str) -> None:
    if status == 429:
        raise BatdongsanRateLimitedError(f"{url} returned 429")
    if status in {403, *range(500, 600)}:
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
                return decode_response(page.content)

            _raise_for_status(page.status, P_SYNC_URL)
        except (BatdongsanRateLimitedError, BatdongsanAccessBlockedError):
            raise
        except Exception as exc:
            logger.warning("Batdongsan POST %s failed: %s", P_SYNC_URL, exc)
            if attempt >= _MAX_ROTATIONS:
                raise BatdongsanAccessBlockedError(
                    f"{P_SYNC_URL} failed after {_MAX_ROTATIONS} attempts"
                ) from exc
        # Rotate on transient blocks. Rate-limited and blocked errors are re-raised
        # above, so this only runs on network/parse errors.

    raise BatdongsanAccessBlockedError(f"{P_SYNC_URL} exhausted all retries")


async def fetch_listings_for_input(input_model: Any) -> dict[str, Any]:
    """Convenience wrapper that builds the payload and fetches."""
    return await fetch_listings(_build_payload(input_model))
