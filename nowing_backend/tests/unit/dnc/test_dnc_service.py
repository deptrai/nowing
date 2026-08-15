"""Unit tests for DncComplianceService (Story 21.14).

Tests in-stream compliance checking, Redis caching, batch lead filtering,
and tag application for blocked contacts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestDncComplianceService:
    """Test DncComplianceService core matching logic and in-stream filtering."""

    @pytest.mark.asyncio
    async def test_is_blocked_by_phone_number(self) -> None:
        """Should detect matching phone number in DNC registry via HMAC hash."""
        from app.lead_intelligence.dnc.normalizer import hash_phone_hmac
        from app.lead_intelligence.dnc.service import DncComplianceService

        service = DncComplianceService(secret_key="test-secret-123")
        expected_hash = hash_phone_hmac("+84908123456", "test-secret-123")

        with patch.object(
            service,
            "_get_workspace_dnc_phone_hashes",
            AsyncMock(return_value={expected_hash}),
        ):
            result = await service.is_blocked(
                workspace_id=1,
                phone="0908123456",
            )
            assert result.is_blocked is True
            assert result.record_type == "phone"

    @pytest.mark.asyncio
    async def test_is_blocked_by_wildcard_domain(self) -> None:
        """Should detect matching wildcard company domain (e.g. *.competitor.vn)."""
        from app.lead_intelligence.dnc.service import DncComplianceService

        service = DncComplianceService(secret_key="test-secret-123")

        with patch.object(
            service,
            "_get_workspace_dnc_domains",
            AsyncMock(return_value={"*.competitor.vn"}),
        ):
            result = await service.is_blocked(
                workspace_id=1,
                domain="sales.competitor.vn",
            )
            assert result.is_blocked is True
            assert result.record_type == "domain"

    @pytest.mark.asyncio
    async def test_batch_filter_leads_tags_blocked_leads(self) -> None:
        """Should tag matching leads as blocked_by_dnc and keep compliant leads unaffected."""
        from app.lead_intelligence.dnc.normalizer import hash_phone_hmac
        from app.lead_intelligence.dnc.service import DncComplianceService

        service = DncComplianceService(secret_key="test-secret-123")
        blocked_hash = hash_phone_hmac("+84908999888", "test-secret-123")

        leads = [
            {"id": "lead-1", "phone": "0908111222", "company": "Safe Co"},
            {"id": "lead-2", "phone": "0908999888", "company": "Blocked Co"},
        ]

        with patch.object(
            service,
            "_get_workspace_dnc_phone_hashes",
            AsyncMock(return_value={blocked_hash}),
        ):
            filtered = await service.batch_filter_leads(workspace_id=1, leads=leads)
            assert len(filtered) == 2

            assert filtered[0]["blocked_by_dnc"] is False
            assert filtered[0].get("dnc_reason") is None

            assert filtered[1]["blocked_by_dnc"] is True
            assert "DNC" in (filtered[1].get("dnc_reason") or "")
