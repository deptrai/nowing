"""Facebook Groups and Twitter Posts Universal Scraper Adapter (Story 21.15)."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    extract_phones_from_text,
)

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


class SocialLeadAdapter(LeadSourceAdapter):
    """Adapter bridging Facebook Groups and Twitter feed via XActions."""

    source_name = "social"
    category = LeadSourceCategory.SOCIAL

    def __init__(self) -> None:
        self.last_execution_status = "ok"

    async def _search_social_feeds(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Call underlying XActions / Facebook / Twitter routines."""
        return []

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search public social group posts with anti-loop retry and degradation."""
        retries = 1
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= retries:
            try:
                attempt += 1
                items = await self._search_social_feeds(
                    workspace_id=workspace_id, query=query, filters=filters, limit=limit
                )
                if not items:
                    logger.warning("Social feed search returned no live results")
                    self.last_execution_status = "degraded"
                    return []
                self.last_execution_status = "ok"
                return [
                    RawLeadRecord(
                        source_name=self.source_name,
                        source_id=str(
                            item.get("post_id") or item.get("id") or f"soc_{idx}"
                        ),
                        data=item,
                        category=self.category,
                    )
                    for idx, item in enumerate(items)
                ]
            except Exception as exc:
                last_exc = exc
                logger.warning("Social feed search attempt %d failed: %s", attempt, exc)

        logger.error("Social scraper failed after %d attempts: %s", attempt, last_exc)
        self.last_execution_status = "degraded"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Standardize social post to NormalizedLead."""
        data = raw_record.data
        candidates = self.extract_contact_candidates(raw_record)
        primary_phone = next(
            (c.value for c in candidates if c.channel == "phone"), None
        )
        primary_email = next(
            (c.value for c in candidates if c.channel == "email"), None
        )

        post_text = data.get("post_text") or data.get("content") or ""
        title = (post_text[:120] + "...") if len(post_text) > 120 else post_text

        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=title or "Bài đăng mạng xã hội",
            contact_name=data.get("author_name") or data.get("author"),
            company_name=data.get("group_name") or data.get("page_name"),
            primary_phone=primary_phone,
            primary_email=primary_email,
            city=data.get("city") or data.get("location"),
            address=data.get("address"),
            price=data.get("price_value"),
            confidence_score=75.0 if primary_phone else 55.0,
            sources=[self.source_name],
            contact_candidates=candidates,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone and email signals embedded in post descriptions."""
        data = raw_record.data
        candidates: list[ContactCandidate] = []
        seen_phones: set[str] = set()

        text = data.get("post_text") or data.get("text") or data.get("content") or ""

        # Phones
        for phone in extract_phones_from_text(text):
            if phone not in seen_phones:
                seen_phones.add(phone)
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=phone,
                        confidence=0.85,
                        metadata={"source_field": "post_text"},
                    )
                )

        # Emails
        for email_match in _EMAIL_PATTERN.findall(text):
            candidates.append(
                ContactCandidate(
                    channel="email",
                    value=email_match.strip().lower(),
                    confidence=0.90,
                    metadata={"source_field": "post_text"},
                )
            )

        return candidates
