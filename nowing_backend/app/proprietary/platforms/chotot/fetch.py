"""Fetch Chợ Tốt Nhà BĐS listings from the public gateway API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
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
_MAX_RESPONSE_BYTES = 50 * 1024 * 1024

_USER_AGENT_POOL = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
)

# Chợ Tốt Nhà public RSA key used to encrypt list_id before the phone API call.
# Extracted from the web bundle's RSAPublicKey.production value.
_CHOTOT_RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAxnvPjlA/K/adq6mA6+uU
tlyBBxFaKeK+WD2FypOeCAP0qtucmaDrIbxirykrxQjRpGxl2HKRBwGd2h/hDuk9
CxRUXD2p0Hrzb1Hb9M5px19TPXM6AWSClR1kozehRusIFrxP6PHqDLx5prJFLlSZ
zg3N3oGhS6oP/a4Ku/iAdCUCiHb5TX3b3+y4Ll/QViZhpKZjU6BhIOsiVIJhyXvn
0cSqLXPjNuXR5A4JkmRl9T9cWncEHTKmoVUyXQJaDZa3yH/OJSEmhhGyKNKkM5so
lasJWSBKenFnFvphw3+KG8BGfJwGkvtRAVbS1ljduH8z8fxALxHgUdnTtgpxB+KZ
/CVnNr97EGqYPLVlX+duGkuy1yCunqVTiY2HyL/0bMTBK84oCQjtMVAHgZ345hZn
mGST71D8+i5HGtOOFoRyP6qK6ex1qfEROzWsmVDA00aHLlQcKOLaHvT/DB30aeUs
ZoL/kQo100XccufpHESrits0mEuoyza4CCFM04F3pDOXAgMBAAE=
-----END PUBLIC KEY-----"""

_PHONE_URL = "https://gateway.chotot.com/v1/public/ad-listing/phone"


class ChototBdsAccessBlockedError(RuntimeError):
    """Raised when Chợ Tốt blocks anonymous access (5xx / non-200)."""


class ChototBdsBotDetectedError(ChototBdsAccessBlockedError):
    """Raised when Chợ Tốt returns 403 (bot / akamai block)."""


class ChototBdsRateLimitedError(RuntimeError):
    """Raised when Chợ Tốt returns 429."""


class ChototBdsDecodeError(ValueError):
    """Raised when the gateway response cannot be parsed."""


def _retry_delay(attempt: int) -> float:
    base = max(0.5, getattr(config, "CHOTOT_BDS_RETRY_BACKOFF_BASE_S", 0.5))
    return base * (2**attempt)


def _user_agent(attempt: int) -> str:
    """Rotate a small pool of mobile/Chrome UAs per attempt/request."""
    ua = getattr(config, "CHOTOT_BDS_USER_AGENT", None)
    if ua:
        return str(ua)
    return _USER_AGENT_POOL[attempt % len(_USER_AGENT_POOL)]


def _timeout() -> float:
    """Allow operators to override the per-request timeout."""
    return max(5.0, getattr(config, "CHOTOT_BDS_TIMEOUT_S", 30.0))


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
    if status == 403:
        raise ChototBdsBotDetectedError(f"{url} returned 403")
    if status in _5XX:
        raise ChototBdsAccessBlockedError(f"{url} returned {status}")
    if status != 200:
        raise ChototBdsAccessBlockedError(f"{url} returned {status}")


def _decode(raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ChototBdsDecodeError(
            f"response exceeds {_MAX_RESPONSE_BYTES} bytes"
        )
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
                    "User-Agent": _user_agent(attempt),
                    "Accept": "application/json",
                },
                proxy=get_proxy_url(),
                timeout=_timeout(),
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

async def fetch_phone(list_id: int) -> str | None:
    """Fetch the public phone number for a Chợ Tốt listing.

    The phone endpoint requires an RSA-PKCS1v15 encrypted ``list_id``
    parameter.  Failure is non-fatal and returns ``None`` so the scraper
    can continue with the listing masked/unavailable.
    """
    if not list_id or list_id <= 0:
        return None

    try:
        key = serialization.load_pem_public_key(_CHOTOT_RSA_PUBLIC_KEY.encode())
        ciphertext = key.encrypt(str(list_id).encode(), padding.PKCS1v15())
        # The HTTP client URL-encodes query parameters, so pass the raw base64.
        e = base64.b64encode(ciphertext).decode()
    except Exception as exc:
        logger.warning("Chotot BĐS phone encryption failed for %s: %s", list_id, exc)
        return None

    for attempt in range(_MAX_ROTATIONS + 1):
        try:
            page = await AsyncFetcher.get(
                _PHONE_URL,
                params={"e": e},
                headers={
                    "User-Agent": _user_agent(attempt),
                    "Accept": "application/json",
                },
                proxy=get_proxy_url(),
                timeout=_timeout(),
            )
            if page.status == 200:
                data = _decode(page.body)
                phone = data.get("phone")
                if isinstance(phone, str) and phone.strip():
                    return phone.strip()
                return None

            _raise_for_status(page.status, _PHONE_URL)
        except ChototBdsDecodeError:
            logger.warning("Chotot BĐS phone response decode failed for %s", list_id)
            return None
        except ChototBdsRateLimitedError:
            if attempt < _MAX_ROTATIONS:
                await asyncio.sleep(_retry_delay(attempt))
                continue
            logger.warning("Chotot BĐS phone fetch rate limited for %s", list_id)
            return None
        except ChototBdsAccessBlockedError as exc:
            if attempt < _MAX_ROTATIONS:
                logger.warning("Chotot BĐS phone fetch blocked for %s: %s", list_id, exc)
                await asyncio.sleep(_retry_delay(attempt))
                continue
            logger.warning("Chotot BĐS phone fetch exhausted for %s: %s", list_id, exc)
            return None
        except Exception as exc:
            logger.warning("Chotot BĐS phone fetch failed for %s: %s", list_id, exc)
            if attempt >= _MAX_ROTATIONS:
                return None
            await asyncio.sleep(_retry_delay(attempt))

    return None


_REGIONS_CACHE: dict[str, Any] | None = None
_regions_lock = asyncio.Lock()


async def load_regions() -> dict[str, Any]:
    """Load the public region/area lookup table and cache it in-process."""
    global _REGIONS_CACHE
    if _REGIONS_CACHE is not None:
        return _REGIONS_CACHE

    async with _regions_lock:
        if _REGIONS_CACHE is not None:
            return _REGIONS_CACHE

        for attempt in range(_MAX_ROTATIONS + 1):
            try:
                page = await AsyncFetcher.get(
                    REGIONS_URL,
                    headers={
                        "User-Agent": _user_agent(attempt),
                        "Accept": "application/json",
                    },
                    proxy=get_proxy_url(),
                    timeout=_timeout(),
                )
                if page.status == 200:
                    decoded = _decode(page.body)
                    if not isinstance(decoded, dict) or "regionFollowId" not in decoded:
                        raise ChototBdsDecodeError(
                            "loadRegions payload missing expected structure"
                        )
                    _REGIONS_CACHE = decoded
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
