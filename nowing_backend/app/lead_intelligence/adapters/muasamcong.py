"""Mua Sắm Công (muasamcong.mpi.gov.vn) public procurement lead adapter (Story 21.20)."""

from __future__ import annotations

import logging
from typing import Any

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
from app.proprietary.platforms.muasamcong.scraper import MuasamcongScraper

logger = logging.getLogger(__name__)


class MuaSamCongLeadAdapter(LeadSourceAdapter):
    """Adapter that surfaces procuring-entity / investor leads from public tenders."""

    source_name = "muasamcong"
    category = LeadSourceCategory.ENTERPRISE

    def __init__(self) -> None:
        self.last_execution_status = "ok"
        # ponytail: reuse one scraper instance so the token-bucket rate limiter
        # enforces the e-GP 15 req/min global cap across repeated calls.
        self._scraper = MuasamcongScraper()

    async def _search_public_tenders(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call the Muasamcong e-GP v2.0 REST scraper."""
        min_price, max_price = extract_price_range(query)
        location = resolve_chotot_city(query, filters, default=None)

        result = await self._scraper.search_tenders(
            keyword=query,
            min_price=float(min_price) if min_price is not None else None,
            max_price=float(max_price) if max_price is not None else None,
            location=location,
            size=min(limit, 20),
        )

        if result.degraded:
            logger.warning(
                "Muasamcong scraper degraded: %s", result.degradation_reason
            )
            self.last_execution_status = "degraded"

        return [item.model_dump() for item in result.items]

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search public procurement tenders with graceful degradation."""
        self.last_execution_status = "ok"
        try:
            items = await self._search_public_tenders(
                workspace_id=workspace_id, query=query, filters=filters, limit=limit
            )
            if self.last_execution_status != "degraded":
                self.last_execution_status = "ok"
            return [
                RawLeadRecord(
                    source_name=self.source_name,
                    source_id=str(
                        item.get("bid_no") or item.get("project_name") or f"muasamcong_{idx}"
                    ),
                    data=item,
                    category=self.category,
                )
                for idx, item in enumerate(items)
            ]
        except Exception as exc:
            logger.error("Muasamcong search failed: %s", exc)
            self.last_execution_status = "degraded"
            return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize a tender item to a procuring-entity lead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )

        company = (
            data.get("procuring_entity")
            or data.get("investor")
            or data.get("project_name")
            or "Chủ đầu tư / Bên mời thầu"
        )

        price = _to_float(data.get("bid_price"))

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("project_name") or "Gói thầu công",
            company_name=company,
            primary_phone=primary_phone,
            price=price,
            city=data.get("location"),
            address=data.get("location"),
            source_url=data.get("dossier_url"),
            confidence_score=75.0 if primary_phone else 60.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def _collect_text_parts(self, data: dict[str, Any]) -> list[str]:
        """Flatten tender fields, recursively walking ``raw_specs`` dicts/lists."""
        parts: list[str] = []
        for key in ("raw_specs", "project_name", "procuring_entity", "investor"):
            value = data.get(key)
            if isinstance(value, dict):
                for v in value.values():
                    if v:
                        parts.append(str(v))
            elif isinstance(value, list):
                for v in value:
                    if v:
                        parts.append(str(v))
            elif value:
                parts.append(str(value))
        return parts

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone candidates from tender spec text."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        text = " ".join(self._collect_text_parts(data))
        for phone in extract_phones_from_text(text):
            if phone not in seen_phones:
                seen_phones.add(phone)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=phone,
                        confidence=0.80,
                        metadata={"source_field": "raw_specs"},
                    )
                )

        return candidates
