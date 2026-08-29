"""Chợ Tốt Multi-Category Universal Scraper Adapter (Story 21.15)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.adapters._query_parser import (
    extract_listing_type_chotot,
    extract_price_range,
    extract_property_type_chotot,
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
    normalize_vietnamese_phone,
)

logger = logging.getLogger(__name__)


class ChototLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Chợ Tốt classified ads (BĐS focus for now)."""

    source_name = "chotot"
    category = LeadSourceCategory.REAL_ESTATE

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _query_chotot_api(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call underlying Chợ Tốt BĐS scraper."""
        from app.proprietary.platforms.chotot.schemas import ChototScrapeInput
        from app.proprietary.platforms.chotot.scraper import scrape_chotot

        city = resolve_chotot_city(query, filters)
        min_price, max_price = extract_price_range(query)
        listing_type = extract_listing_type_chotot(query)
        property_type = extract_property_type_chotot(query)

        input_model = ChototScrapeInput(
            category="bds",
            listing_type=listing_type,
            property_type=property_type or "all",
            city=city,
            min_price=min_price,
            max_price=max_price,
            max_items=min(limit, 20),
            max_pages=5,
        )
        output = await scrape_chotot(input_model, limit=min(limit, 20))

        if output.degraded:
            logger.warning(
                "Chotot scraper degraded: %s", output.degradation_reason
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
        """Search Chợ Tốt ads with retry and graceful degradation."""
        self.last_execution_status = "ok"
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._query_chotot_api(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                if self.last_execution_status != "degraded":
                    self.last_execution_status = "ok"
                return [
                    RawLeadRecord(
                        source_name=self.source_name,
                        source_id=str(
                            item.get("listing_id")
                            or item.get("list_id")
                            or item.get("ad_id")
                            or item.get("detail_url")
                            or f"ct_{idx}"
                        ),
                        data=item,
                        category=self.category,
                    )
                    for idx, item in enumerate(items)
                ]
            except Exception as exc:
                last_exc = exc
                logger.warning("Chotot search attempt %d failed: %s", attempt, exc)

        logger.error("Chotot scraper failed after %d attempts: %s", attempt, last_exc)
        self.last_execution_status = "degraded"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize Chợ Tốt item to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = candidates[0].value if candidates else None

        price_val: float | None = None
        if data.get("price_value") is not None:
            price_val = _to_float(data.get("price_value"))
        elif data.get("price") is not None:
            price_val = _to_float(str(data.get("price")).replace(",", ""))

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or data.get("subject") or "Tin đăng Chợ Tốt",
            company_name=data.get("company_name"),
            primary_phone=primary_phone,
            contact_name=data.get("account_name")
            or data.get("contact_name")
            or data.get("seller_type"),
            price=price_val,
            city=data.get("city") or data.get("region_name") or data.get("area_name"),
            address=data.get("location")
            or data.get("address")
            or data.get("region_name"),
            confidence_score=80.0 if primary_phone else 60.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone contact candidates from Chợ Tốt record."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        direct_phone = data.get("phone") or data.get("contact_phone")
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

        body_text = data.get("body") or data.get("description") or ""
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
