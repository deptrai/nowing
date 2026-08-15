"""Masothue and Public Procurement Universal Scraper Adapter (Story 21.15)."""

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


class EnterpriseProcurementLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Masothue enterprise directory and Cổng Mua Sắm Công procurement."""

    source_name = "enterprise"
    category = LeadSourceCategory.ENTERPRISE

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _fetch_enterprise_records(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call underlying Masothue / Mua Sắm Công platform routines."""
        try:
            from app.proprietary.platforms.masothue.schemas import MasothueSearchInput
            from app.proprietary.platforms.masothue.scraper import scrape_masothue

            inp = MasothueSearchInput(keyword=query, max_items=min(limit, 20))
            output = await scrape_masothue(inp)
            results = []
            for comp in output.companies:
                results.append({
                    "id": comp.tax_code,
                    "tax_code": comp.tax_code,
                    "company_name": comp.company_name,
                    "representative": comp.representative,
                    "phone": comp.phone,
                    "address": comp.address,
                    "industry": comp.industry_name,
                    "status": comp.status,
                })
            return results
        except Exception as exc:
            logger.warning("Live Masothue scrape error: %s", exc)
            return []

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search enterprise and procurement bidding packages with retry."""
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._fetch_enterprise_records(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                self.last_execution_status = "ok"
                return [
                    RawLeadRecord(
                        source_name=self.source_name,
                        source_id=str(
                            item.get("tax_id") or item.get("id") or f"ent_{idx}"
                        ),
                        data=item,
                        category=self.category,
                    )
                    for idx, item in enumerate(items)
                ]
            except Exception as exc:
                last_exc = exc
                logger.warning("Enterprise search attempt %d failed: %s", attempt, exc)

        logger.error(
            "Enterprise scraper failed after %d attempts: %s", attempt, last_exc
        )
        self.last_execution_status = "degraded"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize enterprise record to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )
        primary_email = next(
            (c.value for c in candidates if c.channel == "email"), None
        )

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("procurement_bid")
            or data.get("company_name")
            or "Doanh nghiệp",
            company_name=data.get("company_name") or "Doanh nghiệp đăng ký",
            tax_id=data.get("tax_id"),
            legal_rep=data.get("legal_representative") or data.get("representative"),
            contact_name=data.get("legal_representative") or data.get("contact_name"),
            primary_phone=primary_phone or data.get("phone"),
            primary_email=primary_email or data.get("email"),
            address=data.get("address") or data.get("headquarters"),
            city=data.get("city") or data.get("province"),
            price=float(data.get("bid_value_vnd") or 0.0) or None,
            confidence_score=90.0 if data.get("tax_id") else 75.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone and email contact candidates."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []

        direct_phone = data.get("phone") or data.get("hotline")
        if direct_phone:
            norm = normalize_vietnamese_phone(str(direct_phone))
            if norm:
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=norm,
                        confidence=0.95,
                        metadata={"source_field": "phone"},
                    )
                )

        email = data.get("email")
        if email and "@" in str(email):
            candidates.append(
                ContactCandidate(
                    channel="email",
                    value=str(email).strip().lower(),
                    confidence=0.95,
                    metadata={"source_field": "email"},
                )
            )

        for phone in extract_phones_from_text(data.get("description") or ""):
            candidates.append(
                ContactCandidate(
                    channel="phone",
                    value=phone,
                    confidence=0.80,
                    metadata={"source_field": "description"},
                )
            )

        return candidates
