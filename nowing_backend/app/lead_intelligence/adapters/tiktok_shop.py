"""TikTok Shop Vietnam Universal Scraper Adapter (Story 21.15 / Epic 26 Retro Action 4)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    _to_float,
    extract_phones_from_text,
    normalize_vietnamese_phone,
)

logger = logging.getLogger(__name__)


class TiktokShopLeadAdapter(LeadSourceAdapter):
    """Adapter for TikTok Shop Vietnam product / seller listings."""

    source_name = "tiktok_shop"
    category = LeadSourceCategory.E_COMMERCE
    # TikTok Shop ships nationwide; trend products often skew to major metros.
    supported_provinces = ["*"]
    coverage_quality_by_location = {
        "HN": "high",
        "SG": "high",
        "DN": "high",
        "HP": "medium",
        "CT": "medium",
        "BD": "medium",
        "DNA": "medium",
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
        """Search TikTok Shop listings."""
        self.last_execution_status = "ok"
        # v1 exposes metadata only; live scraping routes via e-commerce capability.
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
            title=data.get("title") or "Sản phẩm TikTok Shop",
            company_name=data.get("shop_name") or data.get("seller"),
            primary_phone=primary_phone,
            contact_name=data.get("seller_name") or data.get("shop_name"),
            price=_to_float(data.get("price")) or None,
            city=data.get("location") or data.get("city"),
            confidence_score=68.0 if primary_phone else 52.0,
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

        phone = data.get("contact_phone") or data.get("seller_phone")
        if phone:
            norm = normalize_vietnamese_phone(str(phone))
            if norm and norm not in seen_phones:
                seen_phones.add(norm)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=norm,
                        confidence=0.88,
                        metadata={"source_field": "seller_phone"},
                    )
                )

        desc = data.get("description") or ""
        for p in extract_phones_from_text(desc):
            if p not in seen_phones:
                seen_phones.add(p)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=p,
                        confidence=0.78,
                        metadata={"source_field": "description"},
                    )
                )

        return candidates
