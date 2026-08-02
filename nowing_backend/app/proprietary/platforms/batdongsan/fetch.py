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
                return decode_response(page.content)

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
