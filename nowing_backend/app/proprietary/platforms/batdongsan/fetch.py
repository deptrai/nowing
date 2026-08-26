"""Fetch and decode the Batdongsan mobile API response."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import zlib
from collections.abc import Awaitable, Callable
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.config import config
from app.services.scraper_platform_account_service import cookie_string_to_playwright
from app.utils.proxy import get_proxy_url

from .city_codes import CITY_SLUGS
from .dynamic_rule import get_batdongsan_rule
from .parsers import parse_detail_phone, parse_web_listings
from .schemas import BatdongsanScrapeInput

logger = logging.getLogger(__name__)

WebFetchFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

try:
    from scrapling.engines._browsers._stealth import AsyncStealthySession
except Exception as exc:  # pragma: no cover - defensive for non-browser envs
    AsyncStealthySession = None
    logger.warning("Batdongsan could not import AsyncStealthySession: %s", exc)

API_ORIGIN = "https://batdongsan.com.vn"
API_HOST = "apimap.batdongsan.com.vn"
P_SYNC_URL = "https://apimap.batdongsan.com.vn/api/p_sync"
MOBILE_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G9500 Build/R16NW)"

# The mobile endpoint rarely blocks, but a 429 can still happen. Stay sticky for
# sequential page fetches; rotate on hard blocks.
_BLOCK_STATUSES = frozenset({403, 429})
_MAX_ROTATIONS = 3
_MAX_DECODED_BYTES = 50 * 1024 * 1024

# Refresh the session cookie a few minutes before it expires. The
# ``con.ses.id`` session cookie is short-lived and the phone API rejects
# requests when it has expired, so we pre-warm by hitting a page before
# the detail/listing fetch.
_SESSION_REFRESH_THRESHOLD_SECONDS = 300


class BatdongsanDecodeError(ValueError):
    """Raised when the obfuscated response cannot be decoded."""


class BatdongsanAccessBlockedError(RuntimeError):
    """Raised when Batdongsan blocks anonymous access."""


class BatdongsanRateLimitedError(RuntimeError):
    """Raised when Batdongsan returns 429."""


class BatdongsanAccountRestrictedError(RuntimeError):
    """Raised when the authenticated account is blocked from viewing phones."""



def _access_token_expires_at(credentials: dict[str, Any] | None) -> float | None:
    """Extract the ``exp`` claim from a Batdongsan JWT access token."""
    token = credentials.get("token") if credentials else None
    if not token:
        return None
    try:
        header, payload_b64, _ = token.split(".")
        _ = header
        payload = json.loads(
            base64.urlsafe_b64decode(
                payload_b64 + "=" * (-len(payload_b64) % 4)
            )
        )
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


def _cookie_expires_at(
    credentials: dict[str, Any] | None, name: str
) -> float | None:
    """Return the ``expires`` timestamp of a named cookie from credentials."""
    if not credentials:
        return None
    cookie_input = credentials.get("cookies")
    if not cookie_input:
        return None
    try:
        cookies = cookie_string_to_playwright(cookie_input, ".batdongsan.com.vn")
        for cookie in cookies:
            if cookie.get("name") == name:
                expires = cookie.get("expires")
                if expires is not None and expires >= 0:
                    return float(expires)
    except Exception:
        pass
    return None


def _should_prewarm(credentials: dict[str, Any] | None) -> bool:
    """Check whether a new browser fetch needs a session pre-warm."""
    if not credentials:
        return False
    now = time.time()
    token_exp = _access_token_expires_at(credentials)
    session_exp = _cookie_expires_at(credentials, "con.ses.id")

    if token_exp and token_exp - now < _SESSION_REFRESH_THRESHOLD_SECONDS:
        logger.warning(
            "Batdongsan accessToken expires in %.0f seconds; "
            "pre-warming may not recover an expired token.",
            token_exp - now,
        )
        return True
    if session_exp and session_exp - now < _SESSION_REFRESH_THRESHOLD_SECONDS:
        logger.info(
            "Batdongsan con.ses.id expires in %.0f seconds; pre-warming session.",
            session_exp - now,
        )
        return True
    return False


async def _prewarm_batdongsan_session(page: Any) -> None:
    """Hit a lightweight page to refresh the session cookie before a call."""
    try:
        await page.goto(
            "https://batdongsan.com.vn/dang-nhap",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        await page.wait_for_timeout(2_000)
    except Exception as exc:
        logger.warning("Batdongsan session pre-warm failed: %s", exc)


def _make_page_setup(
    credentials: dict[str, Any] | None,
    *,
    prewarm: bool = True,
) -> Callable[[Any], Awaitable[None]]:
    """Return a page_setup callable that pre-warms and patches navigation.

    ``prewarm`` refreshes the short-lived ``con.ses.id`` cookie when it is
    close to expiration. It does not recreate an expired ``accessToken``; the
    admin still needs to provide a fresh token for that.
    """
    setup = _stealth_page_setup

    async def page_setup(page: Any) -> None:
        if prewarm and _should_prewarm(credentials):
            await _prewarm_batdongsan_session(page)
        await setup(page)

    return page_setup


def _extract_phone_from_xhr(phone_text: str, detail_url: str) -> str | None:
    """Normalize the ``DecryptPhone`` XHR response to a phone string.

    The endpoint can return either a bare phone number (e.g. ``0906 123 456``)
    or a JSON payload such as ``{"phone":"0906123456"}`` /
    ``{"message":"USER_NO_PERMISSION_TO_VIEW_PHONE"}``.
    """
    text = phone_text.strip()
    if text.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except Exception:
            return text
        if isinstance(payload, dict):
            message = payload.get("message") or ""
            if "USER_NO_PERMISSION" in message:
                logger.warning(
                    "Batdongsan phone API refused for %s: %s", detail_url, message
                )
                raise BatdongsanAccountRestrictedError(
                    f"Account cannot view phone for {detail_url}: {message}"
                )
            phone = payload.get("phone")
            if phone:
                return str(phone).strip()
            return None
    if "USER_NO_PERMISSION" in text:
        logger.warning("Batdongsan phone API refused for %s: %s", detail_url, text)
        raise BatdongsanAccountRestrictedError(
            f"Account cannot view phone for {detail_url}: {text}"
        )
    return text


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
    rule = get_batdongsan_rule()
    request_delay_s = rule.get("delays", {}).get("request_ms", 1500) / 1000.0
    retry_base_s = rule.get("delays", {}).get("retry_base_ms", 1000) / 1000.0
    max_attempts = rule.get("retries", {}).get("max_attempts", _MAX_ROTATIONS)

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": API_ORIGIN,
        "Accept": "application/json",
        "User-Agent": MOBILE_USER_AGENT,
        "Host": API_HOST,
    }

    for attempt in range(max_attempts + 1):
        try:
            await asyncio.sleep(request_delay_s)
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
            if attempt < max_attempts:
                await asyncio.sleep(_retry_delay(attempt, retry_base_s))
                continue
            raise
        except BatdongsanAccessBlockedError:
            if attempt < max_attempts:
                logger.warning(
                    "Batdongsan block on %s, rotating proxy (attempt %s/%s)",
                    P_SYNC_URL,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(_retry_delay(attempt, retry_base_s))
                continue
            raise
        except Exception as exc:
            logger.warning("Batdongsan POST %s failed: %s", P_SYNC_URL, exc)
            if attempt >= max_attempts:
                raise BatdongsanAccessBlockedError(
                    f"{P_SYNC_URL} failed after {max_attempts} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt, retry_base_s))

    raise BatdongsanAccessBlockedError(f"{P_SYNC_URL} exhausted all retries")


async def _open_stealth_session(
    credentials: dict[str, Any] | None = None,
) -> Any:
    """Open a headless browser session for Batdongsan (optional cookies/token)."""
    if AsyncStealthySession is None:
        raise BatdongsanAccessBlockedError(
            "AsyncStealthySession not available; Batdongsan web requires a browser"
        )

    extra_headers = {
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }
    session_kwargs: dict[str, Any] = {
        "headless": True,
        "solve_cloudflare": True,
        "real_chrome": True,
        "proxy": get_proxy_url(),
        "extra_headers": extra_headers,
        "google_search": False,
    }
    if credentials:
        cookie_string = credentials.get("cookies")
        if cookie_string:
            session_kwargs["cookies"] = cookie_string_to_playwright(
                cookie_string, ".batdongsan.com.vn"
            )

    session = AsyncStealthySession(**session_kwargs)
    await session.start()
    return session


async def _stealth_page_setup(page: Any) -> None:
    """Patch page navigation so heavy SSR pages return after DOM is ready.

    The default ``page.goto`` waits for the ``load`` event, which can hang when
    third-party scripts or blocked resources never complete. We want the raw
    HTML as soon as the DOM is parsed, then rely on ``network_idle=True`` in
    ``session.fetch`` to wait for in-flight XHR/resources.
    """
    original_goto = page.goto

    async def goto(url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("wait_until", "domcontentloaded")
        kwargs.setdefault("timeout", 120_000)
        return await original_goto(url, **kwargs)

    page.goto = goto


async def _stealth_response_text(response: Any) -> str:
    """Safely decode a Scrapling Response body to a string."""
    if hasattr(response, "html_content") and response.html_content:
        return response.html_content
    if hasattr(response, "text"):
        return response.text
    body = response.body
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


async def fetch_web_listings_browser(
    payload: dict[str, Any],
    *,
    credentials: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch a Batdongsan web listing page with a headless browser.

    Returns an envelope shaped like the mobile ``p_sync`` response.
    """
    city_code = payload.get("city", "")
    slug = CITY_SLUGS.get(city_code)
    if not slug:
        return {"data": [], "m": None}

    listing_type = "rent" if payload.get("ptype") == 49 else "buy"
    page = int(payload.get("page", 1))
    url = build_web_listings_url(listing_type, slug, page)

    session = await _open_stealth_session(credentials)
    try:
        response = await session.fetch(
            url,
            network_idle=True,
            load_dom=False,
            wait=15_000,
            timeout=120_000,
            page_setup=_stealth_page_setup,
        )
        html = await _stealth_response_text(response)
        items = parse_web_listings(html)
        more = "ok" if len(items) >= 20 else None
        return {"data": items, "m": more}
    except Exception as exc:
        logger.warning("Batdongsan browser web fetch %s failed: %s", url, exc)
        raise BatdongsanAccessBlockedError(f"{url} browser fetch failed") from exc
    finally:
        if hasattr(session, "close"):
            try:
                await session.close()
            except Exception as close_exc:
                logger.warning("Batdongsan session close failed: %s", close_exc)


async def fetch_detail_phone(
    detail_url: str,
    *,
    credentials: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Fetch a Batdongsan detail page and return best-effort phone info."""
    if AsyncStealthySession is None:
        return None, None

    session = await _open_stealth_session(credentials)
    phone_text: str | None = None

    async def _reveal_phone(page: Any) -> None:
        nonlocal phone_text
        try:
            phone_text = await page.evaluate(
                """() => {
                    return new Promise((resolve) => {
                        let checks = 0;
                        const timer = setInterval(() => {
                            const el = document.querySelector('span[raw], div[raw]');
                            if (el && el.getAttribute('raw')) {
                                clearInterval(timer);
                                const raw = el.getAttribute('raw');
                                const html = document.documentElement.outerHTML;
                                const pt = html.match(/window\\.pageTrackingData\\s*=\\s*\\{[\\s\\S]*?"productId":(\\d+)[\\s\\S]*?"createByUser":(\\d+)/);
                                const productId = pt ? pt[1] : '';
                                const sellerId = pt ? pt[2] : '';
                                const form = new URLSearchParams();
                                form.append('PhoneNumber', raw);
                                form.append('createLead[sellerId]', sellerId);
                                form.append('createLead[productId]', productId);
                                form.append('createLead[productType]', '0');
                                form.append('createLead[leadSourcePage]', 'BDS_LISTING_DETAILS_PAGE');
                                form.append('createLead[leadSourceAction]', 'PHONE_REVEAL');
                                form.append('createLead[fromLeadType]', 'AGENT_LISTING');
                                const xhr = new XMLHttpRequest();
                                xhr.open('POST', '/microservice-architecture-router/Product/ProductDetail/DecryptPhone', true);
                                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
                                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                                xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
                                xhr.onload = () => resolve(xhr.status === 200 ? xhr.responseText.trim() || null : null);
                                xhr.onerror = () => resolve(null);
                                xhr.send(form.toString());
                                return;
                            }
                            if (++checks > 30) {
                                clearInterval(timer);
                                resolve(null);
                            }
                        }, 500);
                    });
                }"""
            )
        except Exception as click_exc:
            logger.debug("Batdongsan phone reveal failed: %s", click_exc)

    try:
        response = await session.fetch(
            detail_url,
            network_idle=False,
            load_dom=False,
            wait=2_000,
            timeout=45_000,
            page_setup=_make_page_setup(credentials),
            page_action=_reveal_phone,
        )
        if phone_text:
            phone_text = _extract_phone_from_xhr(phone_text, detail_url)
        if phone_text:
            digits = "".join(ch for ch in phone_text if ch.isdigit())
            if len(digits) >= 9 and "*" not in phone_text:
                return phone_text, phone_text

        html = await _stealth_response_text(response)
        # Guard against redirects to a generic page (e.g. homepage) when a
        # listing is removed/moved. The final URL must still reference the
        # canonical listing id; otherwise the page may show a support hotline.
        listing_id_match = re.search(r"pr(\d+)$", detail_url or "")
        listing_id = listing_id_match.group(1) if listing_id_match else None
        final_url = getattr(response, "url", "")
        if listing_id and f"-pr{listing_id}" not in final_url:
            logger.warning(
                "Batdongsan detail page for %s redirected to %s; skipping phone parse",
                detail_url,
                final_url,
            )
            return None, None
        return parse_detail_phone(html)
    except (BatdongsanAccountRestrictedError, BatdongsanRateLimitedError):
        # Account-level failures should be handled by the caller so it can
        # rotate to another cookie and apply rate-limit cooldowns.
        raise
    except Exception as exc:
        logger.warning("Batdongsan detail phone fetch %s failed: %s", detail_url, exc)
        return None, None
    finally:
        if hasattr(session, "close"):
            try:
                await session.close()
            except Exception as close_exc:
                logger.warning("Batdongsan session close failed: %s", close_exc)


async def resolve_detail_urls(
    input_model: BatdongsanScrapeInput,
    listings: list[Any],
    *,
    credentials: dict[str, Any] | None = None,
    web_fetch_fn: WebFetchFn | None = None,
) -> None:
    """Resolve missing ``detail_url`` values by fetching the web listing pages.

    The mobile ``p_sync`` API does not include listing URLs, so we fall back to
    the SSR listing page and match cards by ``prid``.

    We first try the fast plain-HTTP path; if Cloudflare blocks it (403/429),
    we fall back to a real browser session using the stored cookies.
    """
    if not listings:
        return

    if not isinstance(input_model, BatdongsanScrapeInput):
        return

    slug = CITY_SLUGS.get(input_model.city)
    if not slug:
        return

    unresolved = {
        item.listing_id: item
        for item in listings
        if item.listing_id and not item.detail_url
    }
    if not unresolved:
        return

    listing_type = "rent" if input_model.listing_type == "rent" else "buy"
    delay = max(0.0, getattr(config, "BATDONGSAN_PAGE_DELAY_S", 0.5))

    fetch_fn = web_fetch_fn or fetch_web_listings
    session: Any | None = None

    for page in range(1, input_model.max_pages + 1):
        if not unresolved:
            break
        payload = {
            "city": input_model.city,
            "ptype": 38 if listing_type == "buy" else 49,
            "page": page,
        }
        url = build_web_listings_url(listing_type, slug, page)

        items: list[dict[str, Any]] = []
        fetch_failed = False

        try:
            result = await fetch_fn(payload)
            items = result.get("data") or []
        except (BatdongsanAccessBlockedError, BatdongsanRateLimitedError) as exc:
            logger.info(
                "Batdongsan plain-HTTP resolve blocked on page %s: %s", page, exc
            )
            fetch_failed = True

        # Fall back to a browser session if the listing page is behind
        # Cloudflare or rate-limited.
        if fetch_failed or not items:
            if not session and AsyncStealthySession is not None:
                try:
                    session = await _open_stealth_session(credentials)
                except Exception as exc:
                    logger.warning(
                        "Batdongsan could not open stealth session: %s", exc
                    )
                    break

            if session:
                try:
                    response = await session.fetch(
                        url,
                        network_idle=True,
                        load_dom=False,
                        wait=15_000,
                        timeout=120_000,
                        page_setup=_stealth_page_setup,
                    )
                    html = await _stealth_response_text(response)
                    items = parse_web_listings(html)
                except Exception as exc:
                    logger.warning(
                        "Batdongsan browser resolve detail URLs page %s failed: %s",
                        page,
                        exc,
                    )
                    break
            else:
                if not items:
                    break

        if not items:
            break

        for raw in items:
            listing_id = raw.get("id")
            if listing_id in unresolved:
                item = unresolved[listing_id]
                item.detail_url = raw.get("url")
                del unresolved[listing_id]

        if len(items) < 20:
            break

        await asyncio.sleep(delay)

    if session and hasattr(session, "close"):
        try:
            await session.close()
        except Exception as close_exc:
            logger.warning("Batdongsan session close failed: %s", close_exc)


def _retry_delay(attempt: int, base_s: float | None = None) -> float:
    """Exponential backoff for retry attempts, with a floor of 0.5s."""
    base = base_s if base_s is not None else getattr(config, "BATDONGSAN_RETRY_BACKOFF_BASE_S", 0.5)
    return max(0.5, base) * (2**attempt)


WEB_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

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
    rule = get_batdongsan_rule()
    request_delay_s = rule.get("delays", {}).get("request_ms", 1500) / 1000.0
    retry_base_s = rule.get("delays", {}).get("retry_base_ms", 1000) / 1000.0
    max_attempts = rule.get("retries", {}).get("max_attempts", _MAX_ROTATIONS)

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

    for attempt in range(max_attempts + 1):
        try:
            await asyncio.sleep(request_delay_s)
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
            if attempt < max_attempts:
                await asyncio.sleep(_retry_delay(attempt, retry_base_s))
                continue
            raise
        except BatdongsanAccessBlockedError:
            if attempt < max_attempts:
                logger.warning(
                    "Batdongsan web block on %s, rotating (attempt %s/%s)",
                    url,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(_retry_delay(attempt, retry_base_s))
                continue
            raise
        except Exception as exc:
            logger.warning("Batdongsan web GET %s failed: %s", url, exc)
            if attempt >= max_attempts:
                raise BatdongsanAccessBlockedError(
                    f"{url} failed after {max_attempts} attempts"
                ) from exc
            await asyncio.sleep(_retry_delay(attempt, retry_base_s))

    raise BatdongsanAccessBlockedError(f"{url} exhausted all retries")
