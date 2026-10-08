"""Batdongsan and Muaban BĐS Universal Scraper Adapter (Story 21.15)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.capabilities.core.medirus_proxy import medirus_scrape_or_local
from app.lead_intelligence.adapters._query_parser import (
    extract_listing_type_bds,
    extract_price_range,
    resolve_batdongsan_city,
)
from app.lead_intelligence.adapters.base import (
    _VALID_VN_PREFIXES,
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


def _extract_domain(url: str | None) -> str | None:
    """Safely extract canonical domain from URL."""
    if not url or not str(url).strip():
        return None
    try:
        url_str = str(url).strip()
        parsed = urlparse(url_str if "://" in url_str else f"https://{url_str}")
        netloc = (parsed.netloc or "").lower().strip()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


def _derive_bds_company_name(data: dict[str, Any]) -> str:
    """Derive clean company/entity name from project_name, agency_name, or location.

    Prevents classified ad titles from being treated as company names.
    """
    project_or_agency = (
        data.get("project_name") or data.get("agency_name") or data.get("company_name")
    )
    if project_or_agency and str(project_or_agency).strip():
        return str(project_or_agency).strip()[:200]

    district = str(data.get("district") or "").strip()
    city = str(data.get("city") or "").strip()

    if district and city:
        if district.lower() == city.lower():
            return f"BĐS {district}"[:200]
        return f"BĐS {district} - {city}"[:200]
    if district:
        return f"BĐS {district}"[:200]
    if city:
        return f"BĐS {city}"[:200]

    location = str(data.get("location") or data.get("address") or "").strip()
    if location:
        if " - " in location:
            parts = [p.strip() for p in location.split("-") if p.strip()]
            if len(parts) >= 2:
                return f"BĐS {parts[-2]} - {parts[-1]}"[:200]
            if parts:
                return f"BĐS {parts[0]}"[:200]
            return "Bất động sản"
        if "," in location:
            from app.proprietary.platforms.batdongsan.parsers import _split_address

            d, c = _split_address(location)
            if d and c:
                if d.lower() == c.lower():
                    return f"BĐS {d}"[:200]
                return f"BĐS {d} - {c}"[:200]
            if d:
                return f"BĐS {d}"[:200]
            if c:
                return f"BĐS {c}"[:200]
            parts = [p.strip() for p in location.split(",") if p.strip()]
            if len(parts) >= 2:
                return f"BĐS {parts[-2]} - {parts[-1]}"[:200]
            if parts:
                return f"BĐS {parts[0]}"[:200]
            return "Bất động sản"
        return f"BĐS {location}"[:200]

    return "Bất động sản"


class BatdongsanLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Batdongsan.com.vn and Muaban.net real estate listings."""

    source_name = "batdongsan"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN", "SG", "DN", "BD", "DNA", "HP", "VT", "KH", "LD", "*"]
    coverage_quality_by_location = {
        "HN": "high",
        "SG": "high",
        "DN": "high",
        "BD": "high",
        "DNA": "medium",
        "HP": "medium",
        "VT": "medium",
        "KH": "medium",
        "LD": "medium",
    }

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
            max_items=min(limit, 20),
        )

        async def _local() -> dict[str, Any]:
            output = await scrape_batdongsan(input_model)
            return {
                "items": [item.to_output() for item in output.items],
                "degraded": output.degraded,
                "degradation_reason": output.degradation_reason,
            }

        raw = await medirus_scrape_or_local(
            platform="batdongsan",
            action="search_listings",
            args={
                "city": city,
                "listing_type": listing_type,
                "min_price": min_price,
                "max_price": max_price,
                "max_items": min(limit, 20),
            },
            local_fn=_local,
        )

        if raw.get("degraded"):
            logger.warning(
                "Batdongsan scraper degraded: %s", raw.get("degradation_reason")
            )
            self.last_execution_status = "degraded"

        results = []
        for data in raw.get("items", []) or []:
            detail_url = data.get("detail_url") or data.get("url")
            if not detail_url and data.get("listing_id"):
                from app.proprietary.platforms.batdongsan.parsers import (
                    build_detail_url,
                )

                detail_url = build_detail_url(
                    data.get("listing_id"),
                    data.get("title"),
                    city,
                    listing_type=listing_type,
                )

            results.append(
                {
                    "id": data.get("listing_id") or detail_url,
                    "listing_id": data.get("listing_id"),
                    "title": data.get("title"),
                    "price_vnd": data.get("price") or data.get("price_vnd"),
                    "location": data.get("location"),
                    "city": data.get("city") or city,
                    "district": data.get("district"),
                    "project_name": data.get("project_name"),
                    "contact_phone": data.get("phone"),
                    "description": data.get("description") or "",
                    "url": detail_url,
                    "detail_url": detail_url,
                    "industry": "Bất động sản",
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
            except Exception as exc:  # lead intelligence operation fallback
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

        # Ensure raw_data carries industry and source_url
        data["industry"] = data.get("industry") or "Bất động sản"
        source_url = data.get("url") or data.get("detail_url") or data.get("source_url")
        if source_url:
            data["source_url"] = source_url

        company_name = _derive_bds_company_name(data)
        canonical_domain = _extract_domain(source_url) or "batdongsan.com.vn"

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title") or "Bất động sản rao bán",
            company_name=company_name,
            canonical_domain=canonical_domain,
            primary_phone=primary_phone,
            contact_name=data.get("contact_name") or data.get("author"),
            price=_to_float(data.get("price_vnd") or data.get("price")) or None,
            city=data.get("city") or data.get("location"),
            address=data.get("address") or data.get("location"),
            source_url=source_url,
            confidence_score=85.0 if primary_phone else 65.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract verified phone numbers from raw listing metadata, title, and description."""
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

        # 2. Extract from title text
        title = data.get("title") or ""
        if title:
            for phone in extract_phones_from_text(title):
                if phone not in seen_phones:
                    seen_phones.add(phone)
                    candidates.append(
                        ContactCandidate(
                            channel="phone",
                            value=phone,
                            confidence=0.90,
                            metadata={"source_field": "title"},
                        )
                    )
            from app.proprietary.platforms.batdongsan.parsers import (
                extract_phone_from_title,
            )

            title_phone = extract_phone_from_title(title)
            if title_phone:
                norm_p = normalize_vietnamese_phone(title_phone)
                if (
                    norm_p
                    and len(norm_p) in (10, 11)
                    and any(norm_p.startswith(pfx) for pfx in _VALID_VN_PREFIXES)
                    and norm_p not in seen_phones
                ):
                    seen_phones.add(norm_p)
                    candidates.append(
                        ContactCandidate(
                            channel="phone",
                            value=norm_p,
                            confidence=0.90,
                            metadata={"source_field": "title"},
                        )
                    )

        # 3. Extract from description text
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
