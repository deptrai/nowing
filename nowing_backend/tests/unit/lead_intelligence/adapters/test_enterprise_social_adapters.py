"""Unit tests for Enterprise procurement and Social lead source adapters (Story 21.15 / Story 21.20)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.adapters.enterprise import (
    EnterpriseProcurementLeadAdapter,
)
from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
from app.lead_intelligence.adapters.social import SocialLeadAdapter

pytestmark = pytest.mark.unit


class TestEnterpriseProcurementLeadAdapter:
    """Validate Masothue enterprise adapter."""

    @pytest.mark.asyncio
    async def test_enterprise_search_and_procurement_bids(self) -> None:
        """Should fetch company tax registration and public bidding packages."""
        adapter = EnterpriseProcurementLeadAdapter()
        mock_enterprise = [
            {
                "tax_id": "0101234567",
                "company_name": "Công Ty Cổ Phần Công Nghệ ABC",
                "legal_representative": "Phạm Văn D",
                "address": "Tòa nhà Keangnam, Mễ Trì, Nam Từ Liêm, Hà Nội",
                "phone": "02431234567",
                "procurement_bid": "Gói thầu số 05: Cung cấp phần mềm quản lý",
                "bid_value_vnd": 500000000,
            }
        ]

        with patch.object(
            adapter,
            "_fetch_enterprise_records",
            AsyncMock(return_value=mock_enterprise),
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="gói thầu phần mềm CNTT Hà Nội",
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.tax_id == "0101234567"
            assert normalized.company_name == "Công Ty Cổ Phần Công Nghệ ABC"
            assert normalized.legal_rep == "Phạm Văn D"


class TestSocialLeadAdapter:
    """Validate Facebook Groups & Twitter Posts adapter via XActions."""

    @pytest.mark.asyncio
    async def test_social_search_and_contact_extraction(self) -> None:
        """Should parse public group posts and extract contact signals."""
        adapter = SocialLeadAdapter()
        mock_posts = [
            {
                "platform": "facebook",
                "post_id": "fb_post_8899",
                "author_name": "Hoàng Minh E",
                "group_name": "Cộng Đồng Môi Giới BĐS Hà Nội",
                "post_text": "Cần tìm nguồn khách mua nhà phố Đống Đa > 10 tỷ. Call/Zalo: 0944556677.",
                "post_url": "https://facebook.com/groups/bds/posts/8899",
            }
        ]

        with patch.object(
            adapter, "_search_social_feeds", AsyncMock(return_value=mock_posts)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="mua nhà phố Đống Đa",
                limit=10,
            )
            assert len(raw_records) == 1
            candidates = adapter.extract_contact_candidates(raw_records[0])
            phones = [c.value for c in candidates if c.channel == "phone"]
            assert "0944556677" in phones

            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.primary_phone == "0944556677"


class TestMuaSamCongLeadAdapter:
    """Validate Mua Sắm Công public procurement lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should call Muasamcong scraper and normalize to procuring-entity leads."""
        adapter = MuaSamCongLeadAdapter()
        mock_items = [
            {
                "bid_no": "IB2400123456",
                "project_name": "Cung cấp phần mềm CRM",
                "procuring_entity": "Công ty CP ABC",
                "investor": "Tập đoàn XYZ",
                "bid_price": 500000000,
                "location": "Hà Nội",
                "dossier_url": "https://muasamcong.mpi.gov.vn/123",
            }
        ]

        with patch.object(
            adapter, "_search_public_tenders", AsyncMock(return_value=mock_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="gói thầu phần mềm CRM",
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.company_name == "Công ty CP ABC"
            assert normalized.source_name == "muasamcong"
