"""Unit tests for Muasamcong e-GP v2.0 REST Scraper (Story 16.5 / AD-PROC-1, AD-PROC-4, AD-PROC-6)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.proprietary.platforms.muasamcong.scraper import (
    MuasamcongScraper,
    MuasamcongTokenBucket,
    ProcurementTenderItem,
    ScrapeResult,
)

pytestmark = pytest.mark.unit


_MOCK_SEARCH_RESPONSE_JSON = {
    "code": 200,
    "message": "success",
    "data": {
        "content": [
            {
                "bidNo": "IB2400123456",
                "bidTurnNo": "00",
                "bidName": "Gói thầu số 05: Xây lắp công trình Trụ sở làm việc",
                "procuringEntityName": "Ban Quản lý Dự án Đầu tư Xây dựng Công trình",
                "investorName": "Sở Kế hoạch và Đầu tư tỉnh Đồng Nai",
                "bidPrice": 45000000000.0,
                "bidField": "Xây lắp",
                "bidType": "Rộng rãi trong nước",
                "fundingSource": "Ngân sách Nhà nước",
                "bidOpenDate": "2026-08-20T09:00:00+07:00",
                "bidCloseDate": "2026-08-20T09:00:00+07:00",
                "location": "Tỉnh Đồng Nai",
                "documentUrls": [
                    "https://muasamcong.mpi.gov.vn/egp/api/v1/dossier/download?id=123456"
                ],
                "status": "OPEN",
            },
            {
                "bidNo": "IB2400987654",
                "bidTurnNo": "01",
                "bidName": "Mua sắm trang thiết bị CNTT phục vụ chuyển đổi số",
                "procuringEntityName": "Trung tâm Công nghệ Thông tin",
                "investorName": "Ủy ban Nhân dân Thành phố Hà Nội",
                "bidPrice": 12500000000.0,
                "bidField": "Mua sắm hàng hóa",
                "bidType": "Chào hàng cạnh tranh",
                "fundingSource": "Vốn đầu tư công",
                "bidOpenDate": "2026-08-16T10:00:00+07:00",
                "bidCloseDate": "2026-08-16T10:00:00+07:00",
                "location": "Thành phố Hà Nội",
                "documentUrls": [],
                "status": "OPEN",
            },
        ],
        "totalElements": 2,
        "totalPages": 1,
        "pageNumber": 0,
        "pageSize": 10,
    },
}

_MOCK_DETAIL_RESPONSE_JSON = {
    "code": 200,
    "message": "success",
    "data": {
        "bidNo": "IB2400123456",
        "bidTurnNo": "00",
        "bidName": "Gói thầu số 05: Xây lắp công trình Trụ sở làm việc",
        "procuringEntityName": "Ban Quản lý Dự án Đầu tư Xây dựng Công trình",
        "investorName": "Sở Kế hoạch và Đầu tư tỉnh Đồng Nai",
        "bidPrice": 45000000000.0,
        "bidField": "Xây lắp",
        "bidType": "Rộng rãi trong nước",
        "fundingSource": "Ngân sách Nhà nước",
        "bidOpenDate": "2026-08-20T09:00:00+07:00",
        "bidCloseDate": "2026-08-20T09:00:00+07:00",
        "location": "Tỉnh Đồng Nai",
        "documentUrls": [
            "https://muasamcong.mpi.gov.vn/egp/api/v1/dossier/download?id=123456"
        ],
        "rawSpecs": {
            "hinhThucChonNhaThau": "Đấu thầu rộng rãi trong nước qua mạng",
            "phuongThucChonNhaThau": "Một giai đoạn một túi hồ sơ",
            "thoiGianThucHienHopDong": "180 Ngày",
            "diaDiemPhatHanhHSMT": "Hệ thống Mạng Đấu thầu Quốc gia",
            "diaDiemNhanHSDT": "muasamcong.mpi.gov.vn",
            "baoDamDuThau": "675.000.000 VND",
        },
        "status": "OPEN",
    },
}


class TestMuasamcongTokenBucket:
    """AC-1 / AD-PROC-4: Token-Bucket Rate Limiter enforces <= 15 requests per minute."""

    @pytest.mark.asyncio
    async def test_token_bucket_initial_capacity(self):
        bucket = MuasamcongTokenBucket(rate=15.0, capacity=15.0)
        assert bucket.tokens == 15.0
        assert await bucket.acquire(1.0) is True
        assert bucket.tokens == 14.0

    @pytest.mark.asyncio
    async def test_token_bucket_rate_limiting_wait(self):
        # 1 token capacity, 10 tokens/sec for rapid test
        bucket = MuasamcongTokenBucket(rate=10.0, capacity=1.0)
        assert await bucket.acquire(1.0) is True
        assert bucket.tokens < 1.0

        # Wait for refill
        await asyncio.sleep(0.15)
        assert await bucket.acquire(1.0) is True


class TestMuasamcongScraper:
    """AC-1, AC-2 / AD-PROC-1, AD-PROC-6: e-GP v2.0 REST API scraper parsing & normalization."""

    @pytest.mark.asyncio
    async def test_search_tenders_success(self):
        scraper = MuasamcongScraper()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _MOCK_SEARCH_RESPONSE_JSON
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            result: ScrapeResult = await scraper.search_tenders(
                keyword="Xây lắp",
                field="Xây lắp",
                min_price=1000000000.0,
                max_price=50000000000.0,
                location="Đồng Nai",
                page=0,
                size=10,
            )

            assert result.total_elements == 2
            assert len(result.items) == 2
            assert result.degraded is False

            first_item = result.items[0]
            assert isinstance(first_item, ProcurementTenderItem)
            assert first_item.bid_no == "IB2400123456"
            assert first_item.bid_turn_no == "00"
            assert first_item.project_name == "Gói thầu số 05: Xây lắp công trình Trụ sở làm việc"
            assert first_item.procuring_entity == "Ban Quản lý Dự án Đầu tư Xây dựng Công trình"
            assert first_item.investor == "Sở Kế hoạch và Đầu tư tỉnh Đồng Nai"
            assert first_item.bid_price == 45000000000.0
            assert first_item.field == "Xây lắp"
            assert first_item.location == "Tỉnh Đồng Nai"
            assert first_item.status == "active"
            assert first_item.bid_closing_at is not None

    @pytest.mark.asyncio
    async def test_get_tender_detail_success(self):
        scraper = MuasamcongScraper()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _MOCK_DETAIL_RESPONSE_JSON
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            item = await scraper.get_tender_detail("IB2400123456", "00")
            assert item is not None
            assert item.bid_no == "IB2400123456"
            assert item.bid_turn_no == "00"
            assert item.raw_specs.get("baoDamDuThau") == "675.000.000 VND"
            assert item.dossier_url == "https://muasamcong.mpi.gov.vn/egp/api/v1/dossier/download?id=123456"

    @pytest.mark.asyncio
    async def test_search_tenders_http_error_degradation(self):
        scraper = MuasamcongScraper()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectTimeout("Connection to muasamcong.mpi.gov.vn timed out")

            result = await scraper.search_tenders(keyword="Test Timeout")
            assert result.degraded is True
            assert result.total_elements == 0
            assert "timed out" in (result.degradation_reason or "")

    @pytest.mark.asyncio
    async def test_search_tenders_61s_hang_is_terminated(self, monkeypatch):
        """A 61s HTTP hang must be terminated by the 60s timeout guard."""
        import respx

        from app.proprietary.platforms.muasamcong import scraper as scraper_module

        async def _hang(request):
            await asyncio.sleep(61)
            return httpx.Response(200, json=_MOCK_SEARCH_RESPONSE_JSON)

        with respx.mock:
            respx.post(
                "https://muasamcong.mpi.gov.vn/api/v1/tender/notice/search"
            ).mock(side_effect=_hang)

            scraper = MuasamcongScraper(timeout_seconds=0.1)
            start = asyncio.get_event_loop().time()
            result = await scraper.search_tenders(keyword="Test Hang")
            elapsed = asyncio.get_event_loop().time() - start

        assert result.degraded is True
        assert "time" in (result.degradation_reason or "").lower()
        assert elapsed < 2.0
