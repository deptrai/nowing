# Diff v2 — Story 10.1: Batdongsan.com.vn Scraper

diff --git a/nowing_backend/app/capabilities/batdongsan/scrape/__init__.py b/nowing_backend/app/capabilities/batdongsan/scrape/__init__.py
new file mode 100644
index 000000000..f3d9023ef
--- /dev/null
+++ b/nowing_backend/app/capabilities/batdongsan/scrape/__init__.py
@@ -0,0 +1,3 @@
+"""``batdongsan.scrape`` capability."""
+
+from __future__ import annotations
diff --git a/nowing_backend/app/capabilities/batdongsan/scrape/definition.py b/nowing_backend/app/capabilities/batdongsan/scrape/definition.py
new file mode 100644
index 000000000..942ffda70
--- /dev/null
+++ b/nowing_backend/app/capabilities/batdongsan/scrape/definition.py
@@ -0,0 +1,27 @@
+"""``batdongsan.scrape`` capability registration (billed per item)."""
+
+from __future__ import annotations
+
+from app.capabilities.core import BillingUnit, Capability, register_capability
+
+from app.proprietary.platforms.batdongsan.fetch import fetch_web_listings
+
+from .executor import build_scrape_executor
+from .schemas import ScrapeInput, ScrapeOutput
+
+BATDONGSAN_SCRAPE = Capability(
+    name="batdongsan.scrape",
+    description=(
+        "Scrape real-estate listings from batdongsan.com.vn. Use buy/rent "
+        "listing_type, city code (HN, SG, HP, BD, KH, PT, LA, HY, QNG, TN, TG "
+        "via mobile API; other provinces via web fallback when available), "
+        "and optional district_id."
+    ),
+    input_schema=ScrapeInput,
+    output_schema=ScrapeOutput,
+    executor=build_scrape_executor(web_fetch_fn=fetch_web_listings),
+    billing_unit=BillingUnit.BATDONGSAN_ITEM,
+    docs_url="/docs/connectors/native/batdongsan",
+)
+
+register_capability(BATDONGSAN_SCRAPE)
diff --git a/nowing_backend/app/capabilities/batdongsan/scrape/executor.py b/nowing_backend/app/capabilities/batdongsan/scrape/executor.py
new file mode 100644
index 000000000..14ca8c796
--- /dev/null
+++ b/nowing_backend/app/capabilities/batdongsan/scrape/executor.py
@@ -0,0 +1,121 @@
+"""``batdongsan.scrape`` executor: verb input → scraper → listings."""
+
+from __future__ import annotations
+
+import logging
+from collections.abc import Awaitable, Callable
+from typing import Any
+
+from app.capabilities.core import Executor
+from app.capabilities.core.progress import emit_progress
+from app.config import config
+from app.proprietary.platforms.batdongsan import (
+    BatdongsanScrapeOutput,
+    scrape_batdongsan,
+)
+from app.proprietary.platforms.batdongsan.fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanDecodeError,
+    BatdongsanRateLimitedError,
+)
+from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
+
+from .schemas import ScrapeInput, ScrapeOutput
+
+logger = logging.getLogger(__name__)
+
+ScrapeFn = Callable[..., Awaitable[BatdongsanScrapeOutput | dict[str, Any]]]
+
+
+def _unwrap_result(
+    result: BatdongsanScrapeOutput | dict[str, Any] | None,
+) -> dict[str, Any]:
+    if result is None:
+        return {
+            "items": [],
+            "total_items": 0,
+            "degraded": True,
+            "degradation_reason": "unknown",
+        }
+    if isinstance(result, BatdongsanScrapeOutput):
+        return {
+            "items": [item.to_output() for item in result.items],
+            "total_items": result.total_items,
+            "degraded": result.degraded,
+            "degradation_reason": result.degradation_reason,
+        }
+    return result
+
+
+def build_scrape_executor(
+    scrape_fn: ScrapeFn | None = None,
+    web_fetch_fn: ScrapeFn | None = None,
+) -> Executor:
+    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
+    scrape_fn = scrape_fn or scrape_batdongsan
+    web_fetch_fn = web_fetch_fn
+
+    async def execute(payload: ScrapeInput) -> ScrapeOutput:
+        actor_input = BatdongsanScrapeInput(**payload.model_dump(exclude_unset=True))
+
+        emit_progress(
+            "starting",
+            "Resolving Batdongsan targets",
+            total=payload.max_items,
+            unit="item",
+        )
+        try:
+            kwargs: dict[str, Any] = {"limit": payload.max_items}
+            if web_fetch_fn is not None:
+                kwargs["web_fetch_fn"] = web_fetch_fn
+            raw = await scrape_fn(actor_input, **kwargs)
+        except BatdongsanRateLimitedError:
+            logger.exception("batdongsan.scrape rate limited")
+            return ScrapeOutput(
+                items=[],
+                cost_micros=0,
+                degraded=True,
+                degradation_reason="rate_limited",
+            )
+        except BatdongsanDecodeError:
+            logger.exception("batdongsan.scrape decode error")
+            return ScrapeOutput(
+                items=[],
+                cost_micros=0,
+                degraded=True,
+                degradation_reason="decode_error",
+            )
+        except (BatdongsanAccessBlockedError, Exception) as exc:
+            logger.exception("batdongsan.scrape actor failed: %s", exc)
+            return ScrapeOutput(
+                items=[],
+                cost_micros=0,
+                degraded=True,
+                degradation_reason="api_error",
+            )
+        result = _unwrap_result(raw)
+
+        items = result.get("items", []) or []
+        total_raw = result.get("total_items", 0)
+        total = int(total_raw) if total_raw is not None else 0
+        degraded = bool(result.get("degraded", False))
+        if degraded:
+            cost = 0
+        else:
+            cost = total * getattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3500)
+
+        emit_progress(
+            "done",
+            f"Scraped {total} item(s)",
+            current=total,
+            total=payload.max_items,
+            unit="item",
+        )
+        return ScrapeOutput(
+            items=items,
+            cost_micros=cost,
+            degraded=degraded,
+            degradation_reason=result.get("degradation_reason"),
+        )
+
+    return execute
diff --git a/nowing_backend/app/capabilities/batdongsan/scrape/schemas.py b/nowing_backend/app/capabilities/batdongsan/scrape/schemas.py
new file mode 100644
index 000000000..3bbbe2929
--- /dev/null
+++ b/nowing_backend/app/capabilities/batdongsan/scrape/schemas.py
@@ -0,0 +1,66 @@
+"""``batdongsan.scrape`` I/O contracts."""
+
+from __future__ import annotations
+
+from typing import Any, Literal
+
+from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
+
+
+class ScrapeInput(BaseModel):
+    """MCP/agent-friendly surface for ``batdongsan.scrape``."""
+
+    model_config = ConfigDict(extra="allow")
+
+    listing_type: Literal["buy", "rent"] = "buy"
+    city: str
+    district_id: int | None = None
+    max_pages: int = Field(default=5, ge=1, le=20)
+    max_items: int = Field(default=10, ge=1, le=100)
+    min_price: int | None = None
+    max_price: int | None = None
+    min_area: int | None = None
+    max_area: int | None = None
+
+    @property
+    def estimated_units(self) -> int:
+        """Worst-case billable items for the pre-flight gate: ``max_items`` is a
+        hard ceiling (le=100), so no single call can exceed it."""
+        return self.max_items
+
+    @model_validator(mode="after")
+    def _price_and_area_bounds(self) -> ScrapeInput:
+        if (
+            self.min_price is not None
+            and self.max_price is not None
+            and self.min_price > self.max_price
+        ):
+            raise ValueError("min_price cannot be greater than max_price")
+        if (
+            self.min_area is not None
+            and self.max_area is not None
+            and self.min_area > self.max_area
+        ):
+            raise ValueError("min_area cannot be greater than max_area")
+        return self
+
+
+class ScrapeOutput(BaseModel):
+    """Capability-level output, extended by the proprietary ``to_output`` shape."""
+
+    model_config = ConfigDict(extra="allow")
+
+    items: list[dict[str, Any]] = Field(default_factory=list)
+    cost_micros: int = 0
+    degraded: bool = False
+    degradation_reason: str | None = None
+
+    @computed_field
+    @property
+    def total_items(self) -> int:
+        return len(self.items)
+
+    @property
+    def billable_units(self) -> int:
+        """One returned listing = one billable unit."""
+        return len(self.items)
diff --git a/nowing_backend/app/proprietary/platforms/batdongsan/__init__.py b/nowing_backend/app/proprietary/platforms/batdongsan/__init__.py
new file mode 100644
index 000000000..238bff930
--- /dev/null
+++ b/nowing_backend/app/proprietary/platforms/batdongsan/__init__.py
@@ -0,0 +1,26 @@
+"""Batdongsan.com.vn scraper (proprietary, BSL 1.1)."""
+
+from __future__ import annotations
+
+from .fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanRateLimitedError,
+    decode_response,
+    fetch_listings,
+)
+from .parsers import parse_listing, parse_listings
+from .schemas import BatdongsanListing, BatdongsanScrapeInput, BatdongsanScrapeOutput
+from .scraper import scrape_batdongsan
+
+__all__ = [
+    "BatdongsanAccessBlockedError",
+    "BatdongsanListing",
+    "BatdongsanRateLimitedError",
+    "BatdongsanScrapeInput",
+    "BatdongsanScrapeOutput",
+    "decode_response",
+    "fetch_listings",
+    "parse_listing",
+    "parse_listings",
+    "scrape_batdongsan",
+]
diff --git a/nowing_backend/app/proprietary/platforms/batdongsan/fetch.py b/nowing_backend/app/proprietary/platforms/batdongsan/fetch.py
new file mode 100644
index 000000000..96ac6c4d2
--- /dev/null
+++ b/nowing_backend/app/proprietary/platforms/batdongsan/fetch.py
@@ -0,0 +1,321 @@
+"""Fetch and decode the Batdongsan mobile API response."""
+
+from __future__ import annotations
+
+import asyncio
+import base64
+import json
+import logging
+import time
+import zlib
+from typing import Any
+
+from scrapling.fetchers import AsyncFetcher
+
+from app.config import config
+from app.utils.proxy import get_proxy_url
+
+from .parsers import parse_web_listings
+
+logger = logging.getLogger(__name__)
+
+API_ORIGIN = "https://batdongsan.com.vn"
+API_HOST = "apimap.batdongsan.com.vn"
+P_SYNC_URL = "https://apimap.batdongsan.com.vn/api/p_sync"
+MOBILE_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 8.0.0; SM-G9500 Build/R16NW)"
+
+# The mobile endpoint rarely blocks, but a 429 can still happen. Stay sticky for
+# sequential page fetches; rotate on hard blocks.
+_BLOCK_STATUSES = frozenset({403, 429})
+_MAX_ROTATIONS = 3
+_MAX_DECODED_BYTES = 50 * 1024 * 1024
+
+
+class BatdongsanDecodeError(ValueError):
+    """Raised when the obfuscated response cannot be decoded."""
+
+
+class BatdongsanAccessBlockedError(RuntimeError):
+    """Raised when Batdongsan blocks anonymous access."""
+
+
+class BatdongsanRateLimitedError(RuntimeError):
+    """Raised when Batdongsan returns 429."""
+
+
+def _nibble_swap(data: bytes) -> bytes:
+    """Swap the high and low nibble of each byte (self-inverse)."""
+    return bytes(((b & 0x0F) << 4) | (b >> 4) for b in data)
+
+
+def decode_response(raw: bytes) -> dict[str, Any]:
+    """Decode the obfuscated ``p_sync`` response.
+
+    Pipeline: gzip (optional) → base64 → nibble-swap → Latin-1 JSON.
+    """
+    if len(raw) > _MAX_DECODED_BYTES:
+        raise BatdongsanDecodeError("response exceeds size cap")
+    if raw[:2] == b"\x1f\x8b":
+        # ``gzip.decompress`` gained ``max_length`` only in Python 3.13; use a
+        # zlib decompressobj so the output stays bounded on 3.12 as well.
+        try:
+            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
+            raw = decompressor.decompress(raw, _MAX_DECODED_BYTES + 1)
+        except Exception as exc:
+            raise BatdongsanDecodeError("failed to decompress gzip layer") from exc
+        if len(raw) > _MAX_DECODED_BYTES or decompressor.unconsumed_tail:
+            raise BatdongsanDecodeError("gzip layer exceeds size cap")
+
+    try:
+        decoded = base64.b64decode(raw)
+    except Exception as exc:
+        raise BatdongsanDecodeError("failed to base64-decode response") from exc
+
+    swapped = _nibble_swap(decoded)
+    try:
+        text = swapped.decode("latin-1")
+    except Exception as exc:
+        raise BatdongsanDecodeError(
+            "failed to latin-1 decode nibble-swapped bytes"
+        ) from exc
+
+    try:
+        return json.loads(text)
+    except Exception as exc:
+        raise BatdongsanDecodeError(
+            "failed to parse JSON from decoded response"
+        ) from exc
+
+
+def _raise_for_status(status: int, url: str) -> None:
+    if status == 429:
+        raise BatdongsanRateLimitedError(f"{url} returned 429")
+    if status in {403, *range(500, 600)}:
+        raise BatdongsanAccessBlockedError(f"{url} returned {status}")
+    if status != 200:
+        raise BatdongsanAccessBlockedError(f"{url} returned {status}")
+
+
+async def fetch_listings(payload: dict[str, Any]) -> dict[str, Any]:
+    """POST to ``p_sync`` and return the decoded JSON envelope."""
+    headers = {
+        "Content-Type": "application/x-www-form-urlencoded",
+        "Origin": API_ORIGIN,
+        "Accept": "application/json",
+        "User-Agent": MOBILE_USER_AGENT,
+        "Host": API_HOST,
+    }
+
+    for attempt in range(_MAX_ROTATIONS + 1):
+        try:
+            started = time.perf_counter()
+            page = await AsyncFetcher.post(
+                P_SYNC_URL,
+                data=payload,
+                headers=headers,
+                proxy=get_proxy_url(),
+                stealthy_headers=True,
+                timeout=30,
+            )
+            fetch_ms = (time.perf_counter() - started) * 1000
+            logger.info(
+                "[batdongsan][perf] url=%s status=%s fetch_ms=%.1f",
+                P_SYNC_URL,
+                page.status,
+                fetch_ms,
+            )
+
+            if page.status == 200:
+                return decode_response(page.body)
+
+            _raise_for_status(page.status, P_SYNC_URL)
+        except BatdongsanDecodeError:
+            raise
+        except BatdongsanRateLimitedError:
+            if attempt < _MAX_ROTATIONS:
+                await asyncio.sleep(_retry_delay(attempt))
+                continue
+            raise
+        except BatdongsanAccessBlockedError:
+            if attempt < _MAX_ROTATIONS:
+                logger.warning(
+                    "Batdongsan block on %s, rotating proxy (attempt %s/%s)",
+                    P_SYNC_URL,
+                    attempt + 1,
+                    _MAX_ROTATIONS,
+                )
+                await asyncio.sleep(_retry_delay(attempt))
+                continue
+            raise
+        except Exception as exc:
+            logger.warning("Batdongsan POST %s failed: %s", P_SYNC_URL, exc)
+            if attempt >= _MAX_ROTATIONS:
+                raise BatdongsanAccessBlockedError(
+                    f"{P_SYNC_URL} failed after {_MAX_ROTATIONS} attempts"
+                ) from exc
+            await asyncio.sleep(_retry_delay(attempt))
+
+    raise BatdongsanAccessBlockedError(f"{P_SYNC_URL} exhausted all retries")
+
+
+def _retry_delay(attempt: int) -> float:
+    """Exponential backoff for retry attempts, with a floor of 0.5s."""
+    base = max(0.5, getattr(config, "BATDONGSAN_RETRY_BACKOFF_BASE_S", 0.5))
+    return base * (2**attempt)
+
+
+WEB_USER_AGENT = (
+    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
+    "AppleWebKit/537.36 (KHTML, like Gecko) "
+    "Chrome/126.0.0.0 Safari/537.36"
+)
+
+CITY_SLUGS: dict[str, str] = {
+    "AG": "an-giang",
+    "BD": "binh-duong",
+    "BDI": "binh-dinh",
+    "BG": "bac-giang",
+    "BK": "bac-kan",
+    "BL": "bac-lieu",
+    "BN": "bac-ninh",
+    "BP": "binh-phuoc",
+    "BT": "ben-tre",
+    "BTH": "binh-thuan",
+    "CB": "cao-bang",
+    "CM": "ca-mau",
+    "CT": "can-tho",
+    "DI": "dien-bien",
+    "DKL": "dak-lak",
+    "DN": "da-nang",
+    "DNO": "dak-nong",
+    "DT": "dong-thap",
+    "GL": "gia-lai",
+    "HD": "hai-duong",
+    "HG": "ha-giang",
+    "HN": "ha-noi",
+    "HP": "hai-phong",
+    "HT": "ha-tinh",
+    "HUG": "hau-giang",
+    "HY": "hung-yen",
+    "KH": "khanh-hoa",
+    "KG": "kien-giang",
+    "KT": "kon-tum",
+    "LA": "long-an",
+    "LB": "long-bien",
+    "LC": "lao-cai",
+    "LCH": "lai-chau",
+    "LD": "lam-dong",
+    "LS": "lang-son",
+    "NA": "nghe-an",
+    "NB": "ninh-binh",
+    "ND": "nam-dinh",
+    "NT": "ninh-thuan",
+    "PT": "phu-tho",
+    "PY": "phu-yen",
+    "QB": "quang-binh",
+    "QN": "quang-ninh",
+    "QNG": "quang-ngai",
+    "QT": "quang-tri",
+    "SG": "tp-hcm",
+    "SL": "son-la",
+    "ST": "soc-trang",
+    "TB": "thai-binh",
+    "TG": "tien-giang",
+    "TH": "thanh-hoa",
+    "TN": "thai-nguyen",
+    "TQ": "tuyen-quang",
+    "TV": "tra-vinh",
+    "TTH": "hue",
+    "VL": "vinh-long",
+    "VT": "ba-ria-vung-tau",
+    "YB": "yen-bai",
+}
+
+
+def build_web_listings_url(listing_type: str, slug: str, page: int) -> str:
+    """Build the SSR URL for a city-level buy/rent listing page."""
+    if listing_type == "buy":
+        path = f"/ban-nha-dat-{slug}"
+    else:
+        path = f"/nha-dat-cho-thue-{slug}"
+    if page > 1:
+        path = f"{path}/p{page}"
+    return f"{API_ORIGIN}{path}"
+
+
+async def fetch_web_listings(payload: dict[str, Any]) -> dict[str, Any]:
+    """GET the SSR web page and parse listing cards.
+
+    Returns an envelope shaped like the mobile ``p_sync`` response
+    (``{"data": [...], "m": "ok" | None}``) so the scraper can treat
+    both fetchers uniformly.
+    """
+    city_code = payload.get("city", "")
+    slug = CITY_SLUGS.get(city_code)
+    if not slug:
+        return {"data": [], "m": None}
+
+    listing_type = "rent" if payload.get("ptype") == 49 else "buy"
+    page = int(payload.get("page", 1))
+    url = build_web_listings_url(listing_type, slug, page)
+
+    headers = {
+        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
+        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
+        "User-Agent": WEB_USER_AGENT,
+    }
+
+    for attempt in range(_MAX_ROTATIONS + 1):
+        try:
+            started = time.perf_counter()
+            resp = await AsyncFetcher.get(
+                url,
+                headers=headers,
+                proxy=get_proxy_url(),
+                stealthy_headers=True,
+                timeout=30,
+            )
+            fetch_ms = (time.perf_counter() - started) * 1000
+            logger.info(
+                "[batdongsan][perf][web] url=%s status=%s fetch_ms=%.1f",
+                url,
+                resp.status,
+                fetch_ms,
+            )
+
+            if resp.status == 200:
+                body = resp.body
+                if isinstance(body, bytes):
+                    body = body.decode("utf-8", errors="replace")
+                items = parse_web_listings(body)
+                more = "ok" if len(items) >= 20 else None
+                return {"data": items, "m": more}
+
+            _raise_for_status(resp.status, url)
+        except BatdongsanDecodeError:
+            raise
+        except BatdongsanRateLimitedError:
+            if attempt < _MAX_ROTATIONS:
+                await asyncio.sleep(_retry_delay(attempt))
+                continue
+            raise
+        except BatdongsanAccessBlockedError:
+            if attempt < _MAX_ROTATIONS:
+                logger.warning(
+                    "Batdongsan web block on %s, rotating (attempt %s/%s)",
+                    url,
+                    attempt + 1,
+                    _MAX_ROTATIONS,
+                )
+                await asyncio.sleep(_retry_delay(attempt))
+                continue
+            raise
+        except Exception as exc:
+            logger.warning("Batdongsan web GET %s failed: %s", url, exc)
+            if attempt >= _MAX_ROTATIONS:
+                raise BatdongsanAccessBlockedError(
+                    f"{url} failed after {_MAX_ROTATIONS} attempts"
+                ) from exc
+            await asyncio.sleep(_retry_delay(attempt))
+
+    raise BatdongsanAccessBlockedError(f"{url} exhausted all retries")
diff --git a/nowing_backend/app/proprietary/platforms/batdongsan/parsers.py b/nowing_backend/app/proprietary/platforms/batdongsan/parsers.py
new file mode 100644
index 000000000..351df9e92
--- /dev/null
+++ b/nowing_backend/app/proprietary/platforms/batdongsan/parsers.py
@@ -0,0 +1,208 @@
+"""Pure, I/O-free parsing of Batdongsan ``p_sync`` listing data."""
+
+from __future__ import annotations
+
+import re
+from typing import Any
+
+from bs4 import BeautifulSoup
+
+from .schemas import BatdongsanListing
+
+# District/city prefixes seen in Vietnamese addresses. Quận = urban district,
+# Huyện = rural district, Thị xã = town, TP = city.
+_DISTRICT_PREFIXES = ("Quận", "Huyện", "Thị xã", "TX.", "H.")
+_CITY_PREFIXES = ("TP.", "Tỉnh", "Thành phố")
+
+
+def _normalize_whitespace(value: Any) -> str | None:
+    if not isinstance(value, str):
+        return None
+    cleaned = value.strip()
+    return cleaned if cleaned else None
+
+
+def _extract_number_and_unit(text: str | None) -> str | None:
+    """Pull the leading ``number unit`` token out of strings like ``75 m²``.
+
+    Handles ranges (``72-75 m²``) by keeping the dash inside the number group
+    so it is never mistaken for a unit separator.
+    """
+    if not text:
+        return None
+    match = re.search(r"([\d.,]+(?:-[\d.,]+)?)\s*([^\d.,\s-]+)", text)
+    if match:
+        return f"{match.group(1)} {match.group(2)}".strip()
+    return text.strip() or None
+
+
+def _parse_price(raw: Any) -> tuple[str | None, str | None]:
+    """Return ``(price, price_raw)`` from a Batdongsan price string.
+
+    ``Thỏa thuận`` and non-price strings are kept in ``price_raw`` only.
+    """
+    raw_str = _normalize_whitespace(raw)
+    if raw_str is None:
+        return None, None
+
+    if re.search(r"[\d.,]+", raw_str):
+        normalized = _extract_number_and_unit(raw_str) or raw_str
+        return normalized, raw_str
+    return None, raw_str
+
+
+def _parse_area(raw: Any) -> tuple[str | None, str | None]:
+    """Return ``(area, area_raw)`` from an area string like ``75 m²``."""
+    raw_str = _normalize_whitespace(raw)
+    if raw_str is None:
+        return None, None
+    if re.search(r"[\d.,]+", raw_str):
+        normalized = _extract_number_and_unit(raw_str) or raw_str
+        return normalized, raw_str
+    return None, raw_str
+
+
+def _strip_prefixes(text: str, prefixes: tuple[str, ...]) -> str:
+    for prefix in prefixes:
+        if text.startswith(prefix):
+            text = text[len(prefix) :].strip(" .")
+    return text.strip() or text
+
+
+def _split_address(address: str | None) -> tuple[str | None, str | None]:
+    """Best-effort split ``location`` into ``(district, city)``.
+
+    Addresses are usually comma-delimited: ``Ward, District, City`` or
+    ``Street, Ward, District, City``. The last segment is city, the one before
+    it is district. Only prefixes are stripped, no translation.
+    """
+    if not address:
+        return None, None
+    parts = [p.strip() for p in address.split(",") if p.strip()]
+    if not parts:
+        return None, None
+    city = _strip_prefixes(parts[-1], _CITY_PREFIXES)
+    district = (
+        _strip_prefixes(parts[-2], _DISTRICT_PREFIXES) if len(parts) >= 2 else None
+    )
+    return district, city
+
+
+def _to_float(value: Any) -> float | None:
+    try:
+        return float(value)
+    except (TypeError, ValueError):
+        return None
+
+
+def _to_int(value: Any) -> int | None:
+    if isinstance(value, bool):
+        return None
+    if isinstance(value, int):
+        return value
+    if isinstance(value, float):
+        return int(value)
+    return None
+
+
+def parse_listing(raw: dict[str, Any]) -> BatdongsanListing:
+    """Map a single raw data dict to a typed listing."""
+    address = _normalize_whitespace(raw.get("address"))
+    district, city = _split_address(address) if address else (None, None)
+    price, price_raw = _parse_price(raw.get("price"))
+    area, area_raw = _parse_area(raw.get("area"))
+
+    # If the city is still empty after stripping prefixes, fall back to the
+    # last segment untouched.
+    if not city:
+        parts = [p.strip() for p in (address or "").split(",") if p.strip()]
+        city = parts[-1] if parts else None
+
+    return BatdongsanListing(
+        dataType="batdongsan_listing",
+        listing_id=_to_int(raw.get("id")),
+        title=_normalize_whitespace(raw.get("title")),
+        price=price,
+        price_raw=price_raw,
+        area=area,
+        area_raw=area_raw,
+        location=address,
+        district=district,
+        city=city,
+        post_date=_normalize_whitespace(raw.get("date")),
+        thumbnail_url=_normalize_whitespace(raw.get("avatar")),
+        detail_url=_normalize_whitespace(raw.get("url")),
+        latitude=_to_float(raw.get("lat")),
+        longitude=_to_float(raw.get("lon")),
+        category=_normalize_whitespace(raw.get("cat")),
+        rooms=_to_int(raw.get("room")),
+    )
+
+
+def parse_listings(raw_items: list[dict[str, Any]]) -> list[BatdongsanListing]:
+    """Map a list of raw Batdongsan data dicts to typed listings."""
+    if not raw_items:
+        return []
+    return [parse_listing(item) for item in raw_items if isinstance(item, dict)]
+
+
+_WEB_ORIGIN = "https://batdongsan.com.vn"
+
+
+def parse_web_listings(html: str) -> list[dict[str, Any]]:
+    """Parse SSR listing cards from a batdongsan.com.vn web page.
+
+    Returns raw dicts shaped like mobile ``p_sync`` items so
+    :func:`parse_listings` can consume them uniformly.
+    """
+    soup = BeautifulSoup(html, "lxml")
+    cards = soup.select("div.js__card-listing")
+    items: list[dict[str, Any]] = []
+    for card in cards:
+        prid = card.get("prid")
+        if not prid:
+            continue
+        try:
+            listing_id = int(prid)
+        except (TypeError, ValueError):
+            continue
+
+        link = card.select_one("a.js__product-link-for-product-id")
+        href = (link.get("href") or "") if link else ""
+        detail_url = f"{_WEB_ORIGIN}{href}" if href else None
+
+        title_el = card.select_one("span.js__card-title")
+        title = title_el.get_text(strip=True) if title_el else None
+
+        price_el = card.select_one("span.re__card-config-price")
+        price = price_el.get_text(strip=True) if price_el else None
+
+        area_el = card.select_one("span.re__card-config-area")
+        area = area_el.get_text(strip=True) if area_el else None
+
+        loc_el = card.select_one("div.re__card-location")
+        location = loc_el.get_text(strip=True) if loc_el else None
+
+        avatar = card.get("prav")
+
+        bedroom_el = card.select_one("span.re__card-config-bedroom")
+        room: int | None = None
+        if bedroom_el:
+            aria = bedroom_el.get("aria-label") or ""
+            m = re.search(r"\d+", aria)
+            if m:
+                room = int(m.group(0))
+
+        items.append(
+            {
+                "id": listing_id,
+                "title": title,
+                "price": price,
+                "area": area,
+                "address": location,
+                "avatar": avatar,
+                "url": detail_url,
+                "room": room,
+            }
+        )
+    return items
diff --git a/nowing_backend/app/proprietary/platforms/batdongsan/schemas.py b/nowing_backend/app/proprietary/platforms/batdongsan/schemas.py
new file mode 100644
index 000000000..6cffdead3
--- /dev/null
+++ b/nowing_backend/app/proprietary/platforms/batdongsan/schemas.py
@@ -0,0 +1,69 @@
+# ruff: noqa: N815 - field names intentionally use the public camelCase API
+"""Input/output models for the Batdongsan scraper."""
+
+from __future__ import annotations
+
+from typing import Any, Literal
+
+from pydantic import BaseModel, ConfigDict, Field
+
+
+class BatdongsanScrapeInput(BaseModel):
+    """Proprietary scraper input."""
+
+    model_config = ConfigDict(extra="allow")
+
+    listing_type: Literal["buy", "rent"] = "buy"
+    city: str = "HN"
+    district_id: int | None = None
+    max_pages: int = Field(default=5, ge=1, le=20)
+    max_items: int = Field(default=10, ge=1, le=100)
+    min_price: int | None = None
+    max_price: int | None = None
+    min_area: int | None = None
+    max_area: int | None = None
+
+
+class BatdongsanListing(BaseModel):
+    """Single flat Batdongsan listing item."""
+
+    model_config = ConfigDict(extra="allow")
+
+    dataType: Literal["batdongsan_listing"] = "batdongsan_listing"
+    listing_id: int | None = None
+    title: str | None = None
+    price: str | None = None
+    price_raw: str | None = None
+    area: str | None = None
+    area_raw: str | None = None
+    location: str | None = None
+    district: str | None = None
+    city: str | None = None
+    post_date: str | None = None
+    thumbnail_url: str | None = None
+    detail_url: str | None = None
+    phone: str | None = None
+    phone_display: str | None = None
+    latitude: float | None = None
+    longitude: float | None = None
+    category: str | None = None
+    rooms: int | None = None
+    scrapedAt: str | None = None
+
+    def to_output(self) -> dict[str, Any]:
+        """Serialize to a flat dict for downstream consumers."""
+        return self.model_dump(exclude_none=False)
+
+
+class BatdongsanScrapeOutput(BaseModel):
+    """Scraper-level output (not the capability contract)."""
+
+    items: list[BatdongsanListing] = Field(default_factory=list)
+    total_items: int = 0
+    degraded: bool = False
+    degradation_reason: str | None = None
+
+    @property
+    def billable_units(self) -> int:
+        """One returned listing = one billable unit."""
+        return self.total_items
diff --git a/nowing_backend/app/proprietary/platforms/batdongsan/scraper.py b/nowing_backend/app/proprietary/platforms/batdongsan/scraper.py
new file mode 100644
index 000000000..c5af68b56
--- /dev/null
+++ b/nowing_backend/app/proprietary/platforms/batdongsan/scraper.py
@@ -0,0 +1,223 @@
+"""Orchestrator for the Batdongsan scraper."""
+
+from __future__ import annotations
+
+import asyncio
+import logging
+from collections.abc import Awaitable, Callable
+from datetime import UTC, datetime
+from typing import Any
+
+from app.config import config
+
+from .fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanDecodeError,
+    BatdongsanRateLimitedError,
+    fetch_listings,
+)
+from .parsers import parse_listings
+from .schemas import BatdongsanListing, BatdongsanScrapeInput, BatdongsanScrapeOutput
+
+logger = logging.getLogger(__name__)
+
+FetchFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
+
+# Retry a single page this many times before giving up on that page.
+_MAX_RETRIES = 2
+
+
+def now_iso() -> str:
+    """UTC now as an ISO-8601 millisecond string."""
+    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
+
+
+def _build_page_payload(
+    input_model: BatdongsanScrapeInput, page: int
+) -> dict[str, Any]:
+    payload = {
+        "ptype": 38 if input_model.listing_type == "buy" else 49,
+        "cate": 0,
+        "city": input_model.city,
+        "dist": input_model.district_id if input_model.district_id is not None else -1,
+        "ward": -1,
+        "street": -1,
+        "room": -1,
+        "direct": -1,
+        "minprice": input_model.min_price if input_model.min_price is not None else 0,
+        "maxprice": input_model.max_price if input_model.max_price is not None else 0,
+        "minarea": input_model.min_area if input_model.min_area is not None else 0,
+        "maxarea": input_model.max_area if input_model.max_area is not None else 0,
+        "projectid": -1,
+        "sort": 0,
+        "page": page,
+        "searchType": 0,
+        "client": "android",
+        "m": "list",
+        "pagesize": 20,
+    }
+    return payload
+
+
+def _page_delay() -> float:
+    """Pacing between page requests, so pagination stays polite."""
+    return max(0.0, getattr(config, "BATDONGSAN_PAGE_DELAY_S", 0.5))
+
+
+def _web_fallback_applicable(input_model: BatdongsanScrapeInput) -> bool:
+    """Web fallback only for city-level queries without price/area bounds.
+
+    The SSR URL cannot express district or numeric filters, so falling back
+    for filtered queries would return results that violate the user's
+    constraints.
+    """
+    return (
+        input_model.district_id is None
+        and input_model.min_price is None
+        and input_model.max_price is None
+        and input_model.min_area is None
+        and input_model.max_area is None
+    )
+
+
+async def scrape_batdongsan(
+    input_model: BatdongsanScrapeInput,
+    *,
+    limit: int | None = None,
+    fetch_fn: FetchFn | None = None,
+    web_fetch_fn: FetchFn | None = None,
+) -> BatdongsanScrapeOutput:
+    """Collect listings across pages, honoring caps and degradation.
+
+    ``fetch_fn`` is a seam for tests; production uses :func:`fetch_listings`.
+    ``web_fetch_fn`` is an optional SSR web fallback used when the mobile API
+    returns an empty first page for a city-level query (e.g. provinces not
+    indexed by the mobile API).
+    """
+    fetch = fetch_fn or fetch_listings
+    cap = limit if limit is not None else input_model.max_items
+    max_pages = input_model.max_pages
+
+    items: list[BatdongsanListing] = []
+    seen_ids: set[int] = set()
+    degraded = False
+    degradation_reason: str | None = None
+    rate_limited_seen = False
+    using_web = False
+
+    for page in range(1, max_pages + 1):
+        if len(items) >= cap:
+            break
+
+        payload = _build_page_payload(input_model, page)
+        page_data: list[dict[str, Any]] = []
+        page_meta: Any = None
+        page_failed = False
+
+        active_fetch = web_fetch_fn if using_web else fetch
+        for attempt in range(_MAX_RETRIES + 1):
+            try:
+                result = await active_fetch(payload)
+                page_data = result.get("data") or []
+                page_meta = result.get("m")
+                break
+            except BatdongsanRateLimitedError:
+                rate_limited_seen = True
+                if attempt < _MAX_RETRIES:
+                    await asyncio.sleep(_page_delay())
+                    continue
+                page_failed = True
+                break
+            except BatdongsanDecodeError:
+                degraded = True
+                degradation_reason = "decode_error"
+                page_failed = True
+                break
+            except (BatdongsanAccessBlockedError, Exception):
+                page_failed = True
+                break
+
+        # Web fallback: only on page 1 when mobile gave nothing, the
+        # query is city-level, and a web fetcher is wired.
+        if (
+            page == 1
+            and not page_data
+            and not page_failed
+            and web_fetch_fn is not None
+            and _web_fallback_applicable(input_model)
+        ):
+            for attempt in range(_MAX_RETRIES + 1):
+                try:
+                    web_result = await web_fetch_fn(payload)
+                    web_data = web_result.get("data") or []
+                    if web_data:
+                        page_data = web_data
+                        page_meta = web_result.get("m")
+                        using_web = True
+                        logger.info(
+                            "[batdongsan] web fallback engaged for city=%s "
+                            "page=%s (%d items)",
+                            input_model.city,
+                            page,
+                            len(web_data),
+                        )
+                    break
+                except BatdongsanRateLimitedError:
+                    if attempt < _MAX_RETRIES:
+                        await asyncio.sleep(_page_delay())
+                        continue
+                    break
+                except (BatdongsanAccessBlockedError, BatdongsanDecodeError, Exception):
+                    break
+
+        if page_failed:
+            if degradation_reason is None:
+                degradation_reason = (
+                    "rate_limited" if rate_limited_seen else "api_error"
+                )
+            degraded = True
+            break
+
+        if not isinstance(page_data, list):
+            degraded = True
+            degradation_reason = "api_error"
+            break
+
+        # An empty first page means the district/constraints matched nothing —
+        # a user mistake or an invalid ``dist``, not a normal end of results.
+        if page == 1 and not page_data:
+            degraded = True
+            degradation_reason = "empty"
+            break
+
+        for listing in parse_listings(page_data):
+            if len(items) >= cap:
+                break
+            # Promoted listings can repeat across pages; dedupe so the same
+            # listing is never returned (or billed) twice.
+            if listing.listing_id is not None:
+                if listing.listing_id in seen_ids:
+                    continue
+                seen_ids.add(listing.listing_id)
+            items.append(listing)
+
+        # ``m`` (more flag) is ``None`` at end of list; also stop on empty page.
+        if not page_data or page_meta is None:
+            break
+
+        if page < max_pages and len(items) < cap:
+            await asyncio.sleep(_page_delay())
+
+    for item in items:
+        item.scrapedAt = now_iso()
+
+    if rate_limited_seen:
+        degraded = True
+        degradation_reason = "rate_limited"
+
+    return BatdongsanScrapeOutput(
+        items=items,
+        total_items=len(items),
+        degraded=degraded,
+        degradation_reason=degradation_reason,
+    )
diff --git a/nowing_backend/app/services/scraper_platform_account_service.py b/nowing_backend/app/services/scraper_platform_account_service.py
new file mode 100644
index 000000000..577eb3982
--- /dev/null
+++ b/nowing_backend/app/services/scraper_platform_account_service.py
@@ -0,0 +1,160 @@
+"""Service for managing admin-supplied scraper platform credentials."""
+
+from __future__ import annotations
+
+import json
+import logging
+from http.cookies import SimpleCookie
+from typing import Any
+
+from sqlalchemy import select, update as sql_update
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.config import config
+from app.db import ScraperPlatformAccount, async_session_maker
+from app.utils.oauth_security import TokenEncryption
+
+logger = logging.getLogger(__name__)
+
+
+def _get_token_encryption() -> TokenEncryption | None:
+    if not config.SECRET_KEY:
+        logger.warning("SECRET_KEY not set; scraper credentials cannot be encrypted")
+        return None
+    return TokenEncryption(config.SECRET_KEY)
+
+
+def encrypt_credentials(credentials: dict[str, Any]) -> str:
+    enc = _get_token_encryption()
+    if enc is None:
+        raise ValueError("SECRET_KEY must be set to store scraper credentials")
+    return enc.encrypt_token(json.dumps(credentials, ensure_ascii=False))
+
+
+def decrypt_credentials(encrypted: str | None) -> dict[str, Any] | None:
+    if not encrypted:
+        return None
+    enc = _get_token_encryption()
+    if enc is None:
+        raise ValueError("SECRET_KEY must be set to decrypt scraper credentials")
+    raw = enc.decrypt_token(encrypted)
+    try:
+        return json.loads(raw)
+    except Exception as exc:
+        raise ValueError("Stored scraper credentials are not valid JSON") from exc
+
+
+def cookie_string_to_playwright(cookie_string: str, domain: str) -> list[dict[str, str]]:
+    """Parse a ``name=value; ...`` string into Playwright ``add_cookies`` format."""
+    jar = SimpleCookie(cookie_string)
+    return [
+        {"name": key, "value": morsel.value, "domain": domain, "path": "/"}
+        for key, morsel in jar.items()
+    ]
+
+
+def cookie_string_to_dict(cookie_string: str) -> dict[str, str]:
+    """Parse a ``name=value; ...`` string into a plain name -> value dict."""
+    jar = SimpleCookie(cookie_string)
+    return {key: morsel.value for key, morsel in jar.items()}
+
+
+class ScraperPlatformAccountService:
+    def __init__(self, session: AsyncSession):
+        self.session = session
+
+    async def list(self, platform: str | None = None) -> list[ScraperPlatformAccount]:
+        stmt = select(ScraperPlatformAccount)
+        if platform:
+            stmt = stmt.where(ScraperPlatformAccount.platform == platform)
+        result = await self.session.execute(stmt.order_by(ScraperPlatformAccount.created_at))
+        return list(result.scalars().all())
+
+    async def get(self, account_id: int) -> ScraperPlatformAccount | None:
+        return await self.session.get(ScraperPlatformAccount, account_id)
+
+    async def get_default(self, platform: str) -> ScraperPlatformAccount | None:
+        result = await self.session.execute(
+            select(ScraperPlatformAccount)
+            .where(
+                ScraperPlatformAccount.platform == platform,
+                ScraperPlatformAccount.is_enabled.is_(True),
+                ScraperPlatformAccount.is_default.is_(True),
+            )
+            .order_by(ScraperPlatformAccount.created_at.desc())
+            .limit(1)
+        )
+        return result.scalars().first()
+
+    async def get_default_credentials(self, platform: str) -> dict[str, Any] | None:
+        account = await self.get_default(platform)
+        if not account:
+            return None
+        return decrypt_credentials(account.encrypted_credentials)
+
+    async def create(
+        self,
+        platform: str,
+        label: str | None,
+        is_enabled: bool,
+        is_default: bool,
+        credentials: dict[str, Any] | None,
+    ) -> ScraperPlatformAccount:
+        if is_default:
+            await self._clear_default_for_platform(platform)
+        account = ScraperPlatformAccount(
+            platform=platform,
+            label=label,
+            is_enabled=is_enabled,
+            is_default=is_default,
+            encrypted_credentials=encrypt_credentials(credentials) if credentials else None,
+        )
+        self.session.add(account)
+        await self.session.commit()
+        await self.session.refresh(account)
+        return account
+
+    async def update(
+        self,
+        account: ScraperPlatformAccount,
+        updates: dict[str, Any],
+    ) -> ScraperPlatformAccount:
+        label = updates.get("label")
+        if label is not None or "label" in updates:
+            account.label = label
+        is_enabled = updates.get("is_enabled")
+        if is_enabled is not None or "is_enabled" in updates:
+            account.is_enabled = is_enabled
+        is_default = updates.get("is_default")
+        if is_default is not None or "is_default" in updates:
+            if is_default:
+                await self._clear_default_for_platform(account.platform)
+            account.is_default = is_default
+        credentials = updates.get("credentials")
+        if credentials is not None or "credentials" in updates:
+            account.encrypted_credentials = (
+                encrypt_credentials(credentials) if credentials else None
+            )
+        await self.session.commit()
+        await self.session.refresh(account)
+        return account
+
+    async def delete(self, account: ScraperPlatformAccount) -> None:
+        await self.session.delete(account)
+        await self.session.commit()
+
+    async def _clear_default_for_platform(self, platform: str) -> None:
+        await self.session.execute(
+            sql_update(ScraperPlatformAccount)
+            .where(
+                ScraperPlatformAccount.platform == platform,
+                ScraperPlatformAccount.is_default.is_(True),
+            )
+            .values(is_default=False)
+        )
+
+
+async def get_default_credentials(platform: str) -> dict[str, Any] | None:
+    """Fetch the default enabled credentials for a platform without a pre-existing session."""
+    async with async_session_maker() as session:
+        return await ScraperPlatformAccountService(session).get_default_credentials(platform)
diff --git a/nowing_backend/tests/integration/capabilities/batdongsan/scrape/test_batdongsan_scrape.py b/nowing_backend/tests/integration/capabilities/batdongsan/scrape/test_batdongsan_scrape.py
new file mode 100644
index 000000000..d354f43ee
--- /dev/null
+++ b/nowing_backend/tests/integration/capabilities/batdongsan/scrape/test_batdongsan_scrape.py
@@ -0,0 +1,139 @@
+"""Integration tests for ``batdongsan.scrape`` (Story 10.1).
+
+Default run replays the recorded ``p_sync`` envelope through the full
+scraper pipeline and verifies billing against a real Postgres session.
+Set ``SCRAPE_LIVE=1`` to additionally hit the real mobile API.
+"""
+
+from __future__ import annotations
+
+import json
+import os
+from pathlib import Path
+
+import pytest
+from sqlalchemy import select
+
+from app.capabilities.core.billing import charge_capability
+from app.capabilities.core.types import BillingUnit, CapabilityContext
+from app.config import config
+from app.db import TokenUsage
+from app.proprietary.platforms.batdongsan.schemas import (
+    BatdongsanScrapeInput,
+    BatdongsanScrapeOutput,
+)
+from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan
+
+pytestmark = [pytest.mark.integration]
+
+_FIXTURE = (
+    Path(__file__).resolve().parents[4]
+    / "unit/platforms/batdongsan/fixtures/sample_p_sync.json"
+)
+
+
+def _load_fixture() -> dict:
+    return json.loads(_FIXTURE.read_text(encoding="utf-8"))
+
+
+async def _fixture_fetcher(_payload: dict) -> dict:
+    """Replay the recorded envelope for page 1; end pagination afterwards."""
+    if _payload.get("page", 1) > 1:
+        return {"data": [], "m": None}
+    return _load_fixture()
+
+
+@pytest.mark.asyncio
+async def test_recorded_fixture_roundtrip_typed_listings():
+    """AC-1/AC-2/AC-3: fixture replay yields typed listings with parsed fields."""
+    output = await scrape_batdongsan(
+        BatdongsanScrapeInput(listing_type="buy", city="HN", max_items=10),
+        fetch_fn=_fixture_fetcher,
+    )
+
+    assert output.degraded is False
+    assert output.total_items == 2
+    assert len(output.items) == 2
+
+    first = output.items[0]
+    assert first.listing_id == 46122640
+    assert first.title == "Bán nhà riêng tại Ba Đình"
+    assert first.price == "19.8 Tỷ"
+    assert first.area == "75 m²"
+    assert first.district == "Ba Đình"
+    assert first.city == "Hà Nội"
+    assert first.post_date == "31/07/2026"
+    assert first.thumbnail_url.startswith("https://file4.batdongsan.com.vn/")
+    assert first.detail_url.startswith("https://batdongsan.com.vn/")
+
+
+@pytest.mark.asyncio
+async def test_recorded_fixture_billing_only_charges_parsed_items(
+    db_session,
+    db_user,
+    db_workspace,
+    monkeypatch,
+):
+    """AC-4: charge only items parsed successfully, at BATDONGSAN_ITEM rate."""
+    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
+    monkeypatch.setattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM", 3500)
+    db_user.credit_micros_balance = 1_000_000
+
+    output = BatdongsanScrapeOutput(
+        items=list((await _fixture_fetcher({}))["data"]),
+        total_items=2,
+    )
+    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
+
+    charged = await charge_capability(output, BillingUnit.BATDONGSAN_ITEM, ctx)
+
+    assert charged == 2 * 3500
+    assert db_user.credit_micros_balance == 1_000_000 - 2 * 3500
+
+    rows = (
+        (
+            await db_session.execute(
+                select(TokenUsage).where(
+                    TokenUsage.workspace_id == db_workspace.id,
+                    TokenUsage.usage_type == "batdongsan_item",
+                )
+            )
+        )
+        .scalars()
+        .all()
+    )
+    assert len(rows) == 1
+    assert rows[0].cost_micros == 2 * 3500
+    assert rows[0].user_id == db_user.id
+
+
+@pytest.mark.skipif(
+    os.getenv("SCRAPE_LIVE") != "1",
+    reason="set SCRAPE_LIVE=1 to hit the real batdongsan.com.vn API",
+)
+@pytest.mark.asyncio
+async def test_live_scrape_against_real_api():
+    """AC-1/AC-5: real API call returns listings or a typed degradation."""
+    output = await scrape_batdongsan(
+        BatdongsanScrapeInput(
+            listing_type="buy",
+            city="HN",
+            max_pages=1,
+            max_items=5,
+        )
+    )
+
+    if output.degraded:
+        assert output.degradation_reason in {
+            "api_error",
+            "rate_limited",
+            "decode_error",
+            "empty",
+            "unknown",
+        }
+    else:
+        assert output.total_items >= 0
+        for item in output.items:
+            assert item.listing_id is not None
+            assert item.title
+            assert item.detail_url
diff --git a/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_billing.py b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_billing.py
new file mode 100644
index 000000000..f7bdf8cfe
--- /dev/null
+++ b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_billing.py
@@ -0,0 +1,20 @@
+"""Unit tests for Batdongsan billing registration."""
+
+from __future__ import annotations
+
+import pytest
+
+from app.capabilities.core.types import BillingUnit
+from app.config import config
+
+pytestmark = pytest.mark.unit
+
+
+def test_billing_unit_includes_batdongsan_item():
+    assert hasattr(BillingUnit, "BATDONGSAN_ITEM")
+    assert BillingUnit.BATDONGSAN_ITEM.value == "batdongsan_item"
+
+
+def test_batdongsan_rate_config_has_default():
+    assert hasattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM")
+    assert config.BATDONGSAN_SCRAPE_MICROS_PER_ITEM == 3500
diff --git a/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_executor.py b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_executor.py
new file mode 100644
index 000000000..e3771c52b
--- /dev/null
+++ b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_executor.py
@@ -0,0 +1,226 @@
+"""Unit tests for the ``batdongsan.scrape`` executor."""
+
+from __future__ import annotations
+
+from collections.abc import Awaitable, Callable
+from typing import Any
+
+import pytest
+
+from app.capabilities.batdongsan.scrape.executor import build_scrape_executor
+from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput
+from app.proprietary.platforms.batdongsan.fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanDecodeError,
+    BatdongsanRateLimitedError,
+)
+from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
+
+pytestmark = pytest.mark.unit
+
+ScrapeFn = Callable[..., Awaitable[dict[str, Any]]]
+
+
+class _FakeScraper:
+    """Records the actor input it was called with; returns canned output."""
+
+    def __init__(self, items: list[dict[str, Any]]):
+        self._items = items
+        self.calls: list[tuple[BatdongsanScrapeInput, int | None]] = []
+
+    async def __call__(
+        self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+    ) -> dict[str, Any]:
+        self.calls.append((actor_input, limit))
+        return {
+            "items": self._items,
+            "total_items": len(self._items),
+            "degraded": False,
+        }
+
+
+@pytest.mark.asyncio
+async def test_maps_input_and_wraps_items():
+    scraper = _FakeScraper([{"listing_id": 1}, {"listing_id": 2}])
+    execute = build_scrape_executor(scrape_fn=scraper)
+
+    out = await execute(
+        ScrapeInput(listing_type="buy", city="SG", district_id=1, max_items=5)
+    )
+
+    assert isinstance(out, ScrapeOutput)
+    assert out.total_items == 2
+    assert len(out.items) == 2
+    assert out.items[0]["listing_id"] == 1
+    assert out.degraded is False
+    assert out.cost_micros == 2 * 3500
+
+    actor_input, limit = scraper.calls[0]
+    assert actor_input.listing_type == "buy"
+    assert actor_input.city == "SG"
+    assert actor_input.district_id == 1
+    assert actor_input.max_items == 5
+    assert limit == 5
+
+
+@pytest.mark.asyncio
+async def test_actor_exception_degrades_without_crashing():
+    async def exploding_scraper(
+        actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+    ) -> dict[str, Any]:
+        raise RuntimeError("boom")
+
+    execute = build_scrape_executor(scrape_fn=exploding_scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert isinstance(out, ScrapeOutput)
+    assert out.total_items == 0
+    assert out.items == []
+    assert out.degraded is True
+    assert out.degradation_reason == "api_error"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_rate_limited_actor_degrades_with_rate_limited_reason():
+    async def limited_scraper(
+        actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+    ) -> dict[str, Any]:
+        raise BatdongsanRateLimitedError("429")
+
+    execute = build_scrape_executor(scrape_fn=limited_scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.degraded is True
+    assert out.degradation_reason == "rate_limited"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_decode_error_actor_degrades_with_decode_error_reason():
+    async def broken_scraper(
+        actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+    ) -> dict[str, Any]:
+        raise BatdongsanDecodeError("bad bytes")
+
+    execute = build_scrape_executor(scrape_fn=broken_scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.degraded is True
+    assert out.degradation_reason == "decode_error"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_blocked_actor_degrades_with_api_error_reason():
+    async def blocked_scraper(
+        actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+    ) -> dict[str, Any]:
+        raise BatdongsanAccessBlockedError("blocked")
+
+    execute = build_scrape_executor(scrape_fn=blocked_scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.degraded is True
+    assert out.degradation_reason == "api_error"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_degraded_run_is_free():
+    class _DegradedScraper(_FakeScraper):
+        async def __call__(
+            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+        ) -> dict[str, Any]:
+            return {
+                "items": self._items,
+                "total_items": len(self._items),
+                "degraded": True,
+                "degradation_reason": "rate_limited",
+            }
+
+    scraper = _DegradedScraper([{"listing_id": 1}])
+    execute = build_scrape_executor(scrape_fn=scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.total_items == 1
+    assert out.degraded is True
+    assert out.degradation_reason == "rate_limited"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_missing_degraded_key_defaults_to_false():
+    class _NoDegradedScraper(_FakeScraper):
+        async def __call__(
+            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+        ) -> dict[str, Any]:
+            return {"items": self._items, "total_items": len(self._items)}
+
+    scraper = _NoDegradedScraper([{"listing_id": 1}])
+    execute = build_scrape_executor(scrape_fn=scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.total_items == 1
+    assert out.degraded is False
+    assert out.cost_micros == 1 * 3500
+
+
+@pytest.mark.asyncio
+async def test_none_result_degrades_with_unknown_reason():
+    class _NoneScraper(_FakeScraper):
+        async def __call__(
+            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+        ) -> dict[str, Any] | None:
+            return None
+
+    execute = build_scrape_executor(scrape_fn=_NoneScraper([]))
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.total_items == 0
+    assert out.degraded is True
+    assert out.degradation_reason == "unknown"
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_dict_without_total_items_counts_zero():
+    class _NoCountScraper(_FakeScraper):
+        async def __call__(
+            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+        ) -> dict[str, Any]:
+            return {"items": self._items}
+
+    scraper = _NoCountScraper([{"listing_id": 1}])
+    execute = build_scrape_executor(scrape_fn=scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.total_items == 1
+    assert out.degraded is False
+    assert out.cost_micros == 0
+
+
+@pytest.mark.asyncio
+async def test_dict_with_none_total_items_counts_zero():
+    class _NoneCountScraper(_FakeScraper):
+        async def __call__(
+            self, actor_input: BatdongsanScrapeInput, *, limit: int | None = None
+        ) -> dict[str, Any]:
+            return {"items": self._items, "total_items": None}
+
+    scraper = _NoneCountScraper([{"listing_id": 1}])
+    execute = build_scrape_executor(scrape_fn=scraper)
+
+    out = await execute(ScrapeInput(city="HN", max_items=5))
+
+    assert out.total_items == 1
+    assert out.degraded is False
+    assert out.cost_micros == 0
diff --git a/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_schemas.py b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_schemas.py
new file mode 100644
index 000000000..eeac33720
--- /dev/null
+++ b/nowing_backend/tests/unit/capabilities/batdongsan/scrape/test_schemas.py
@@ -0,0 +1,128 @@
+"""Unit tests for the ``batdongsan.scrape`` capability schemas."""
+
+from __future__ import annotations
+
+import pytest
+from pydantic import ValidationError
+
+from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput
+
+pytestmark = pytest.mark.unit
+
+
+def test_scrape_input_defaults():
+    inp = ScrapeInput(city="HN")
+    assert inp.listing_type == "buy"
+    assert inp.city == "HN"
+    assert inp.district_id is None
+    assert inp.max_pages == 5
+    assert inp.max_items == 10
+
+
+def test_scrape_input_estimated_units_equals_max_items():
+    assert ScrapeInput(city="HN").estimated_units == 10
+    assert ScrapeInput(city="HN", max_items=3).estimated_units == 3
+
+
+def test_scrape_input_rejects_invalid_listing_type():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", listing_type="sale")
+
+
+def test_scrape_input_rejects_max_pages_above_ceiling():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_pages=100)
+
+
+def test_scrape_input_accepts_max_pages_at_ceiling():
+    assert ScrapeInput(city="HN", max_pages=20).max_pages == 20
+
+
+def test_scrape_input_rejects_max_pages_above_ceiling_by_one():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_pages=21)
+
+
+def test_scrape_input_rejects_max_pages_below_floor():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_pages=0)
+
+
+def test_scrape_input_accepts_max_pages_at_floor():
+    assert ScrapeInput(city="HN", max_pages=1).max_pages == 1
+
+
+def test_scrape_input_rejects_max_items_above_ceiling():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_items=200)
+
+
+def test_scrape_input_accepts_max_items_at_ceiling():
+    assert ScrapeInput(city="HN", max_items=100).max_items == 100
+
+
+def test_scrape_input_rejects_max_items_above_ceiling_by_one():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_items=101)
+
+
+def test_scrape_input_rejects_max_items_below_floor():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", max_items=0)
+
+
+def test_scrape_input_accepts_max_items_at_floor():
+    assert ScrapeInput(city="HN", max_items=1).max_items == 1
+
+
+def test_scrape_input_rejects_min_price_above_max_price():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", min_price=100, max_price=50)
+
+
+def test_scrape_input_accepts_min_price_below_max_price():
+    assert ScrapeInput(city="HN", min_price=100, max_price=200)
+
+
+def test_scrape_input_accepts_equal_price_bounds():
+    assert ScrapeInput(city="HN", min_price=50, max_price=50)
+
+
+def test_scrape_input_accepts_only_min_price():
+    assert ScrapeInput(city="HN", min_price=50).min_price == 50
+
+
+def test_scrape_input_accepts_only_max_price():
+    assert ScrapeInput(city="HN", max_price=50).max_price == 50
+
+
+def test_scrape_input_rejects_min_area_above_max_area():
+    with pytest.raises(ValidationError):
+        ScrapeInput(city="HN", min_area=100, max_area=50)
+
+
+def test_scrape_input_accepts_min_area_below_max_area():
+    assert ScrapeInput(city="HN", min_area=100, max_area=200)
+
+
+def test_scrape_input_accepts_equal_area_bounds():
+    assert ScrapeInput(city="HN", min_area=50, max_area=50)
+
+
+def test_scrape_input_accepts_only_min_area():
+    assert ScrapeInput(city="HN", min_area=50).min_area == 50
+
+
+def test_scrape_input_accepts_only_max_area():
+    assert ScrapeInput(city="HN", max_area=50).max_area == 50
+
+
+def test_scrape_output_has_cost_and_degradation_fields():
+    out = ScrapeOutput(items=[{"id": 1}])
+    assert out.total_items == 1
+    assert out.billable_units == 1
+    assert out.degraded is False
+    assert out.degradation_reason is None
+    assert out.cost_micros == 0
+    assert "cost_micros" in out.model_dump()
+    assert "total_items" in out.model_dump()
diff --git a/nowing_backend/tests/unit/capabilities/batdongsan/test_registry.py b/nowing_backend/tests/unit/capabilities/batdongsan/test_registry.py
new file mode 100644
index 000000000..762205840
--- /dev/null
+++ b/nowing_backend/tests/unit/capabilities/batdongsan/test_registry.py
@@ -0,0 +1,23 @@
+"""The batdongsan namespace registers its verb as one Capability the doors/agent read."""
+
+from __future__ import annotations
+
+import pytest
+
+from app.capabilities import (
+    batdongsan,  # noqa: F401  — importing the namespace registers its verbs
+)
+from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput
+from app.capabilities.core import BillingUnit
+from app.capabilities.core.store import get_capability
+
+pytestmark = pytest.mark.unit
+
+
+def test_batdongsan_scrape_is_registered_and_billable():
+    cap = get_capability("batdongsan.scrape")
+
+    assert cap.name == "batdongsan.scrape"
+    assert cap.input_schema is ScrapeInput
+    assert cap.output_schema is ScrapeOutput
+    assert cap.billing_unit is BillingUnit.BATDONGSAN_ITEM
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/fixtures/sample_p_sync.json b/nowing_backend/tests/unit/platforms/batdongsan/fixtures/sample_p_sync.json
new file mode 100644
index 000000000..6421b7bd4
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/fixtures/sample_p_sync.json
@@ -0,0 +1,33 @@
+{
+  "data": [
+    {
+      "title": "B\u00e1n nh\u00e0 ri\u00eang t\u1ea1i Ba \u0110\u00ecnh",
+      "address": "Ph\u01b0\u1eddng Qu\u00e1n Th\u00e1nh, Qu\u1eadn Ba \u0110\u00ecnh, H\u00e0 N\u1ed9i",
+      "avatar": "https://file4.batdongsan.com.vn/crop/200x200/some.jpg",
+      "price": "19.8 T\u1ef7",
+      "lat": 21.0286146035022,
+      "lon": 105.812719675434,
+      "id": 46122640,
+      "area": "75 m\u00b2",
+      "cat": "B\u00e1n nh\u00e0 ri\u00eang",
+      "date": "31/07/2026",
+      "room": 18,
+      "url": "https://batdongsan.com.vn/nha-dat-ban-ba-dinh/some-pr46122640"
+    },
+    {
+      "title": "Cho thu\u00ea c\u0103n h\u1ed9 Qu\u1eadn 1",
+      "address": "Ph\u01b0\u1eddng B\u1ebfn Ngh\u00e9, Qu\u1eadn 1, H\u1ed3 Ch\u00ed Minh",
+      "avatar": "https://file4.batdongsan.com.vn/crop/200x200/other.jpg",
+      "price": "25 tri\u1ec7u/th\u00e1ng",
+      "lat": 10.772,
+      "lon": 106.698,
+      "id": 46122641,
+      "area": "65 m\u00b2",
+      "cat": "Cho thu\u00ea c\u0103n h\u1ed9",
+      "date": "30/07/2026",
+      "room": 2,
+      "url": "https://batdongsan.com.vn/nha-dat-cho-thue-quan-1/other-pr46122641"
+    }
+  ],
+  "m": "ok"
+}
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/fixtures/web_page.html b/nowing_backend/tests/unit/platforms/batdongsan/fixtures/web_page.html
new file mode 100644
index 000000000..5ae3e7acc
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/fixtures/web_page.html
@@ -0,0 +1,42 @@
+<!DOCTYPE html>
+<html lang="vi"><body>
+<div class="re__search-result">
+<div class="js__card js__card-full-web js__card-listing js__listing-ranking-tooltip pr-container re__card-full" clo="srpg" ipos="1" pgno="1" prav="https://file4.batdongsan.com.vn/crop/200x140/2026/06/28/img1_wm.jpg" prid="45972873" uid="513539">
+<a class="js__product-link-for-product-id" data-product-id="45972873" href="/ban-nha-rieng-duong-thu-khoa-huan-phuong-phu-thuy-1-181/ban-hem-222-20-pr45972873" title="Bán nhà hẻm 222/20 Thủ Khoa Huân">
+<div class="re__card-image"><img alt="Ảnh đại diện" src="https://file4.batdongsan.com.vn/crop/232x186/2026/06/28/img1_wm.jpg"/></div>
+<div class="re__card-info">
+<h3 class="re__card-title"><span class="pr-title js__card-title" product-title="">Bán nhà hẻm 222/20 Thủ Khoa Huân, phường Phú Thủy, DT 102.7m2</span></h3>
+<div class="re__card-config js__card-config">
+<span class="re__card-config-price js__card-config-item">3,4 tỷ</span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span class="re__card-config-area js__card-config-item">102,7 m²</span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span class="re__card-config-price_per_m2 js__card-config-item">33,11 tr/m²</span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span aria-label="2 Phòng ngủ" class="re__card-config-bedroom js__card-config-item" role="tooltip"><span>2</span><i class="re__icon-bedroom--sm"></i></span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span aria-label="1 WC" class="re__card-config-toilet js__card-config-item" role="tooltip"><span>1</span><i class="re__icon-bath--sm"></i></span>
+</div>
+<div class="re__card-location"><span>TP. Phan Thiết (P. Phú Thủy mới)</span></div>
+</div>
+</div>
+</a>
+</div>
+<div class="js__card js__card-full-web js__card-listing pr-container re__card-full" clo="srpg" ipos="2" pgno="1" prav="https://file4.batdongsan.com.vn/crop/200x140/2026/06/28/img2_wm.jpg" prid="45972874" uid="513540">
+<a class="js__product-link-for-product-id" data-product-id="45972874" href="/ban-can-ho-chung-cu-phuong-phu-thuy-pr45972874" title="Bán căn hộ chung cư Phú Thủy">
+<div class="re__card-image"><img alt="Ảnh đại diện" src="https://file4.batdongsan.com.vn/crop/232x186/2026/06/28/img2_wm.jpg"/></div>
+<div class="re__card-info">
+<h3 class="re__card-title"><span class="pr-title js__card-title" product-title="">Bán căn hộ chung cư Phú Thủy, 2 phòng ngủ</span></h3>
+<div class="re__card-config js__card-config">
+<span class="re__card-config-price js__card-config-item">2,1 tỷ</span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span class="re__card-config-area js__card-config-item">89 m²</span>
+<span class="re__card-config-dot js__card-config-item">·</span>
+<span aria-label="3 Phòng ngủ" class="re__card-config-bedroom js__card-config-item" role="tooltip"><span>3</span><i class="re__icon-bedroom--sm"></i></span>
+</div>
+<div class="re__card-location"><span>TP. Phan Thiết (P. Phú Thủy)</span></div>
+</div>
+</div>
+</a>
+</div>
+</div></body></html>
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_decode.py b/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_decode.py
new file mode 100644
index 000000000..5349cb137
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_decode.py
@@ -0,0 +1,183 @@
+"""Offline tests for the Batdongsan ``p_sync`` fetcher and decode pipeline.
+
+No network. Uses a captured fixture plus hand-built edge cases to exercise the
+``gzip → base64 → nibble-swap → Latin-1 JSON`` pipeline.
+"""
+
+from __future__ import annotations
+
+import base64
+import gzip
+import json
+from pathlib import Path
+
+import pytest
+
+from app.proprietary.platforms.batdongsan.fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanDecodeError,
+    BatdongsanRateLimitedError,
+    decode_response,
+    fetch_listings,
+)
+
+pytestmark = pytest.mark.unit
+
+_FIXTURE_DIR = Path(__file__).parent / "fixtures"
+
+
+def _load_sample() -> dict:
+    return json.loads((_FIXTURE_DIR / "sample_p_sync.json").read_text(encoding="utf-8"))
+
+
+def _nibble_swap(data: bytes) -> bytes:
+    return bytes(((b & 0x0F) << 4) | (b >> 4) for b in data)
+
+
+def _encode_fixture(decoded: dict) -> bytes:
+    """Reverse the decoder pipeline to produce the raw response bytes."""
+    json_bytes = json.dumps(decoded, ensure_ascii=True).encode("latin-1")
+    swapped = _nibble_swap(json_bytes)
+    b64_bytes = base64.b64encode(swapped)
+    return gzip.compress(b64_bytes)
+
+
+def test_nibble_swap_is_self_inverse():
+    assert _nibble_swap(_nibble_swap(b"hello")) == b"hello"
+
+
+def test_decode_response_extracts_data_and_meta():
+    decoded = _load_sample()
+    raw = _encode_fixture(decoded)
+
+    result = decode_response(raw)
+
+    assert result == decoded
+
+
+def test_decode_response_handles_plain_base64_without_gzip():
+    decoded = _load_sample()
+    json_bytes = json.dumps(decoded, ensure_ascii=True).encode("latin-1")
+    raw = base64.b64encode(_nibble_swap(json_bytes))
+
+    result = decode_response(raw)
+
+    assert result == decoded
+
+
+def test_decode_response_returns_empty_for_empty_data():
+    raw = _encode_fixture({"data": [], "m": None})
+
+    result = decode_response(raw)
+
+    assert result["data"] == []
+
+
+def test_decode_response_raises_decode_error_for_invalid_bytes():
+    with pytest.raises(ValueError):
+        decode_response(b"not-valid-data")
+
+
+def test_decode_response_raises_decode_error_for_gzip_bomb(mocker):
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch._MAX_DECODED_BYTES", 1024)
+    bomb = gzip.compress(b"\x00" * 8192)
+    with pytest.raises(BatdongsanDecodeError, match="size cap"):
+        decode_response(bomb)
+
+
+@pytest.mark.asyncio
+async def test_fetch_listings_returns_data(mocker):
+    decoded = _load_sample()
+    raw = _encode_fixture(decoded)
+
+    mock_page = mocker.MagicMock()
+    mock_page.status = 200
+    mock_page.body = raw
+    mock_post = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_post.return_value = mock_page
+
+    payload = {"ptype": 38, "city": "HN", "page": 1}
+    result = await fetch_listings(payload)
+
+    assert isinstance(result, dict)
+    assert "data" in result
+    assert len(result["data"]) == 2
+    mock_post.assert_awaited_once()
+
+
+@pytest.mark.asyncio
+async def test_fetch_listings_raises_decode_error_without_retrying(mocker):
+    mock_page = mocker.MagicMock()
+    mock_page.status = 200
+    mock_page.body = b"not-valid-data"
+    mock_post = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_post.return_value = mock_page
+
+    with pytest.raises(BatdongsanDecodeError):
+        await fetch_listings({"ptype": 38, "city": "HN"})
+
+    mock_post.assert_awaited_once()
+
+
+@pytest.mark.asyncio
+async def test_fetch_listings_404_raises_blocked(mocker):
+    mock_page = mocker.MagicMock()
+    mock_page.status = 404
+    mock_page.body = b""
+    mock_post = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_post.return_value = mock_page
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+    with pytest.raises(BatdongsanAccessBlockedError):
+        await fetch_listings({"ptype": 38, "city": "HN"})
+
+
+@pytest.mark.asyncio
+async def test_fetch_listings_429_raises_rate_limited(mocker):
+    mock_page = mocker.MagicMock()
+    mock_page.status = 429
+    mock_page.body = b""
+    mock_post = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_post.return_value = mock_page
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+    with pytest.raises(BatdongsanRateLimitedError):
+        await fetch_listings({"ptype": 38, "city": "HN"})
+
+
+@pytest.mark.asyncio
+async def test_fetch_listings_rotates_on_403_then_succeeds(mocker):
+    decoded = _load_sample()
+    raw = _encode_fixture(decoded)
+
+    blocked_page = mocker.MagicMock()
+    blocked_page.status = 403
+    blocked_page.body = b""
+
+    ok_page = mocker.MagicMock()
+    ok_page.status = 200
+    ok_page.body = raw
+
+    mock_post = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.post",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_post.side_effect = [blocked_page, ok_page]
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+    result = await fetch_listings({"ptype": 38, "city": "HN"})
+
+    assert isinstance(result, dict)
+    assert mock_post.await_count == 2
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_web.py b/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_web.py
new file mode 100644
index 000000000..ad019459f
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/test_fetch_web.py
@@ -0,0 +1,129 @@
+"""Offline tests for the Batdongsan web SSR fetcher."""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from app.proprietary.platforms.batdongsan.fetch import (
+    CITY_SLUGS,
+    BatdongsanAccessBlockedError,
+    build_web_listings_url,
+    fetch_web_listings,
+)
+
+pytestmark = pytest.mark.unit
+
+
+@pytest.fixture(autouse=True)
+def _no_sleep(mocker):
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+
+_FIXTURE_DIR = Path(__file__).parent / "fixtures"
+
+
+def test_city_slugs_contains_known_codes():
+    assert CITY_SLUGS["HN"] == "ha-noi"
+    assert CITY_SLUGS["SG"] == "tp-hcm"
+    assert CITY_SLUGS["BTH"] == "binh-thuan"
+    assert CITY_SLUGS["TTH"] == "hue"
+
+
+def test_build_web_listings_url_buy():
+    assert (
+        build_web_listings_url("buy", "binh-thuan", 1)
+        == "https://batdongsan.com.vn/ban-nha-dat-binh-thuan"
+    )
+    assert (
+        build_web_listings_url("buy", "binh-thuan", 3)
+        == "https://batdongsan.com.vn/ban-nha-dat-binh-thuan/p3"
+    )
+
+
+def test_build_web_listings_url_rent():
+    assert (
+        build_web_listings_url("rent", "ha-noi", 1)
+        == "https://batdongsan.com.vn/nha-dat-cho-thue-ha-noi"
+    )
+
+
+@pytest.mark.asyncio
+async def test_fetch_web_listings_returns_data(mocker):
+    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
+    mock_page = mocker.MagicMock()
+    mock_page.status = 200
+    mock_page.body = html
+    mock_get = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_get.return_value = mock_page
+
+    result = await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})
+
+    assert isinstance(result, dict)
+    assert len(result["data"]) == 2
+    assert result["data"][0]["id"] == 45972873
+    assert (
+        result["data"][0]["title"]
+        == "Bán nhà hẻm 222/20 Thủ Khoa Huân, phường Phú Thủy, DT 102.7m2"
+    )
+    assert result["data"][0]["price"] == "3,4 tỷ"
+    assert result["data"][0]["area"] == "102,7 m²"
+    assert result["data"][0]["address"] == "TP. Phan Thiết (P. Phú Thủy mới)"
+    assert result["data"][0]["room"] == 2
+    assert result["m"] is None  # < 20 items → no more
+
+
+@pytest.mark.asyncio
+async def test_fetch_web_listings_unknown_city_returns_empty(mocker):
+    mock_get = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
+        new_callable=mocker.AsyncMock,
+    )
+
+    result = await fetch_web_listings({"ptype": 38, "city": "ZZZ", "page": 1})
+
+    assert result == {"data": [], "m": None}
+    mock_get.assert_not_awaited()
+
+
+@pytest.mark.asyncio
+async def test_fetch_web_listings_403_raises_blocked(mocker):
+    mock_page = mocker.MagicMock()
+    mock_page.status = 403
+    mock_page.body = b""
+    mock_get = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_page.status = 403
+    mock_get.return_value = mock_page
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+    with pytest.raises(BatdongsanAccessBlockedError):
+        await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})
+
+
+@pytest.mark.asyncio
+async def test_fetch_web_listings_rotates_on_403_then_succeeds(mocker):
+    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
+    blocked = mocker.MagicMock()
+    blocked.status = 403
+    blocked.body = b""
+    ok = mocker.MagicMock()
+    ok.status = 200
+    ok.body = html
+    mock_get = mocker.patch(
+        "app.proprietary.platforms.batdongsan.fetch.AsyncFetcher.get",
+        new_callable=mocker.AsyncMock,
+    )
+    mock_get.side_effect = [blocked, ok]
+    mocker.patch("app.proprietary.platforms.batdongsan.fetch.asyncio.sleep")
+
+    result = await fetch_web_listings({"ptype": 38, "city": "BTH", "page": 1})
+
+    assert len(result["data"]) == 2
+    assert mock_get.await_count == 2
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/test_parsers.py b/nowing_backend/tests/unit/platforms/batdongsan/test_parsers.py
new file mode 100644
index 000000000..1fdbccb88
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/test_parsers.py
@@ -0,0 +1,152 @@
+"""Offline parser tests for the Batdongsan scraper.
+
+No network. Uses a captured fixture plus synthetic edge cases to exercise the
+raw ``p_sync`` data → ``BatdongsanListing`` mapping.
+"""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+
+from app.proprietary.platforms.batdongsan.parsers import parse_listing, parse_listings
+from app.proprietary.platforms.batdongsan.schemas import BatdongsanListing
+
+pytestmark = pytest.mark.unit
+
+_FIXTURE_DIR = Path(__file__).parent / "fixtures"
+
+
+def _load_sample() -> list[dict]:
+    decoded = json.loads(
+        (_FIXTURE_DIR / "sample_p_sync.json").read_text(encoding="utf-8")
+    )
+    return decoded["data"]
+
+
+def test_parse_listings_maps_all_fields():
+    raw_items = _load_sample()
+
+    listings = parse_listings(raw_items)
+
+    assert len(listings) == 2
+    first = listings[0]
+    assert isinstance(first, BatdongsanListing)
+    assert first.listing_id == 46122640
+    assert first.title == "Bán nhà riêng tại Ba Đình"
+    assert first.price == "19.8 Tỷ"
+    assert first.price_raw == "19.8 Tỷ"
+    assert first.area == "75 m²"
+    assert first.area_raw == "75 m²"
+    assert first.location == "Phường Quán Thánh, Quận Ba Đình, Hà Nội"
+    assert first.city == "Hà Nội"
+    assert first.district == "Ba Đình"
+    assert first.post_date == "31/07/2026"
+    assert (
+        first.thumbnail_url == "https://file4.batdongsan.com.vn/crop/200x200/some.jpg"
+    )
+    assert (
+        first.detail_url
+        == "https://batdongsan.com.vn/nha-dat-ban-ba-dinh/some-pr46122640"
+    )
+    assert first.latitude == 21.0286146035022
+    assert first.longitude == 105.812719675434
+    assert first.rooms == 18
+
+
+def test_parse_listing_returns_none_fields_for_missing_optional():
+    raw = {
+        "id": 999,
+        "title": "Sample",
+        "price": "Thỏa thuận",
+        "area": None,
+        "avatar": None,
+    }
+
+    listing = parse_listing(raw)
+
+    assert listing.listing_id == 999
+    assert listing.price_raw == "Thỏa thuận"
+    assert listing.price is None
+    assert listing.area is None
+    assert listing.area_raw is None
+    assert listing.thumbnail_url is None
+
+
+def test_parse_listings_returns_empty_for_empty_input():
+    assert parse_listings([]) == []
+
+
+def test_parse_listings_parses_rent_listing():
+    raw_items = _load_sample()
+    rent = raw_items[1]
+
+    listings = parse_listings([rent])
+
+    assert len(listings) == 1
+    assert listings[0].listing_id == 46122641
+    assert listings[0].title == "Cho thuê căn hộ Quận 1"
+
+
+def test_parse_listing_keeps_area_range_token():
+    listing = parse_listing({"id": 1, "area": "72-75 m²"})
+
+    assert listing.area == "72-75 m²"
+    assert listing.area_raw == "72-75 m²"
+
+
+def test_parse_web_listings_extracts_cards():
+    from app.proprietary.platforms.batdongsan.parsers import parse_web_listings
+
+    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
+    items = parse_web_listings(html)
+
+    assert len(items) == 2
+    first = items[0]
+    assert first["id"] == 45972873
+    assert (
+        first["title"]
+        == "Bán nhà hẻm 222/20 Thủ Khoa Huân, phường Phú Thủy, DT 102.7m2"
+    )
+    assert first["price"] == "3,4 tỷ"
+    assert first["area"] == "102,7 m²"
+    assert first["address"] == "TP. Phan Thiết (P. Phú Thủy mới)"
+    assert (
+        first["avatar"]
+        == "https://file4.batdongsan.com.vn/crop/200x140/2026/06/28/img1_wm.jpg"
+    )
+    assert (
+        first["url"]
+        == "https://batdongsan.com.vn/ban-nha-rieng-duong-thu-khoa-huan-phuong-phu-thuy-1-181/ban-hem-222-20-pr45972873"
+    )
+    assert first["room"] == 2
+
+    second = items[1]
+    assert second["id"] == 45972874
+    assert second["room"] == 3
+
+
+def test_parse_web_listings_empty_html():
+    from app.proprietary.platforms.batdongsan.parsers import parse_web_listings
+
+    assert parse_web_listings("<html><body></body></html>") == []
+
+
+def test_parse_web_listings_feeds_into_parse_listing():
+    from app.proprietary.platforms.batdongsan.parsers import (
+        parse_listing,
+        parse_web_listings,
+    )
+
+    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
+    items = parse_web_listings(html)
+    listing = parse_listing(items[0])
+
+    assert listing.listing_id == 45972873
+    assert listing.price == "3,4 tỷ"
+    assert listing.area == "102,7 m²"
+    assert listing.rooms == 2
+    assert listing.thumbnail_url is not None
+    assert listing.detail_url is not None
diff --git a/nowing_backend/tests/unit/platforms/batdongsan/test_scraper.py b/nowing_backend/tests/unit/platforms/batdongsan/test_scraper.py
new file mode 100644
index 000000000..d34595a84
--- /dev/null
+++ b/nowing_backend/tests/unit/platforms/batdongsan/test_scraper.py
@@ -0,0 +1,370 @@
+"""Offline orchestrator tests for the Batdongsan scraper.
+
+The network boundary (``fetch_listings``) is injected as a fake. Tests cover
+pagination, caps, and degradation.
+"""
+
+from __future__ import annotations
+
+from typing import Any
+
+import pytest
+
+from app.proprietary.platforms.batdongsan.fetch import (
+    BatdongsanAccessBlockedError,
+    BatdongsanDecodeError,
+    BatdongsanRateLimitedError,
+)
+from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
+from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan
+
+pytestmark = pytest.mark.unit
+
+_MODULE = "app.proprietary.platforms.batdongsan.scraper"
+
+
+@pytest.fixture(autouse=True)
+def _no_page_delay(mocker):
+    """Keep pacing sleeps out of offline tests."""
+    mocker.patch(f"{_MODULE}.asyncio.sleep")
+
+
+def _listing(id_: int, title: str = "Listing") -> dict[str, Any]:
+    return {
+        "id": id_,
+        "title": title,
+        "address": "Hà Nội",
+        "price": "1 Tỷ",
+        "area": "50 m²",
+        "date": "01/08/2026",
+        "url": f"https://batdongsan.com.vn/p/{id_}.htm",
+    }
+
+
+class _FakeFetcher:
+    """Records page payloads and returns canned ``p_sync`` envelopes."""
+
+    def __init__(self, pages: list[list[dict[str, Any]]]):
+        self.pages = pages
+        self.calls: list[dict[str, Any]] = []
+
+    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
+        self.calls.append(payload)
+        page = payload.get("page", 1)
+        if page > len(self.pages):
+            return {"data": [], "m": None}
+        return {"data": self.pages[page - 1], "m": "ok"}
+
+
+@pytest.mark.asyncio
+async def test_scraper_paginates_until_max_items():
+    pages = [[_listing(i) for i in range(1, 6)], [_listing(i) for i in range(6, 11)]]
+    fetcher = _FakeFetcher(pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=7,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)
+
+    assert output.total_items == 7
+    assert len(output.items) == 7
+    assert [item.listing_id for item in output.items] == list(range(1, 8))
+    assert output.degraded is False
+    assert len(fetcher.calls) == 2
+
+
+@pytest.mark.asyncio
+async def test_scraper_stops_on_empty_page():
+    pages = [[_listing(1), _listing(2)], []]
+    fetcher = _FakeFetcher(pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=100,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)
+
+    assert output.total_items == 2
+    assert len(output.items) == 2
+    assert output.degraded is False
+
+
+@pytest.mark.asyncio
+async def test_scraper_empty_first_page_degrades_with_empty_reason():
+    pages = [[]]
+    fetcher = _FakeFetcher(pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=100,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)
+
+    assert output.total_items == 0
+    assert output.degraded is True
+    assert output.degradation_reason == "empty"
+
+
+@pytest.mark.asyncio
+async def test_scraper_dedupes_listings_across_pages():
+    pages = [
+        [_listing(1), _listing(2)],
+        [_listing(2), _listing(3)],
+        [_listing(4)],
+    ]
+    fetcher = _FakeFetcher(pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=100,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)
+
+    assert output.total_items == 4
+    assert [item.listing_id for item in output.items] == [1, 2, 3, 4]
+
+
+@pytest.mark.asyncio
+async def test_scraper_decode_error_degrades_with_decode_error():
+    async def broken_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
+        raise BatdongsanDecodeError("bad wire bytes")
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=10,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=broken_fetcher)
+
+    assert output.degraded is True
+    assert output.degradation_reason == "decode_error"
+    assert output.total_items == 0
+
+
+@pytest.mark.asyncio
+async def test_scraper_non_list_data_degrades_with_api_error():
+    async def weird_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
+        return {"data": {"unexpected": True}, "m": "ok"}
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=10,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=weird_fetcher)
+
+    assert output.degraded is True
+    assert output.degradation_reason == "api_error"
+    assert output.total_items == 0
+
+
+@pytest.mark.asyncio
+async def test_scraper_honors_max_pages():
+    pages = [
+        [_listing(1), _listing(2)],
+        [_listing(3), _listing(4)],
+        [_listing(5), _listing(6)],
+    ]
+    fetcher = _FakeFetcher(pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=1,
+        max_items=100,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=fetcher)
+
+    assert output.total_items == 2
+    assert len(output.items) == 2
+    assert len(fetcher.calls) == 1
+
+
+@pytest.mark.asyncio
+async def test_scraper_returns_degraded_on_api_error():
+    async def failing_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
+        raise BatdongsanAccessBlockedError("blocked")
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=10,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=failing_fetcher)
+
+    assert output.degraded is True
+    assert output.degradation_reason == "api_error"
+    assert output.total_items == 0
+    assert output.items == []
+
+
+@pytest.mark.asyncio
+async def test_scraper_rate_limited_degrades_after_retry():
+    calls = 0
+
+    async def flaky_fetcher(_payload: dict[str, Any]) -> dict[str, Any]:
+        nonlocal calls
+        calls += 1
+        if calls < 3:
+            raise BatdongsanRateLimitedError("429")
+        return {"data": [_listing(1)], "m": "ok"}
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="HN",
+        max_pages=10,
+        max_items=10,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=flaky_fetcher)
+
+    assert output.degraded is True
+    assert output.degradation_reason == "rate_limited"
+
+
+class _FakeWebFetcher:
+    """Returns canned web envelopes; records calls."""
+
+    def __init__(self, pages: list[list[dict[str, Any]]]):
+        self.pages = pages
+        self.calls: list[dict[str, Any]] = []
+
+    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
+        self.calls.append(payload)
+        page = payload.get("page", 1)
+        if page > len(self.pages):
+            return {"data": [], "m": None}
+        data = self.pages[page - 1]
+        return {"data": data, "m": "ok" if len(data) >= 20 else None}
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_engages_when_mobile_empty_city_level():
+    mobile = _FakeFetcher([[]])
+    web = _FakeWebFetcher([[_listing(101), _listing(102)]])
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="BTH", max_pages=5, max_items=10
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.total_items == 2
+    assert output.degraded is False
+    assert [item.listing_id for item in output.items] == [101, 102]
+    assert len(mobile.calls) == 1  # only page 1 mobile
+    assert len(web.calls) == 1
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_skipped_when_district_filter_present():
+    mobile = _FakeFetcher([[]])
+    web = _FakeWebFetcher([[_listing(101)]])
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="BTH", district_id=5, max_pages=5, max_items=10
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.total_items == 0
+    assert output.degraded is True
+    assert output.degradation_reason == "empty"
+    assert len(web.calls) == 0  # web never called
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_skipped_when_price_bound_present():
+    mobile = _FakeFetcher([[]])
+    web = _FakeWebFetcher([[_listing(101)]])
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy",
+        city="BTH",
+        max_price=5_000_000_000,
+        max_pages=5,
+        max_items=10,
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.degraded is True
+    assert output.degradation_reason == "empty"
+    assert len(web.calls) == 0
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_both_empty_degrades_empty():
+    mobile = _FakeFetcher([[]])
+    web = _FakeWebFetcher([[]])
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="BTH", max_pages=5, max_items=10
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.total_items == 0
+    assert output.degraded is True
+    assert output.degradation_reason == "empty"
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_paginates_with_web_fetcher():
+    mobile = _FakeFetcher([[]])
+    web_pages = [
+        [_listing(i) for i in range(1, 21)],  # 20 items → m=ok
+        [_listing(21), _listing(22)],  # 2 items → m=None
+    ]
+    web = _FakeWebFetcher(web_pages)
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="BTH", max_pages=5, max_items=25
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.total_items == 22
+    assert output.degraded is False
+    assert len(mobile.calls) == 1  # only page 1
+    assert len(web.calls) == 2  # pages 1 + 2
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_not_used_when_mobile_has_data():
+    mobile = _FakeFetcher([[_listing(1), _listing(2)]])
+    web = _FakeWebFetcher([[_listing(999)]])
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="HN", max_pages=5, max_items=10
+    )
+    output = await scrape_batdongsan(input_model, fetch_fn=mobile, web_fetch_fn=web)
+
+    assert output.total_items == 2
+    assert [item.listing_id for item in output.items] == [1, 2]
+    assert len(web.calls) == 0
+
+
+@pytest.mark.asyncio
+async def test_web_fallback_blocked_degrades_empty():
+    mobile = _FakeFetcher([[]])
+
+    async def blocked_web(_payload: dict[str, Any]) -> dict[str, Any]:
+        raise BatdongsanAccessBlockedError("403")
+
+    input_model = BatdongsanScrapeInput(
+        listing_type="buy", city="BTH", max_pages=5, max_items=10
+    )
+    output = await scrape_batdongsan(
+        input_model, fetch_fn=mobile, web_fetch_fn=blocked_web
+    )
+
+    assert output.total_items == 0
+    assert output.degraded is True
+    assert output.degradation_reason == "empty"
diff --git a/nowing_web/app/admin/scraper-accounts/page.tsx b/nowing_web/app/admin/scraper-accounts/page.tsx
new file mode 100644
index 000000000..4fbdd2e18
--- /dev/null
+++ b/nowing_web/app/admin/scraper-accounts/page.tsx
@@ -0,0 +1,419 @@
+"use client";
+
+import { useAtom } from "jotai";
+import { useEffect, useMemo, useState } from "react";
+import { toast } from "sonner";
+import { currentUserAtom } from "@/atoms/user/user-query.atoms";
+import { Button } from "@/components/ui/button";
+import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
+import {
+	Dialog,
+	DialogContent,
+	DialogDescription,
+	DialogFooter,
+	DialogHeader,
+	DialogTitle,
+} from "@/components/ui/dialog";
+import { Input } from "@/components/ui/input";
+import { Label } from "@/components/ui/label";
+import {
+	Select,
+	SelectContent,
+	SelectItem,
+	SelectTrigger,
+	SelectValue,
+} from "@/components/ui/select";
+import { Spinner } from "@/components/ui/spinner";
+import { Switch } from "@/components/ui/switch";
+import type {
+	ScraperPlatformAccount,
+	ScraperPlatformAccountCredentials,
+} from "@/lib/apis/scraper-platform-accounts-api.service";
+import { scraperPlatformAccountsApiService } from "@/lib/apis/scraper-platform-accounts-api.service";
+
+const PLATFORM_OPTIONS = [
+	{ value: "muaban_bds", label: "Muaban BĐS" },
+	{ value: "batdongsan", label: "Batdongsan.com.vn" },
+	{ value: "chotot_bds", label: "Chotot BĐS" },
+];
+
+interface AccountForm {
+	platform: string;
+	label: string;
+	is_enabled: boolean;
+	is_default: boolean;
+	cookies: string;
+	token: string;
+}
+
+const emptyForm: AccountForm = {
+	platform: "",
+	label: "",
+	is_enabled: true,
+	is_default: false,
+	cookies: "",
+	token: "",
+};
+
+function toForm(account: ScraperPlatformAccount): AccountForm {
+	const creds = account.credentials ?? {};
+	return {
+		platform: account.platform,
+		label: account.label ?? "",
+		is_enabled: account.is_enabled,
+		is_default: account.is_default,
+		cookies: creds.cookies ?? "",
+		token: creds.token ?? "",
+	};
+}
+
+function fromForm(form: AccountForm): {
+	platform: string;
+	label: string | null;
+	is_enabled: boolean;
+	is_default: boolean;
+	credentials: ScraperPlatformAccountCredentials | null;
+} {
+	return {
+		platform: form.platform,
+		label: form.label.trim() || null,
+		is_enabled: form.is_enabled,
+		is_default: form.is_default,
+		credentials:
+			form.cookies.trim() || form.token.trim()
+				? {
+						cookies: form.cookies.trim() || null,
+						token: form.token.trim() || null,
+					}
+				: null,
+	};
+}
+
+export default function ScraperAccountsAdminPage() {
+	const [{ data: user, isLoading: userLoading }] = useAtom(currentUserAtom);
+	const [accounts, setAccounts] = useState<ScraperPlatformAccount[]>([]);
+	const [listLoading, setListLoading] = useState(true);
+	const [createOpen, setCreateOpen] = useState(false);
+	const [draft, setDraft] = useState<AccountForm>(emptyForm);
+	const [editDialog, setEditDialog] = useState<{
+		open: boolean;
+		account: ScraperPlatformAccount | null;
+		draft: AccountForm;
+	}>({ open: false, account: null, draft: emptyForm });
+	const [deleteDialog, setDeleteDialog] = useState<ScraperPlatformAccount | null>(null);
+
+	const isSuperuser = user?.is_superuser ?? false;
+
+	const load = async () => {
+		setListLoading(true);
+		try {
+			const data = await scraperPlatformAccountsApiService.list();
+			setAccounts(data);
+		} catch {
+			toast.error("Failed to load scraper accounts");
+		} finally {
+			setListLoading(false);
+		}
+	};
+
+	useEffect(() => {
+		if (isSuperuser) {
+			void load();
+		}
+	}, [isSuperuser]);
+
+	useEffect(() => {
+		if (!createOpen) {
+			setDraft(emptyForm);
+		}
+	}, [createOpen]);
+
+	const isCreateValid = useMemo(() => draft.platform.trim().length > 0, [draft.platform]);
+
+	async function handleCreate() {
+		if (!isCreateValid) return;
+		try {
+			await scraperPlatformAccountsApiService.create(fromForm(draft));
+			setCreateOpen(false);
+			toast.success("Account created");
+			await load();
+		} catch {
+			toast.error("Failed to create account");
+		}
+	}
+
+	async function handleUpdate() {
+		if (!editDialog.account) return;
+		try {
+			await scraperPlatformAccountsApiService.update(
+				editDialog.account.id,
+				fromForm(editDialog.draft)
+			);
+			setEditDialog({ open: false, account: null, draft: emptyForm });
+			toast.success("Account updated");
+			await load();
+		} catch {
+			toast.error("Failed to update account");
+		}
+	}
+
+	async function handleDelete() {
+		if (!deleteDialog) return;
+		try {
+			await scraperPlatformAccountsApiService.delete(deleteDialog.id);
+			toast.success("Account deleted");
+			await load();
+		} catch {
+			toast.error("Failed to delete account");
+		} finally {
+			setDeleteDialog(null);
+		}
+	}
+
+	async function handleToggleEnabled(account: ScraperPlatformAccount) {
+		try {
+			await scraperPlatformAccountsApiService.update(account.id, {
+				is_enabled: !account.is_enabled,
+			});
+			toast.success("Account updated");
+			await load();
+		} catch {
+			toast.error("Failed to update account");
+		}
+	}
+
+	function openEdit(account: ScraperPlatformAccount) {
+		setEditDialog({ open: true, account, draft: toForm(account) });
+	}
+
+	if (userLoading) {
+		return (
+			<div className="flex h-full items-center justify-center">
+				<Spinner size="lg" />
+			</div>
+		);
+	}
+
+	if (!isSuperuser) {
+		return (
+			<div className="flex h-full flex-col items-center justify-center gap-4 p-6">
+				<h1 className="text-2xl font-semibold">Access denied</h1>
+				<p className="text-muted-foreground">You must be a superuser to view this page.</p>
+			</div>
+		);
+	}
+
+	return (
+		<div className="container mx-auto max-w-5xl p-6">
+			<div className="mb-6 flex items-center justify-between">
+				<div>
+					<h1 className="text-2xl font-semibold">Scraper platform accounts</h1>
+					<p className="text-sm text-muted-foreground">
+						Manage cookies, tokens and API credentials for scraper platforms.
+					</p>
+				</div>
+				<Button onClick={() => setCreateOpen(true)}>Add account</Button>
+			</div>
+
+			{listLoading ? (
+				<div className="flex h-64 items-center justify-center">
+					<Spinner size="lg" />
+				</div>
+			) : accounts.length === 0 ? (
+				<Card>
+					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
+						No scraper platform accounts found.
+					</CardContent>
+				</Card>
+			) : (
+				<div className="space-y-4">
+					{accounts.map((account) => (
+						<Card key={account.id}>
+							<CardHeader className="pb-3">
+								<div className="flex items-start justify-between gap-4">
+									<div>
+										<CardTitle>
+											{account.label || account.platform}
+											{account.is_default && (
+												<span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
+													Default
+												</span>
+											)}
+										</CardTitle>
+										<CardDescription>{account.platform}</CardDescription>
+									</div>
+									<div className="flex items-center gap-2">
+										<span className="text-sm text-muted-foreground">
+											{account.is_enabled ? "Enabled" : "Disabled"}
+										</span>
+										<Switch
+											checked={account.is_enabled}
+											onCheckedChange={() => handleToggleEnabled(account)}
+										/>
+										<Button variant="outline" size="sm" onClick={() => openEdit(account)}>
+											Edit
+										</Button>
+										<Button variant="outline" size="sm" onClick={() => setDeleteDialog(account)}>
+											Delete
+										</Button>
+									</div>
+								</div>
+							</CardHeader>
+							<CardContent className="space-y-2 text-sm">
+								<p className="text-muted-foreground">
+									Created: {new Date(account.created_at).toLocaleString()}
+								</p>
+							</CardContent>
+						</Card>
+					))}
+				</div>
+			)}
+
+			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
+				<DialogContent className="max-w-xl">
+					<DialogHeader>
+						<DialogTitle>Add scraper account</DialogTitle>
+						<DialogDescription>
+							Paste the browser cookie string or token the scraper should use.
+						</DialogDescription>
+					</DialogHeader>
+					<AccountFormFields form={draft} setForm={(next) => setDraft(next(draft))} />
+					<DialogFooter>
+						<Button variant="outline" onClick={() => setCreateOpen(false)}>
+							Cancel
+						</Button>
+						<Button onClick={handleCreate} disabled={!isCreateValid}>
+							Save
+						</Button>
+					</DialogFooter>
+				</DialogContent>
+			</Dialog>
+
+			<Dialog
+				open={editDialog.open}
+				onOpenChange={(open) => {
+					if (!open) setEditDialog({ open: false, account: null, draft: emptyForm });
+				}}
+			>
+				<DialogContent className="max-w-xl">
+					<DialogHeader>
+						<DialogTitle>Edit scraper account</DialogTitle>
+						<DialogDescription>Update credentials for this platform.</DialogDescription>
+					</DialogHeader>
+					<AccountFormFields
+						form={editDialog.draft}
+						setForm={(next) => setEditDialog((prev) => ({ ...prev, draft: next(prev.draft) }))}
+					/>
+					<DialogFooter>
+						<Button
+							variant="outline"
+							onClick={() => setEditDialog({ open: false, account: null, draft: emptyForm })}
+						>
+							Cancel
+						</Button>
+						<Button onClick={handleUpdate}>Save</Button>
+					</DialogFooter>
+				</DialogContent>
+			</Dialog>
+
+			<Dialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
+				<DialogContent className="max-w-md">
+					<DialogHeader>
+						<DialogTitle>Delete account</DialogTitle>
+						<DialogDescription>
+							Are you sure you want to delete this account? This action cannot be undone.
+						</DialogDescription>
+					</DialogHeader>
+					<DialogFooter>
+						<Button variant="outline" onClick={() => setDeleteDialog(null)}>
+							Cancel
+						</Button>
+						<Button variant="destructive" onClick={handleDelete}>
+							Delete
+						</Button>
+					</DialogFooter>
+				</DialogContent>
+			</Dialog>
+		</div>
+	);
+}
+
+function AccountFormFields({
+	form,
+	setForm,
+}: {
+	form: AccountForm;
+	setForm: (fn: (prev: AccountForm) => AccountForm) => void;
+}) {
+	function update<K extends keyof AccountForm>(key: K, value: AccountForm[K]) {
+		setForm((prev) => ({ ...prev, [key]: value }));
+	}
+
+	return (
+		<div className="space-y-4 py-4">
+			<div className="space-y-2">
+				<Label>Platform</Label>
+				<Select value={form.platform} onValueChange={(v) => update("platform", v)}>
+					<SelectTrigger>
+						<SelectValue placeholder="Select a platform" />
+					</SelectTrigger>
+					<SelectContent>
+						{PLATFORM_OPTIONS.map((opt) => (
+							<SelectItem key={opt.value} value={opt.value}>
+								{opt.label}
+							</SelectItem>
+						))}
+					</SelectContent>
+				</Select>
+			</div>
+
+			<div className="space-y-2">
+				<Label>Label</Label>
+				<Input
+					value={form.label}
+					onChange={(e) => update("label", e.target.value)}
+					placeholder="e.g. Production muaban account"
+				/>
+			</div>
+
+			<div className="flex items-center gap-6">
+				<div className="flex items-center gap-2">
+					<Switch
+						checked={form.is_enabled}
+						onCheckedChange={(v) => update("is_enabled", v)}
+						id="edit-enabled"
+					/>
+					<Label htmlFor="edit-enabled">Enabled</Label>
+				</div>
+				<div className="flex items-center gap-2">
+					<Switch
+						checked={form.is_default}
+						onCheckedChange={(v) => update("is_default", v)}
+						id="edit-default"
+					/>
+					<Label htmlFor="edit-default">Default</Label>
+				</div>
+			</div>
+
+			<div className="space-y-2">
+				<Label>Browser cookie string</Label>
+				<textarea
+					value={form.cookies}
+					onChange={(e) => update("cookies", e.target.value)}
+					placeholder="Paste document.cookie here"
+					className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
+				/>
+			</div>
+
+			<div className="space-y-2">
+				<Label>Token</Label>
+				<Input
+					type="password"
+					value={form.token}
+					onChange={(e) => update("token", e.target.value)}
+					placeholder="API token if the platform supports one"
+				/>
+			</div>
+		</div>
+	);
+}
diff --git a/nowing_backend/scripts/capture_batdongsan_session.py b/nowing_backend/scripts/capture_batdongsan_session.py
new file mode 100644
index 000000000..e5fc3de72
--- /dev/null
+++ b/nowing_backend/scripts/capture_batdongsan_session.py
@@ -0,0 +1,245 @@
+"""Capture a fresh Batdongsan.com.vn browser session and save it to the DB.
+
+This is meant for self-host admins who log in with Google OAuth and cannot
+share a password. It opens a headed Chromium window on the Batdongsan login
+page, waits for the admin to complete OAuth, then captures the full cookie
+jar (including HttpOnly cookies) and stores it in the
+`ScraperPlatformAccount` record for `batdongsan`.
+
+Usage:
+    cd nowing_backend
+    PYTHONPATH=. python3 scripts/capture_batdongsan_session.py
+
+The script will print the captured cookies as a Playwright JSON array and
+try to update the default `batdongsan` account. If the DB is not available,
+just save the printed JSON and paste it into the admin UI.
+"""
+
+from __future__ import annotations
+
+import argparse
+import asyncio
+import json
+import logging
+import os
+import sys
+from typing import Any
+
+# Allow running without a package install.
+sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
+
+from playwright.async_api import async_playwright
+
+from app.db import async_session_maker
+from app.services.scraper_platform_account_service import ScraperPlatformAccountService
+
+logger = logging.getLogger(__name__)
+logging.basicConfig(level=logging.INFO)
+
+LOGIN_URL = "https://batdongsan.com.vn/dang-nhap"
+LISTING_URL = "https://batdongsan.com.vn/ban-nha-rieng-pho-ngoc-khanh-phuong-ngoc-khanh-2/toa-chdv-giang-vo-75m2-7-tang-19-8-ty-17pkk-dong-tien-cho-thue-100tr-th-pr46122640"
+
+
+def _read_line(prompt: str) -> str:
+    try:
+        return input(prompt)
+    except (EOFError, KeyboardInterrupt):
+        return ""
+
+
+def _extract_access_token(cookies: list[dict[str, Any]]) -> str | None:
+    for c in cookies:
+        if c.get("name") == "accessToken":
+            return c.get("value")
+    return None
+
+
+def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
+    parser = argparse.ArgumentParser(description="Capture Batdongsan session")
+    parser.add_argument(
+        "--auto",
+        action="store_true",
+        help="Do not wait for Enter; poll cookies until accessToken appears.",
+    )
+    parser.add_argument(
+        "--timeout",
+        type=int,
+        default=300,
+        help="Seconds to wait for login in auto mode (default: 300).",
+    )
+    parser.add_argument(
+        "--no-update-db",
+        action="store_true",
+        help="Only print cookies; do not write to the DB.",
+    )
+    parser.add_argument(
+        "--platform",
+        type=str,
+        default="batdongsan",
+        help="Platform slug to save under (default: batdongsan).",
+    )
+    parser.add_argument(
+        "--cdp",
+        type=str,
+        default=None,
+        help="Connect to an existing Chrome via CDP (e.g. http://localhost:9222).",
+    )
+    return parser.parse_args(argv)
+
+
+async def _save_credentials(
+    credentials: dict[str, Any], platform: str = "batdongsan"
+) -> bool:
+    try:
+        async with async_session_maker() as session:
+            svc = ScraperPlatformAccountService(session)
+            account = await svc.get_default(platform)
+            if account is None:
+                # Create a default account if one does not exist.
+                await svc.create(
+                    platform=platform,
+                    label="captured",
+                    is_enabled=True,
+                    is_default=True,
+                    credentials=credentials,
+                )
+                logger.info("Created default %s scraper account", platform)
+            else:
+                await svc.update(account, {"credentials": credentials})
+                logger.info("Updated default %s scraper account", platform)
+        return True
+    except Exception as exc:
+        logger.warning("Could not save credentials to DB: %s", exc)
+        return False
+
+
+async def _wait_for_login(context, timeout: int = 300) -> list[dict[str, Any]] | None:
+    """Poll cookies until the accessToken appears or we time out."""
+    for attempt in range(timeout // 5):
+        cookies = await context.cookies()
+        if _extract_access_token(cookies):
+            logger.info("accessToken detected on attempt %d", attempt + 1)
+            return cookies
+        await asyncio.sleep(5)
+    return None
+
+
+def _filter_batdongsan_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
+    """Keep cookies whose domain belongs to batdongsan.com.vn."""
+    return [
+        c
+        for c in cookies
+        if c.get("domain", "").endswith(".batdongsan.com.vn")
+        or c.get("domain", "") == "batdongsan.com.vn"
+    ]
+
+
+async def _capture_cookies(context, page) -> list[dict[str, Any]]:
+    """Navigate to a listing and return the filtered Batdongsan cookie jar."""
+    logger.info("Navigating to listing to refresh session cookies")
+    await page.goto(LISTING_URL, wait_until="domcontentloaded", timeout=120_000)
+    await asyncio.sleep(3)
+
+    cookies = await context.cookies()
+    return _filter_batdongsan_cookies(cookies)
+
+
+async def _open_browser_context(p, args: argparse.Namespace):
+    """Launch a fresh Playwright browser or attach to an existing Chrome."""
+    if args.cdp:
+        logger.info("Connecting to existing Chrome at %s", args.cdp)
+        browser = await p.chromium.connect_over_cdp(args.cdp)
+        # Reuse the first existing context, or create a new one if none exists.
+        contexts = browser.contexts
+        context = contexts[0] if contexts else await browser.new_context()
+        # Use the first existing page, or create a new tab.
+        pages = context.pages
+        page = pages[0] if pages else await context.new_page()
+        return browser, context, page
+
+    browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
+    context = await browser.new_context(
+        locale="vi-VN",
+        timezone_id="Asia/Ho_Chi_Minh",
+        viewport={"width": 1440, "height": 900},
+        user_agent=(
+            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
+            "AppleWebKit/537.36 (KHTML, like Gecko) "
+            "Chrome/128.0.0.0 Safari/537.36"
+        ),
+    )
+    page = await context.new_page()
+    return browser, context, page
+
+
+async def capture(args: argparse.Namespace | None = None) -> int:
+    args = args or _parse_args(None)
+    async with async_playwright() as p:
+        browser, context, page = await _open_browser_context(p, args)
+
+        logger.info("Opening login page: %s", LOGIN_URL)
+        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=120_000)
+
+        if args.auto:
+            print(
+                "A browser window is open. Please log in to Batdongsan. "
+                "Cookies will be captured automatically once logged in."
+            )
+            raw_cookies = await _wait_for_login(context, timeout=args.timeout)
+            if raw_cookies is None:
+                logger.error("Timeout waiting for login. No accessToken cookie found.")
+                await browser.close()
+                return 1
+            kept = _filter_batdongsan_cookies(raw_cookies)
+        else:
+            print("\n" + "=" * 60)
+            print("1. Log in to Batdongsan with Google in the opened browser.")
+            print("2. Optionally open a listing and click 'Hiện số' to refresh the token.")
+            print("3. Come back here and press Enter to capture cookies.")
+            print("=" * 60)
+            _read_line("> Press Enter when you are logged in and on the site...")
+            kept = await _capture_cookies(context, page)
+
+        await browser.close()
+
+        if not kept:
+            logger.error("No Batdongsan cookies captured. Did you log in?")
+            return 1
+
+        access_token = _extract_access_token(kept)
+        if not access_token:
+            logger.warning(
+                "No accessToken cookie found; the session may not be logged in"
+            )
+
+        credentials = {
+            "cookies": json.dumps(kept, ensure_ascii=False),
+            "token": access_token,
+        }
+
+        cookie_file = os.path.expanduser("~/batdongsan_cookies.json")
+        with open(cookie_file, "w", encoding="utf-8") as f:
+            json.dump(kept, f, ensure_ascii=False, indent=2)
+        logger.info("Wrote cookies to %s", cookie_file)
+
+        if not args.no_update_db:
+            saved = await _save_credentials(credentials, platform=args.platform)
+            if saved:
+                print("\nSaved to DB. You can now use the scraper.")
+            else:
+                print("\nCould not save to DB. Copy the cookies above into the admin UI.")
+        else:
+            print("\nSkipping DB update because --no-update-db was set.")
+
+        print("\n--- Playwright cookie JSON (filtered) ---")
+        print(json.dumps(kept, ensure_ascii=False, indent=2))
+    return 0
+
+
+def main(argv: list[str] | None = None) -> int:
+    args = _parse_args(argv)
+    return asyncio.run(capture(args))
+
+
+if __name__ == "__main__":
+    sys.exit(main())
