"""Unit tests for LeadSourceAdapter ABC, phone normalization, ReDoS safety, and contact extraction (Story 21.15 / Story 21.20)."""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    RawLeadRecord,
    extract_emails_from_text,
    extract_phones_from_text,
    extract_social_ids_from_text,
    normalize_vietnamese_phone,
)
from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter

pytestmark = pytest.mark.unit


class TestLeadSourceAdapterABC:
    """Validate that LeadSourceAdapter enforces the required abstract interface."""

    def test_cannot_instantiate_abstract_base_class(self) -> None:
        """Should raise TypeError when attempting to instantiate LeadSourceAdapter directly."""
        with pytest.raises(TypeError):
            LeadSourceAdapter()  # type: ignore[abstract]

    def test_subclass_must_implement_all_three_abstract_methods(self) -> None:
        """Subclass missing search_leads, normalize_lead, or extract_contact_candidates cannot be instantiated."""
        class IncompleteAdapter(LeadSourceAdapter):
            async def search_leads(
                self,
                workspace_id: int,
                query: str,
                filters: dict[str, Any] | None = None,
                limit: int = 50,
            ) -> list[Any]:
                return []

            # missing normalize_lead and extract_contact_candidates

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore[abstract]


class TestPhoneNormalizationAndReDoSSafety:
    """Ensure regex parsing is robust, ReDoS-safe, and standardizes Vietnamese phone numbers."""

    def test_phone_prefix_normalization(self) -> None:
        """Should normalize +84, 84, 0 prefixes into standard 10-digit format."""
        assert normalize_vietnamese_phone("+84912345678") == "0912345678"
        assert normalize_vietnamese_phone("84912345678") == "0912345678"
        assert normalize_vietnamese_phone("0912.345.678") == "0912345678"
        assert normalize_vietnamese_phone("0912 345 678") == "0912345678"
        assert normalize_vietnamese_phone("0912-345-678") == "0912345678"

    def test_phone_extraction_redos_safe_against_evil_strings(self) -> None:
        """Should extract phones in linear time without catastrophic backtracking."""
        evil_string = "0" * 5000 + "9" * 5000 + "abc!@#"
        start_time = time.perf_counter()
        phones = extract_phones_from_text(evil_string)
        duration = time.perf_counter() - start_time

        # Must execute in under 50ms
        assert duration < 0.05
        assert isinstance(phones, list)


class TestMultiChannelContactExtraction:
    """Contact extraction should surface phones, emails, and social handles."""

    def test_extract_emails_and_social_from_text(self) -> None:
        """Should extract emails and social IDs from BĐS description text."""
        text = (
            "Liên hệ chính chủ 0901234567 hoặc email owner@example.com. "
            "Zalo: 0901234567, facebook.com/seller.page"
        )
        assert extract_emails_from_text(text) == ["owner@example.com"]
        social = extract_social_ids_from_text(text)
        assert "zalo" in social
        assert "facebook" in social

    def test_batdongsan_extracts_email_and_zalo(self) -> None:
        """Batdongsan adapter should extract email and social candidates."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds_123",
            data={
                "title": "Bán nhà phố quận 7",
                "description": "Liên hệ a.example@domain.vn hoặc zalo 0909876543",
                "phone": "0901234567",
            },
        )
        candidates = adapter.extract_contact_candidates(raw)
        channels = {c.channel for c in candidates}
        assert "phone" in channels
        assert "email" in channels
        assert "zalo" in channels
