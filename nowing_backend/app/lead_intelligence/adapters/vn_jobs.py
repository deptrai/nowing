"""VnJobs (TopCV + ITviec + VietnamWorks) aggregate job-market adapter (Story 21.20)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.lead_intelligence.adapters._query_parser import (
    extract_price_range,
    resolve_chotot_city,
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
from app.services.jobs_aggregator import aggregate_jobs
from app.services.jobs_aggregator.schemas import VnJobAggregateInput

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


def _select_salary_value(
    salary_min: Any,
    salary_max: Any,
    salary_period: Any,
    salary_raw: Any,
) -> Any:
    """Return a numeric salary value, treating "thỏa thuận"/hidden/zero as None."""
    raw_text = str(salary_raw or "").lower()
    is_negotiable = (
        salary_period in ("negotiable", "hidden")
        or (salary_min == 0 and salary_max == 0)
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


class VnJobsLeadAdapter(LeadSourceAdapter):
    """Adapter that surfaces hiring-company leads from the multi-source job aggregator."""

    source_name = "vn_jobs"
    category = LeadSourceCategory.JOB_MARKET

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _aggregate_job_listings(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call the existing multi-source job aggregator without persisting."""
        city = resolve_chotot_city(query, filters, default=None)
        min_price, max_price = extract_price_range(query)

        input_model = VnJobAggregateInput(
            keyword=query,
            location=city,
            salary_min=min_price,
            salary_max=max_price,
            sources=["topcv", "itviec", "vietnamworks"],
            max_items_per_source=min(limit, 20),
            max_pages=5,
        )

        output = await aggregate_jobs(input_model, None)

        if output.degraded or output.degradation_reasons:
            logger.warning(
                "VnJobs aggregate degraded: %s",
                output.degradation_reasons,
            )
            self.last_execution_status = "degraded"

        return [item.model_dump() for item in output.items]

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search aggregated job listings with graceful degradation."""
        self.last_execution_status = "ok"
        try:
            items = await self._aggregate_job_listings(
                workspace_id=workspace_id, query=query, filters=filters, limit=limit
            )
            if self.last_execution_status != "degraded":
                self.last_execution_status = "ok"
            return [
                RawLeadRecord(
                    source_name=self.source_name,
                    source_id=str(item.get("id") or f"vn_jobs_{idx}"),
                    data=item,
                    category=self.category,
                )
                for idx, item in enumerate(items)
            ]
        except Exception as exc:
            logger.error("VnJobs aggregate search failed: %s", exc)
            self.last_execution_status = "degraded"
            return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize an aggregated job listing to a company lead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )
        primary_email = next(
            (c.value for c in candidates if c.channel == "email"), None
        )

        source_url = (data.get("source_urls") or [None])[0]
        salary = data.get("salary") or {}
        salary_min = salary.get("min") if isinstance(salary, dict) else None
        salary_max = salary.get("max") if isinstance(salary, dict) else None
        salary_period = salary.get("period") if isinstance(salary, dict) else None
        salary_raw = salary.get("raw") if isinstance(salary, dict) else None
        salary_val = _select_salary_value(salary_min, salary_max, salary_period, salary_raw)

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Tuyển dụng nhân sự",
            company_name=data.get("company") or "Doanh nghiệp tuyển dụng",
            canonical_domain=_extract_domain(data.get("company_website") or source_url),
            primary_phone=primary_phone,
            primary_email=primary_email,
            city=data.get("location"),
            address=data.get("location"),
            price=_to_float(salary_val),
            source_url=source_url,
            confidence_score=85.0 if (primary_phone or primary_email) else 70.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract contact candidates from PII-redacted job text.

        The job aggregator already redacts phones/emails from descriptions before
        returning listings, so real contact details are intentionally not exposed.
        """
        data = raw_record.data
        candidates: list[ContactCandidate] = []

        body_text = " ".join(
            str(v)
            for v in [data.get("job_description"), data.get("job_requirement")]
            if v
        )
        seen: set[str] = set()
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
