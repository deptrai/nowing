"""Telegram LeadSourceAdapter implementation (Story 22.3 / AC-4 / AD-44).

Converts scraped Telegram messages and extracted Vietnamese entities into standard
NormalizedLead records and extracts ContactCandidates for the Split-View Table Matrix.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor

logger = logging.getLogger(__name__)


class TelegramLeadAdapter(LeadSourceAdapter):
    """Universal lead adapter for Telegram channels and discussion groups."""

    source_name: str = "telegram"
    category: LeadSourceCategory = LeadSourceCategory.SOCIAL

    async def _execute_search_query(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query database for stored telegram messages."""
        return []

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[Any]:
        """Search scraped Telegram posts and return normalized leads."""
        records = await self._execute_search_query(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            limit=limit,
        )
        if not records:
            logger.warning("Telegram search returned no live results")
            self.last_execution_status = "degraded"
            return []
        return [self.normalize_lead(r) for r in records]

    def normalize_lead(
        self, raw_record: RawLeadRecord | dict[str, Any]
    ) -> NormalizedLead:
        """Transform raw Telegram post and entities into standard NormalizedLead."""
        data = raw_record.data if isinstance(raw_record, RawLeadRecord) else raw_record
        rec_id = str(
            data.get("id")
            or (raw_record.source_id if isinstance(raw_record, RawLeadRecord) else "0")
        )

        text = data.get("message_text", "")
        entities = data.get("raw_entities")
        if isinstance(entities, str):
            try:
                entities = json.loads(entities)
            except Exception:
                entities = {}
        if not isinstance(entities, dict):
            entities = TelegramEntityExtractor.extract_entities(text)

        phones = entities.get("phones", [])
        prices = entities.get("prices", [])
        locations = entities.get("locations", [])
        emails = entities.get("emails", [])

        price_val: float | None = None
        if prices and isinstance(prices[0], dict):
            price_val = float(prices[0].get("amount_vnd") or 0.0)

        primary_phone = phones[0] if phones else None
        primary_email = emails[0] if emails else None
        city = locations[0] if locations else None

        title = text[:100] if text else "Telegram Post"

        metadata = {
            "channel_username": data.get("channel_username"),
            "channel_id": data.get("channel_id"),
            "message_id": data.get("message_id"),
            "views_count": data.get("views_count"),
            "forwards_count": data.get("forwards_count"),
            "posted_at": data.get("posted_at"),
        }

        contact_candidates = self.extract_contact_candidates(raw_record)

        # Store extra Telegram-specific context inside raw_data instead of
        # bypassing Pydantic validation with object.__setattr__.
        raw_data = dict(data)
        raw_data["telegram_metadata"] = metadata
        raw_data["phone_numbers"] = phones

        return NormalizedLead(
            source_name="telegram",
            source_id=rec_id,
            title=title,
            primary_phone=primary_phone,
            primary_email=primary_email,
            city=city,
            price=price_val,
            contact_candidates=contact_candidates,
            raw_data=raw_data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord | dict[str, Any]
    ) -> list[ContactCandidate]:
        """Extract ContactCandidate instances from phones and emails in message."""
        data = raw_record.data if isinstance(raw_record, RawLeadRecord) else raw_record
        text = data.get("message_text", "")
        entities = data.get("raw_entities")
        if isinstance(entities, str):
            try:
                entities = json.loads(entities)
            except Exception:
                entities = {}
        if not isinstance(entities, dict):
            entities = TelegramEntityExtractor.extract_entities(text)

        candidates: list[ContactCandidate] = []
        for phone in entities.get("phones", []):
            candidates.append(
                ContactCandidate(
                    channel="phone",
                    value=phone,
                    confidence=0.95,
                    metadata={"contact_type": "phone", "source": "telegram"},
                )
            )

        for email in entities.get("emails", []):
            candidates.append(
                ContactCandidate(
                    channel="email",
                    value=email,
                    confidence=0.90,
                    metadata={"contact_type": "email", "source": "telegram"},
                )
            )

        return candidates
