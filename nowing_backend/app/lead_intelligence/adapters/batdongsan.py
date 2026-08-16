"""Batdongsan and Muaban BĐS Universal Scraper Adapter (Story 21.15)."""

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


class BatdongsanLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Batdongsan.com.vn and Muaban.net real estate listings."""

    source_name = "batdongsan"
    category = LeadSourceCategory.REAL_ESTATE

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _fetch_raw_listings(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call underlying Batdongsan scraper routines."""
        try:
            from app.proprietary.platforms.batdongsan.schemas import (
                BatdongsanScrapeInput,
            )
            from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan

            input_model = BatdongsanScrapeInput(
                query=query,
                max_items=min(limit, 20),
            )
            output = await scrape_batdongsan(input_model)
            results = []
            for item in output.items:
                results.append({
                    "id": item.id,
                    "title": item.title,
                    "price_vnd": item.price_vnd,
                    "location": item.location,
                    "project_name": item.project_name,
                    "contact_phone": getattr(item, "phone", None) or getattr(item, "contact_phone", None),
                    "description": item.description,
                    "url": item.url,
                })
            return results
        except Exception as exc:
            logger.warning("Live Batdongsan scrape error: %s", exc)
            return []

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search property listings with anti-loop max 1 retry and graceful degradation (AD-19.1)."""
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._fetch_raw_listings(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                self.last_execution_status = "ok"
                return [
                    RawLeadRecord(
                        source_name=self.source_name,
                        source_id=str(
                            item.get("id") or item.get("url") or f"bds_{idx}"
                        ),
                        data=item,
                        category=self.category,
                    )
                    for idx, item in enumerate(items)
                ]
            except Exception as exc:
                last_exc = exc
                logger.warning("Batdongsan scraper attempt %d failed: %s", attempt, exc)

        # Fail-soft graceful degradation
        logger.error(
            "Batdongsan scraper failed after %d attempts: %s. Returning degraded status.",
            attempt,
            last_exc,
        )
        self.last_execution_status = "degraded"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize property listing to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = candidates[0].value if candidates else None

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Bất động sản rao bán",
            company_name=data.get("project_name") or data.get("agency_name"),
            primary_phone=primary_phone,
            contact_name=data.get("contact_name") or data.get("author"),
            price=float(data.get("price_vnd") or data.get("price") or 0.0) or None,
            city=data.get("location") or data.get("city"),
            address=data.get("address") or data.get("location"),
            confidence_score=85.0 if primary_phone else 65.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract verified phone numbers from raw listing metadata and description."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        # 1. Unmasked / direct phone fields
        direct_phone = (
            data.get("contact_phone_unmasked")
            or data.get("contact_phone")
            or data.get("phone")
        )
        if direct_phone:
            norm = normalize_vietnamese_phone(str(direct_phone))
            if norm and norm not in seen_phones:
                seen_phones.add(norm)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=norm,
                        confidence=0.95,
                        metadata={"source_field": "contact_phone"},
                    )
                )

        # 2. Extract from description text
        desc = data.get("description") or ""
        text_phones = extract_phones_from_text(desc)
        for phone in text_phones:
            if phone not in seen_phones:
                seen_phones.add(phone)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=phone,
                        confidence=0.85,
                        metadata={"source_field": "description_text"},
                    )
                )

        return candidates
