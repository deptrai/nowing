"""Muasamcong e-GP v2.0 REST Scraper and Rate Limiter (Story 16.5 / AD-PROC-1, AD-PROC-4, AD-PROC-6)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.proprietary.platforms.muasamcong.schemas import (
    ProcurementTenderItem,
    ScrapeResult,
)

logger = logging.getLogger(__name__)

# e-GP v2.0 REST Endpoints
DEFAULT_BASE_URL = "https://muasamcong.mpi.gov.vn"
SEARCH_ENDPOINT = "/api/v1/tender/notice/search"
DETAIL_ENDPOINT = "/api/v1/tender/notice/detail/{bid_no}"

# AD-PROC-4: Vietnamese ISP Proxy & Token-Bucket Rate Limiting (<= 15 req/min)
MAX_REQUESTS_PER_MINUTE = 15.0
DEFAULT_REFILL_RATE = MAX_REQUESTS_PER_MINUTE / 60.0  # 0.25 tokens/sec
DEFAULT_CAPACITY = MAX_REQUESTS_PER_MINUTE  # 15.0 tokens


class MuasamcongTokenBucket:
    """Async Token-Bucket Rate Limiter enforcing <= 15 requests/minute (AD-PROC-4)."""

    def __init__(self, rate: float = DEFAULT_REFILL_RATE, capacity: float = DEFAULT_CAPACITY) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        delta = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + delta * self.rate)
        self.last_refill = now

    async def acquire(self, tokens: float = 1.0) -> bool:
        """Acquires tokens, sleeping asynchronously if needed to satisfy rate limit."""
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                # Calculate sleep duration to replenish required tokens
                needed = tokens - self.tokens
                sleep_duration = needed / self.rate

            await asyncio.sleep(min(sleep_duration, 5.0))


def _parse_iso_datetime(val: Any) -> datetime | None:
    """Parses various date/time formats into UTC datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    if isinstance(val, (int, float)):
        # Handle unix timestamps in ms or s
        ts = val / 1000.0 if val > 1e11 else val
        return datetime.fromtimestamp(ts, tz=UTC)
    if isinstance(val, str):
        try:
            # Handle standard ISO formats
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
        # Try custom e-GP format: DD/MM/YYYY HH:MM or YYYY-MM-DD HH:MM:SS
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


class MuasamcongScraper:
    """Ingests tender intelligence from e-GP v2.0 REST API (muasamcong.mpi.gov.vn)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        proxy_url: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url
        self.proxy_url = proxy_url
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = MuasamcongTokenBucket(
            rate=DEFAULT_REFILL_RATE,
            capacity=DEFAULT_CAPACITY,
        )

    def _get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://muasamcong.mpi.gov.vn/",
            "Origin": "https://muasamcong.mpi.gov.vn",
        }

    def _normalize_item(self, raw: dict[str, Any]) -> ProcurementTenderItem:
        """Converts raw e-GP JSON item into a validated ProcurementTenderItem."""
        bid_no = str(raw.get("bidNo") or raw.get("bid_no") or raw.get("bidCode") or "")
        bid_turn_no = str(raw.get("bidTurnNo") or raw.get("bid_turn_no") or "00")
        project_name = str(raw.get("bidName") or raw.get("bid_name") or raw.get("projectName") or "Gói thầu")
        procuring_entity = raw.get("procuringEntityName") or raw.get("procuring_entity")
        investor = raw.get("investorName") or raw.get("investor")
        field = raw.get("bidField") or raw.get("field") or raw.get("procurement_field")
        bid_type = raw.get("bidType") or raw.get("bid_type")
        funding_source = raw.get("fundingSource") or raw.get("funding_source")

        # Normalize price
        raw_price = raw.get("bidPrice") or raw.get("bid_price") or raw.get("totalAmount")
        bid_price: float | None = None
        if raw_price is not None:
            try:
                bid_price = float(str(raw_price).replace(",", "").strip())
            except (ValueError, TypeError):
                bid_price = None

        bid_open_date = _parse_iso_datetime(raw.get("bidOpenDate") or raw.get("bid_open_date"))
        bid_closing_at = _parse_iso_datetime(raw.get("bidCloseDate") or raw.get("bid_close_date") or raw.get("bid_closing_at"))
        location = raw.get("location") or raw.get("bidLocation") or raw.get("province")

        doc_urls = raw.get("documentUrls") or raw.get("document_urls") or []
        dossier_url = doc_urls[0] if isinstance(doc_urls, list) and doc_urls else raw.get("dossier_url")

        raw_specs = raw.get("rawSpecs") or raw.get("raw_specs") or {}
        raw_status = str(raw.get("status") or "").upper()
        status = "closed" if "CLOSE" in raw_status else ("cancelled" if "CANCEL" in raw_status else "active")

        return ProcurementTenderItem(
            bid_no=bid_no,
            bid_turn_no=bid_turn_no,
            project_name=project_name,
            procuring_entity=procuring_entity,
            investor=investor,
            field=field,
            bid_type=bid_type,
            funding_source=funding_source,
            bid_price=bid_price,
            bid_open_date=bid_open_date,
            bid_closing_at=bid_closing_at,
            location=location,
            dossier_url=dossier_url,
            raw_specs=raw_specs,
            status=status,
        )

    async def search_tenders(
        self,
        keyword: str | None = None,
        field: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        location: str | None = None,
        page: int = 0,
        size: int = 10,
    ) -> ScrapeResult:
        """Queries e-GP v2.0 REST search endpoint with token-bucket rate limiting."""
        await self.rate_limiter.acquire(1.0)

        payload: dict[str, Any] = {
            "pageNumber": page,
            "pageSize": size,
            "keyword": keyword or "",
            "field": field,
            "minPrice": min_price,
            "maxPrice": max_price,
            "location": location,
        }
        # Clean null values
        payload = {k: v for k, v in payload.items() if v is not None}

        url = urljoin(self.base_url, SEARCH_ENDPOINT)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                proxy=self.proxy_url,
                headers=self._get_headers(),
                follow_redirects=True,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                content_list = []
                total_elements = 0
                total_pages = 0
                page_num = page

                if isinstance(data, dict):
                    data_body = data.get("data") or data
                    if isinstance(data_body, dict):
                        content_list = data_body.get("content") or data_body.get("items") or []
                        total_elements = int(data_body.get("totalElements") or len(content_list))
                        total_pages = int(data_body.get("totalPages") or 1)
                        page_num = int(data_body.get("pageNumber") or page)
                    elif isinstance(data_body, list):
                        content_list = data_body
                        total_elements = len(content_list)
                        total_pages = 1

                items = [self._normalize_item(item) for item in content_list]

                return ScrapeResult(
                    items=items,
                    total_elements=total_elements,
                    total_pages=total_pages,
                    page_number=page_num,
                    page_size=size,
                    degraded=False,
                )

        except Exception as exc:
            logger.warning(
                "Muasamcong scraper search failed or timed out: %s. Entering degraded mode.",
                str(exc),
            )
            return ScrapeResult(
                items=[],
                total_elements=0,
                total_pages=0,
                page_number=page,
                page_size=size,
                degraded=True,
                degradation_reason=str(exc),
            )

    async def get_tender_detail(
        self,
        bid_no: str,
        bid_turn_no: str = "00",
    ) -> ProcurementTenderItem | None:
        """Fetches detailed tender specs and dossier URLs by bid number."""
        await self.rate_limiter.acquire(1.0)

        endpoint = DETAIL_ENDPOINT.format(bid_no=bid_no)
        url = urljoin(self.base_url, endpoint)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                proxy=self.proxy_url,
                headers=self._get_headers(),
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params={"turnNo": bid_turn_no})
                response.raise_for_status()
                data = response.json()

                raw_item = data.get("data") if isinstance(data, dict) and "data" in data else data
                if isinstance(raw_item, dict):
                    return self._normalize_item(raw_item)
                return None

        except Exception as exc:
            logger.warning(
                "Failed to fetch tender detail for %s (%s): %s",
                bid_no,
                bid_turn_no,
                str(exc),
            )
            return None
