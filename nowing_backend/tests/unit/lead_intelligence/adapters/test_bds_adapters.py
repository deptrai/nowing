"""Unit tests for Real Estate (BĐS) lead source adapters: Batdongsan, Chotot, Muaban BĐS (Story 21.15 / Story 21.20)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead, RawLeadRecord
from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter

pytestmark = pytest.mark.unit


class TestBatdongsanLeadAdapter:
    """Validate Batdongsan.com.vn adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should fetch raw property listings and normalize to standard Lead record."""
        adapter = BatdongsanLeadAdapter()
        mock_raw_items = [
            {
                "id": "bds_12345",
                "title": "Bán biệt thự Vinhomes Ocean Park Gia Lâm 150m2",
                "price_string": "15 tỷ",
                "price_vnd": 15000000000,
                "location": "Gia Lâm, Hà Nội",
                "contact_name": "Nguyễn Văn A",
                "contact_phone_masked": "0912***456",
                "contact_phone_unmasked": "0912345456",
                "url": "https://batdongsan.com.vn/ban-nha-biet-thu-du-an-vinhomes-ocean-park-pr12345",
            }
        ]

        with patch.object(
            adapter, "_fetch_raw_listings", AsyncMock(return_value=mock_raw_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="biệt thự Vinhomes Ocean Park",
                filters={"location": "Hà Nội"},
                limit=10,
            )
            assert len(raw_records) == 1

            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.title == "Bán biệt thự Vinhomes Ocean Park Gia Lâm 150m2"
            assert normalized.source_name == "batdongsan"
            assert normalized.primary_phone == "0912345456"
            assert normalized.contact_name == "Nguyễn Văn A"
            assert normalized.price == 15000000000

    def test_extract_contact_candidates(self) -> None:
        """Should extract valid phone candidate from raw listing."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds_123",
            data={
                "contact_phone": "0987654321",
                "contact_name": "Trần Thị B",
                "description": "Liên hệ chính chủ 0901234567 để xem nhà.",
            },
        )
        candidates = adapter.extract_contact_candidates(raw)
        phones = [c.value for c in candidates if c.channel == "phone"]
        assert "0987654321" in phones
        assert "0901234567" in phones

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_cloudflare_or_429(self) -> None:
        """Should retry at most once, and return degraded status without crashing."""
        adapter = BatdongsanLeadAdapter()

        with patch.object(
            adapter,
            "_fetch_raw_listings",
            AsyncMock(side_effect=RuntimeError("Cloudflare 403 Challenge")),
        ) as mock_fetch:
            records = await adapter.search_leads(
                workspace_id=1,
                query="chung cư Cầu Giấy",
                limit=10,
            )
            # Max 1 retry (initial + 1 retry = 2 calls)
            assert mock_fetch.call_count <= 2
            # Should return empty list gracefully
            assert records == []
            assert adapter.last_execution_status == "degraded"


class TestChototLeadAdapter:
    """Validate Chợ Tốt multi-category lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should query Chotot API and normalize lead records."""
        adapter = ChototLeadAdapter()
        mock_items = [
            {
                "list_id": 998877,
                "subject": "Cho thuê mặt bằng kinh doanh Quận 1",
                "price": 25000000,
                "region_name": "Tp Hồ Chí Minh",
                "account_name": "Lê Văn C",
                "phone": "0933112233",
            }
        ]

        with patch.object(
            adapter, "_query_chotot_api", AsyncMock(return_value=mock_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="mặt bằng kinh doanh Quận 1",
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.title == "Cho thuê mặt bằng kinh doanh Quận 1"
            assert normalized.primary_phone == "0933112233"


class TestMuabanBdsLeadAdapter:
    """Validate Muaban.net BĐS lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should query Muaban.net BĐS scraper and normalize to standard Lead record."""
        adapter = MuabanBdsLeadAdapter()
        mock_items = [
            {
                "listing_id": 123,
                "title": "Bán nhà phố Quận 7",
                "price_value": 6500000000,
                "location": "Quận 7, TP.HCM",
                "city": "TP.HCM",
                "phone": "0909123456",
                "detail_url": "https://muaban.net/bds/123",
            }
        ]

        with patch.object(
            adapter, "_query_muaban_bds_api", AsyncMock(return_value=mock_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="nhà phố Quận 7",
                filters={"locations": ["TP.HCM"]},
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.title == "Bán nhà phố Quận 7"
            assert normalized.primary_phone == "0909123456"
            assert normalized.price == 6500000000
            assert normalized.source_name == "muaban_bds"

    @pytest.mark.asyncio
    async def test_muaban_bds_recovers_from_degraded(self) -> None:
        """A second successful search_leads call must clear a previous degraded latch."""
        adapter = MuabanBdsLeadAdapter()
        adapter.last_execution_status = "degraded"

        with patch.object(
            adapter,
            "_query_muaban_bds_api",
            AsyncMock(return_value=[{"listing_id": 1, "title": "Test"}]),
        ):
            records = await adapter.search_leads(
                workspace_id=1, query="nhà phố", limit=10
            )
            assert records
            assert adapter.last_execution_status == "ok"
