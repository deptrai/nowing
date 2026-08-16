"""Unit tests for TelegramLeadAdapter (Story 22.3 / AC-4).

Validates that TelegramLeadAdapter implements LeadSourceAdapter ABC (AD-44),
normalizes raw Telegram messages into standard NormalizedLead records, and extracts ContactCandidates.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-4: TelegramLeadAdapter Contract & Normalization Tests
# ---------------------------------------------------------------------------


class TestTelegramLeadAdapterInterface:
    """Validate that TelegramLeadAdapter satisfies LeadSourceAdapter ABC."""

    def test_implements_lead_source_adapter_abc(self) -> None:
        """TelegramLeadAdapter must subclass LeadSourceAdapter without TypeError."""
        from app.lead_intelligence.adapters.base import LeadSourceAdapter
        from app.proprietary.platforms.telegram.lead_adapter import TelegramLeadAdapter

        adapter = TelegramLeadAdapter()
        assert isinstance(adapter, LeadSourceAdapter)
        assert adapter.source_name == "telegram"

    def test_registered_in_lead_source_registry(self) -> None:
        """TelegramLeadAdapter must be discoverable in LeadSourceAdapterRegistry."""
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

        registry = LeadSourceAdapterRegistry.get_instance()
        adapter = registry.get_adapter("telegram")
        assert adapter is not None
        assert adapter.source_name == "telegram"


class TestTelegramLeadAdapterNormalization:
    """Validate normalization of raw Telegram message records into NormalizedLead."""

    @pytest.fixture
    def sample_raw_telegram_record(self) -> dict[str, Any]:
        return {
            "id": 101,
            "channel_id": 999,
            "channel_username": "bds_hanoi_chinhchu",
            "message_id": 4567,
            "message_text": "Bán gấp nhà Cầu Giấy 55m2 x 5 tầng, giá 12.5 tỷ. LH chính chủ: 0912.345.678",
            "raw_entities": {
                "phones": ["0912345678"],
                "prices": [
                    {"raw_text": "12.5 tỷ", "amount_vnd": 12_500_000_000, "unit": "tỷ"}
                ],
                "locations": ["Cầu Giấy, Hà Nội"],
                "emails": [],
            },
            "views_count": 1240,
            "forwards_count": 14,
            "posted_at": "2026-08-15T14:30:00Z",
        }

    def test_normalize_lead_populates_required_fields(
        self, sample_raw_telegram_record: dict[str, Any]
    ) -> None:
        """normalize_lead must map telegram message attributes and entities to NormalizedLead."""
        from app.proprietary.platforms.telegram.lead_adapter import TelegramLeadAdapter

        adapter = TelegramLeadAdapter()
        normalized = adapter.normalize_lead(sample_raw_telegram_record)

        assert normalized.source == "telegram"
        assert normalized.source_record_id == "101"
        assert (
            normalized.title
            == "Bán gấp nhà Cầu Giấy 55m2 x 5 tầng, giá 12.5 tỷ. LH chính chủ: 0912.345.678"[
                :100
            ]
        )
        assert normalized.price_vnd == 12_500_000_000
        assert "0912345678" in normalized.phone_numbers
        assert normalized.metadata.get("channel_username") == "bds_hanoi_chinhchu"
        assert normalized.metadata.get("views_count") == 1240

    def test_extract_contact_candidates(
        self, sample_raw_telegram_record: dict[str, Any]
    ) -> None:
        """extract_contact_candidates must yield ContactCandidate records for extracted phones."""
        from app.proprietary.platforms.telegram.lead_adapter import TelegramLeadAdapter

        adapter = TelegramLeadAdapter()
        candidates = adapter.extract_contact_candidates(sample_raw_telegram_record)

        assert len(candidates) >= 1
        phone_candidate = candidates[0]
        assert phone_candidate.contact_type == "phone"
        assert phone_candidate.value == "0912345678"
        assert phone_candidate.source == "telegram"


class TestTelegramLeadAdapterSearch:
    """Validate async lead search over stored telegram_messages."""

    @pytest.mark.asyncio
    async def test_search_leads_queries_database(self) -> None:
        """search_leads must query telegram_messages with workspace and keyword filters."""
        from app.proprietary.platforms.telegram.lead_adapter import TelegramLeadAdapter

        adapter = TelegramLeadAdapter()
        with patch.object(
            adapter, "_execute_search_query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = [
                {
                    "id": 1,
                    "message_text": "Bán nhà Cầu Giấy 10 tỷ",
                    "raw_entities": {"phones": ["0912345678"], "prices": []},
                    "channel_username": "bds_hanoi",
                }
            ]
            results = await adapter.search_leads(
                workspace_id=1,
                query="Cầu Giấy",
                filters={"min_price": 5_000_000_000},
                limit=10,
            )

            assert len(results) == 1
            assert results[0].source == "telegram"
            mock_query.assert_awaited_once()
