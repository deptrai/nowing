"""TopCV and ITviec Recruitment Job Market Universal Scraper Adapter (Story 21.15)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    extract_phones_from_text,
    normalize_vietnamese_phone,
)

logger = logging.getLogger(__name__)


def _extract_domain(url: str | None) -> str | None:
    """Safely extract canonical domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


class JobMarketLeadAdapter(LeadSourceAdapter):
    """Adapter aggregating TopCV and ITviec job postings to surface hiring company leads."""

    source_name = "job_market"
    category = LeadSourceCategory.JOB_MARKET

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _search_topcv(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Query TopCV recruitment portal."""
        from app.proprietary.platforms.topcv.scraper import scrape_topcv

        # ponytail: scrape_topcv currently only supports keyword search;
        # location filter is not wired in the underlying scraper.
        params: dict[str, Any] = {
            "keyword": query,
            "max_items": min(limit, 20),
            "max_pages": 2,
            "fetch_details": True,
        }
        raw = await scrape_topcv(params)
        return raw.get("items", [])

    async def _search_itviec(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Query ITviec tech recruitment portal."""
        from app.proprietary.platforms.itviec.scraper import scrape_itviec

        # ponytail: scrape_itviec currently only supports keyword search.
        params: dict[str, Any] = {
            "keyword": query,
            "max_items": min(limit, 20),
            "max_pages": 2,
            "fetch_details": True,
        }
        raw = await scrape_itviec(params)
        return raw.get("items", [])

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Aggregate recruitment leads across multiple portals with error isolation."""
        half_limit = max(1, limit // 2)

        results = await asyncio.gather(
            self._search_topcv(workspace_id, query, filters, half_limit),
            self._search_itviec(workspace_id, query, filters, half_limit),
            return_exceptions=True,
        )
        topcv_items = results[0] if isinstance(results[0], list) else []
        itviec_items = results[1] if isinstance(results[1], list) else []

        raw_records: list[RawLeadRecord] = []
        for idx, item in enumerate(topcv_items):
            raw_records.append(
                RawLeadRecord(
                    source_name="topcv",
                    source_id=str(
                        item.get("id") or item.get("job_id") or f"topcv_{idx}"
                    ),
                    data=item,
                    category=self.category,
                )
            )
        for idx, item in enumerate(itviec_items):
            raw_records.append(
                RawLeadRecord(
                    source_name="itviec",
                    source_id=str(item.get("id") or item.get("job_id") or f"itv_{idx}"),
                    data=item,
                    category=self.category,
                )
            )

        if isinstance(results[0], Exception) or isinstance(results[1], Exception):
            self.last_execution_status = "degraded"
        else:
            self.last_execution_status = "ok"

        return raw_records

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize recruitment item to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )
        primary_email = next(
            (c.value for c in candidates if c.channel == "email"), None
        )

        domain = _extract_domain(data.get("company_website") or data.get("website"))

        location = data.get("location") or data.get("address") or ""
        city: str | None = None
        if location and ":" in location:
            city = location.split(":", 1)[0].strip()
        elif location:
            city = location

        company = (
            data.get("company") or data.get("company_name") or "Doanh nghiệp tuyển dụng"
        )

        return NormalizedLead(
            source_name=raw_record.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Tuyển dụng nhân sự",
            company_name=company,
            canonical_domain=domain,
            primary_phone=primary_phone,
            primary_email=primary_email,
            tax_id=data.get("tax_id"),
            contact_name=data.get("hr_name") or data.get("contact_person"),
            city=city,
            address=location or data.get("address"),
            confidence_score=85.0 if (primary_phone or primary_email) else 70.0,
            sources=[raw_record.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract HR email, phone numbers, and domain candidates."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []

        # HR email
        email = data.get("hr_email") or data.get("email") or data.get("contact_email")
        if email and "@" in str(email):
            candidates.append(
                ContactCandidate(
                    channel="email",
                    value=str(email).strip().lower(),
                    confidence=0.95,
                    metadata={"source_field": "hr_email"},
                )
            )

        # Phone
        direct_phone = (
            data.get("hr_phone") or data.get("phone") or data.get("contact_phone")
        )
        if direct_phone:
            norm = normalize_vietnamese_phone(str(direct_phone))
            if norm:
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=norm,
                        confidence=0.95,
                        metadata={"source_field": "hr_phone"},
                    )
                )

        # Body text phones
        body_text = " ".join(
            str(v)
            for v in [data.get("job_description"), data.get("job_requirement")]
            if v
        )
        for phone in extract_phones_from_text(body_text):
            candidates.append(
                ContactCandidate(
                    channel="phone",
                    value=phone,
                    confidence=0.80,
                    metadata={"source_field": "job_description"},
                )
            )

        return candidates
