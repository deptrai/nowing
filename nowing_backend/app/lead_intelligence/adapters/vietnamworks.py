"""VietnamWorks direct job-market lead adapter (Story 21.20)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.lead_intelligence.adapters._query_parser import (
    extract_price_range,
)
from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    _to_float,
    extract_phones_from_text,
)
from app.proprietary.platforms.vietnamworks.scraper import scrape_vietnamworks
from app.services.pii.redact import redact_job_pii

logger = logging.getLogger(__name__)


def _extract_domain(url: str | None) -> str | None:
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


def _select_salary_value(salary_min: Any, salary_max: Any, salary_raw: Any) -> Any:
    """Return a numeric salary value, treating "thỏa thuận"/zero as None."""
    raw_text = str(salary_raw or "").lower()
    is_negotiable = (
        (salary_min == 0 and salary_max == 0)
        or ("thỏa thuận" in raw_text)
        or ("thương lượng" in raw_text)
        or ("negotiable" in raw_text)
    )
    if is_negotiable:
        return None
    if salary_min not in (None, 0):
        return salary_min
    if salary_max not in (None, 0):
        return salary_max
    return None


class VietnamWorksLeadAdapter(LeadSourceAdapter):
    """Adapter that surfaces hiring-company leads directly from VietnamWorks."""

    source_name = "vietnamworks"
    category = LeadSourceCategory.JOB_MARKET

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    def _redact_job_text(self, item: dict[str, Any]) -> dict[str, Any]:
        """Mask PII in job description/requirement before downstream use."""
        for field in ("job_description", "job_requirement"):
            value = item.get(field)
            if value:
                item[field] = redact_job_pii(value).text
        return item

    async def _fetch_vietnamworks_jobs(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call the VietnamWorks public job-search API."""
        min_price, max_price = extract_price_range(query)

        params: dict[str, Any] = {
            "keyword": query,
            "max_items": min(limit, 20),
            "max_pages": 5,
        }
        if min_price is not None:
            params["salary_min"] = min_price
        if max_price is not None:
            params["salary_max"] = max_price

        output = await scrape_vietnamworks(params)

        if output.get("degraded"):
            logger.warning(
                "VietnamWorks scraper degraded: %s",
                output.get("degradation_reason"),
            )
            self.last_execution_status = "degraded"

        return [self._redact_job_text(item) for item in output.get("items", [])]

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search VietnamWorks job listings with graceful degradation."""
        self.last_execution_status = "ok"
        try:
            items = await self._fetch_vietnamworks_jobs(
                workspace_id=workspace_id, query=query, filters=filters, limit=limit
            )
            if self.last_execution_status != "degraded":
                self.last_execution_status = "ok"
            return [
                RawLeadRecord(
                    source_name=self.source_name,
                    source_id=str(item.get("id") or f"vietnamworks_{idx}"),
                    data=item,
                    category=self.category,
                )
                for idx, item in enumerate(items)
            ]
        except Exception as exc:
            logger.error("VietnamWorks search failed: %s", exc)
            self.last_execution_status = "degraded"
            return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize a VietnamWorks job item to a company lead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )
        primary_email = next(
            (c.value for c in candidates if c.channel == "email"), None
        )

        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")
        salary_raw = data.get("salary_raw")
        salary_val = _select_salary_value(salary_min, salary_max, salary_raw)

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Tuyển dụng nhân sự",
            company_name=data.get("company") or "Doanh nghiệp tuyển dụng",
            canonical_domain=_extract_domain(data.get("company_website") or data.get("source_url")),
            primary_phone=primary_phone,
            primary_email=primary_email,
            city=data.get("location"),
            address=data.get("location"),
            price=_to_float(salary_val),
            source_url=data.get("source_url"),
            confidence_score=85.0 if (primary_phone or primary_email) else 70.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract contact candidates from redacted VietnamWorks job text.

        Job descriptions are PII-redacted before downstream use, so real
        phone/email are intentionally not exposed.
        """
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen: set[str] = set()

        body_text = " ".join(
            str(v)
            for v in [data.get("job_description"), data.get("job_requirement")]
            if v
        )
        for phone in extract_phones_from_text(body_text):
            if phone not in seen:
                seen.add(phone)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=phone,
                        confidence=0.70,
                        metadata={"source_field": "job_description"},
                    )
                )

        return candidates
