"""Vietnam News Aggregator Universal Scraper Adapter (Story 21.15 / Epic 26 Retro Action 4)."""

from __future__ import annotations

import logging
from typing import Any

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


class NewsLeadAdapter(LeadSourceAdapter):
    """Adapter for Vietnamese news / press releases used as lead-signal triggers."""

    source_name = "news"
    category = LeadSourceCategory.NEWS
    # National news portals cover all provinces; regional dailies bias toward
    # their home province.
    supported_provinces = ["*"]
    coverage_quality_by_location = {
        "HN": "high",
        "SG": "high",
        "DN": "medium",
        "HP": "medium",
        "CT": "medium",
        "BD": "low",
        "DNA": "low",
        "KH": "low",
        "LD": "low",
    }

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search news articles mentioning the query."""
        self.last_execution_status = "ok"
        # v1 exposes metadata only; live news search is handled by the RSS /
        # news pipeline.
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Tin tức doanh nghiệp",
            company_name=data.get("company_name") or data.get("source"),
            primary_phone=primary_phone,
            contact_name=data.get("author") or data.get("reporter"),
            confidence_score=65.0 if primary_phone else 50.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        phone = data.get("contact_phone")
        if phone:
            norm = normalize_vietnamese_phone(str(phone))
            if norm and norm not in seen_phones:
                seen_phones.add(norm)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=norm,
                        confidence=0.85,
                        metadata={"source_field": "contact_phone"},
                    )
                )

        body = data.get("body") or data.get("content") or ""
        for p in extract_phones_from_text(body):
            if p not in seen_phones:
                seen_phones.add(p)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=p,
                        confidence=0.75,
                        metadata={"source_field": "body"},
                    )
                )

        return candidates
