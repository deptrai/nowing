"""Muaban.net BĐS Universal Scraper Adapter (Story 21.20)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.adapters._query_parser import (
    extract_listing_type_bds,
    extract_price_range,
    extract_property_type_chotot,
    resolve_muaban_bds_city,
)
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


class MuabanBdsLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Muaban.net real estate listings into the lead pipeline."""

    source_name = "muaban_bds"
    category = LeadSourceCategory.REAL_ESTATE

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _query_muaban_bds_api(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call the underlying Muaban.net BĐS scraper."""
        from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput
        from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds

        city = resolve_muaban_bds_city(query, filters)
        min_price, max_price = extract_price_range(query)
        listing_type = extract_listing_type_bds(query)
        property_type = extract_property_type_chotot(query)

        input_model = MuabanBdsScrapeInput(
            city=city,
            listing_type=listing_type,
            property_type=property_type or "all",
            min_price=min_price,
            max_price=max_price,
            max_items=min(limit, 20),
            max_pages=5,
        )
        output = await scrape_muaban_bds(input_model)

        if output.degraded:
            logger.warning(
                "Muaban BĐS scraper degraded: %s", output.degradation_reason
            )
            self.last_execution_status = "degraded"

        return [item.to_output() for item in output.items]

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search Muaban.net BĐS listings with retry and graceful degradation."""
        self.last_execution_status = "ok"
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._query_muaban_bds_api(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                if self.last_execution_status != "degraded":
                    self.last_execution_status = "ok"
                return [
                    RawLeadRecord(
                        source_name=self.source_name,
                        source_id=str(
                            item.get("listing_id")
                            or item.get("detail_url")
                            or f"muaban_bds_{idx}"
                        ),
                        data=item,
                        category=self.category,
                    )
                    for idx, item in enumerate(items)
                ]
            except Exception as exc:
                last_exc = exc
                logger.warning("Muaban BĐS search attempt %d failed: %s", attempt, exc)

        logger.error(
            "Muaban BĐS scraper failed after %d attempts: %s", attempt, last_exc
        )
        self.last_execution_status = "degraded"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize Muaban BĐS item to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = candidates[0].value if candidates else None

        price_val: float | None = _to_float(data.get("price_value"))
        if price_val is None and data.get("price") is not None:
            price_val = _to_float(str(data.get("price")).replace(",", ""))

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Tin đăng Muaban BĐS",
            company_name=data.get("company") or data.get("agency_name"),
            primary_phone=primary_phone,
            contact_name=data.get("contact_name") or data.get("seller_name"),
            price=price_val,
            city=data.get("city") or data.get("location"),
            address=data.get("location") or data.get("address"),
            confidence_score=80.0 if primary_phone else 60.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone contact candidates from Muaban BĐS record."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        direct_phone = (
            data.get("phone")
            or data.get("phone_display")
            or data.get("phone_enc")
            or data.get("contact_phone")
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
                        metadata={"source_field": "phone"},
                    )
                )

        body_text = data.get("description") or data.get("title") or ""
        for phone in extract_phones_from_text(body_text):
            if phone not in seen_phones:
                seen_phones.add(phone)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=phone,
                        confidence=0.85,
                        metadata={"source_field": "body_text"},
                    )
                )

        return candidates
