"""Batdongsan and Muaban BĐS Universal Scraper Adapter (Story 21.15)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from app.lead_intelligence.adapters._query_parser import (
    extract_listing_type_bds,
    extract_price_range,
    resolve_batdongsan_city,
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
from app.lead_intelligence.services.circuit_breaker import PlatformCircuitBreaker

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
        from app.proprietary.platforms.batdongsan.schemas import (
            BatdongsanScrapeInput,
        )
        from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan

        city = resolve_batdongsan_city(query, filters)
        min_price, max_price = extract_price_range(query)
        listing_type = extract_listing_type_bds(query)

        input_model = BatdongsanScrapeInput(
            city=city,
            listing_type=listing_type,
            min_price=min_price,
            max_price=max_price,
            max_items=min(limit, 10),
            max_pages=2,
            resolve_phones=True,
        )

        breaker = PlatformCircuitBreaker()
        if not await breaker.is_available(self.source_name):
            logger.warning("Circuit breaker open for %s", self.source_name)
            self.last_execution_status = "degraded"
            return []

        try:
            output = await asyncio.wait_for(
                scrape_batdongsan(
                    input_model, resolve_phones=input_model.resolve_phones
                ),
                timeout=90.0,
            )
        except TimeoutError:
            logger.warning("Batdongsan scraper timed out after 90s")
            await breaker.record_failure(self.source_name, "timeout")
            self.last_execution_status = "degraded"
            return []
        except Exception:
            await breaker.record_failure(self.source_name, "scraper_error")
            raise

        with contextlib.suppress(Exception):
            await breaker.record_success(self.source_name)

        if output.degraded:
            logger.warning("Batdongsan scraper degraded: %s", output.degradation_reason)
            self.last_execution_status = "degraded"

        results = []
        for item in output.items:
            data = item.to_output()
            results.append(
                {
                    "id": data.get("listing_id") or data.get("detail_url"),
                    "title": data.get("title"),
                    "price_vnd": data.get("price") or data.get("price_vnd"),
                    "location": data.get("location"),
                    "city": data.get("city"),
                    "district": data.get("district"),
                    "project_name": data.get("project_name"),
                    "contact_phone": data.get("phone"),
                    "description": data.get("description") or "",
                    "url": data.get("detail_url"),
                    "price_value": data.get("price_value"),
                    "area_value": data.get("area_value"),
                }
            )
        return results

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search property listings with anti-loop max 1 retry and graceful degradation (AD-19.1)."""
        self.last_execution_status = "ok"
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._fetch_raw_listings(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                if self.last_execution_status != "degraded":
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
            price=_to_float(
                data.get("price_value") or data.get("price_vnd") or data.get("price")
            )
            or None,
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
        """Extract phone, email, and social handles from raw listing metadata and description."""
        from app.lead_intelligence.adapters.base import (
            extract_emails_from_text,
            extract_social_ids_from_text,
        )

        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()
        seen_emails: set[str] = set()
        seen_social: set[str] = set()

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

        # 2. Extract from title + description text
        text = f"{data.get('title') or ''} {data.get('description') or ''}"
        for phone in extract_phones_from_text(text):
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

        for email in extract_emails_from_text(text):
            if email not in seen_emails:
                seen_emails.add(email)
                candidates.append(
                    ContactCandidate(
                        channel="email",
                        value=email,
                        confidence=0.8,
                        metadata={"source_field": "description_text"},
                    )
                )

        for channel, values in extract_social_ids_from_text(text).items():
            for value in values:
                key = f"{channel}:{value}"
                if key not in seen_social:
                    seen_social.add(key)
                    candidates.append(
                        ContactCandidate(
                            channel=channel,
                            value=value,
                            confidence=0.6,
                            metadata={"source_field": "description_text"},
                        )
                    )

        return candidates
