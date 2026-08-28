"""Red-phase unit tests for LeadSourceAdapter ABC, Registry, and 5 Scraper Adapters (Story 21.15)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Target module to be implemented in Story 21.15:
# from app.lead_intelligence.adapters.base import (
#     ContactCandidate,
#     LeadSourceAdapter,
#     LeadSourceCategory,
#     NormalizedLead,
#     RawLeadRecord,
# )
# from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
# from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
# from app.lead_intelligence.adapters.enterprise import EnterpriseProcurementLeadAdapter
# from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
# from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
# from app.lead_intelligence.adapters.social import SocialLeadAdapter

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. LeadSourceAdapter ABC Contract Tests (AC-1)
# ---------------------------------------------------------------------------
class TestLeadSourceAdapterABC:
    """Validate that LeadSourceAdapter enforces the required abstract interface."""

    def test_cannot_instantiate_abstract_base_class(self) -> None:
        """Should raise TypeError when attempting to instantiate LeadSourceAdapter directly."""
        from app.lead_intelligence.adapters.base import LeadSourceAdapter

        with pytest.raises(TypeError):
            LeadSourceAdapter()  # type: ignore[abstract]

    def test_subclass_must_implement_all_three_abstract_methods(self) -> None:
        """Subclass missing search_leads, normalize_lead, or extract_contact_candidates cannot be instantiated."""
        from app.lead_intelligence.adapters.base import LeadSourceAdapter

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


# ---------------------------------------------------------------------------
# 2. LeadSourceAdapterRegistry Tests (AC-2)
# ---------------------------------------------------------------------------
class TestLeadSourceAdapterRegistry:
    """Validate dynamic discovery, category indexing, and intent routing."""

    def test_registry_registration_and_retrieval(self) -> None:
        """Should register concrete adapters and retrieve them by source_name."""
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

        registry = LeadSourceAdapterRegistry()
        bds_adapter = BatdongsanLeadAdapter()
        chotot_adapter = ChototLeadAdapter()

        registry.register(bds_adapter)
        registry.register(chotot_adapter)

        assert registry.get("batdongsan") is bds_adapter
        assert registry.get("chotot") is chotot_adapter
        assert len(registry.list_all()) == 2

    def test_registry_filter_by_category(self) -> None:
        """Should filter registered adapters by LeadSourceCategory."""
        from app.lead_intelligence.adapters.base import LeadSourceCategory
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())

        real_estate_adapters = registry.find_by_category(LeadSourceCategory.REAL_ESTATE)
        assert len(real_estate_adapters) == 1
        assert real_estate_adapters[0].source_name == "batdongsan"

        job_adapters = registry.find_by_category(LeadSourceCategory.JOB_MARKET)
        assert len(job_adapters) == 1
        assert job_adapters[0].source_name == "job_market"

    def test_registry_resolve_adapters_for_intent(self) -> None:
        """Should route user intent keywords to relevant adapters."""
        from app.lead_intelligence.adapters.base import LeadSourceCategory
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
        from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
        from app.lead_intelligence.adapters.social import SocialLeadAdapter
        from app.lead_intelligence.adapters.telegram import TelegramLeadAdapter
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
        from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())
        registry.register(SocialLeadAdapter())
        registry.register(TelegramLeadAdapter())

        def names(matched: list[Any]) -> set[str]:
            return {a.source_name for a in matched}

        # Intent: Real estate & property — BĐS keywords
        bds_matched = registry.resolve_adapters_for_intent(
            "Tìm nhà đất chung cư biệt thự Hà Nội"
        )
        assert names(bds_matched) == {"batdongsan", "chotot", "muaban_bds"}
        for a in bds_matched:
            assert a.category == LeadSourceCategory.REAL_ESTATE

        # Intent: location + price with no BĐS keyword should default to REAL_ESTATE
        price_location_matched = registry.resolve_adapters_for_intent(
            "quận 7 TP.HCM giá dưới 8 tỷ"
        )
        assert names(price_location_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Intent: job recruitment (priority order may pick vn_jobs first)
        jobs_matched = registry.resolve_adapters_for_intent(
            "Tìm công ty IT đang tuyển dụng Golang Developer"
        )
        assert all(a.category == LeadSourceCategory.JOB_MARKET for a in jobs_matched)
        assert len(jobs_matched) == 1

        # Intent: procurement
        proc_matched = registry.resolve_adapters_for_intent("gói thầu xây dựng TP.HCM")
        assert names(proc_matched) == {"muasamcong"}

        # Intent: enterprise tax
        ent_matched = registry.resolve_adapters_for_intent("mã số thuế 0123456789")
        assert names(ent_matched) == {"enterprise"}

        # Intent: broker with BĐS keyword must not route to social
        broker_matched = registry.resolve_adapters_for_intent(
            "môi giới bất động sản quận 7"
        )
        assert names(broker_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Intent: broad query with no signal falls back to all adapters
        fallback_matched = registry.resolve_adapters_for_intent(
            "cho tôi thông tin"
        )
        assert len(fallback_matched) == 10

    def test_registry_resolve_adapters_for_intent_with_lead_intent(self) -> None:
        """Should route seller intent to social first, then BĐS fallback."""
        from app.lead_intelligence.adapters.base import LeadIntent
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
        from app.lead_intelligence.adapters.social import SocialLeadAdapter

        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(SocialLeadAdapter())

        def names(matched: list[Any]) -> set[str]:
            return {a.source_name for a in matched}

        # Seller intent should prefer social (buyer-demand) adapters.
        sell_matched = registry.resolve_adapters_for_intent(
            "Tôi cần bán 10 lô đất ký gửi quận 7",
            intent=LeadIntent.SELL,
        )
        assert "social" in names(sell_matched)

        # Buyer intent should still route to BĐS listings.
        buy_matched = registry.resolve_adapters_for_intent(
            "Tìm 10 nhà bán quận 7 TP.HCM giá dưới 8 tỷ",
            intent=LeadIntent.BUY,
        )
        assert names(buy_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Neutral / missing intent must remain backward-compatible.
        neutral_matched = registry.resolve_adapters_for_intent(
            "quận 7 TP.HCM giá dưới 8 tỷ"
        )
        assert names(neutral_matched) == {"batdongsan", "chotot", "muaban_bds"}

    def test_registry_raises_key_error_for_unknown_adapter(self) -> None:
        """Should raise KeyError when requesting non-existent adapter."""
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

        registry = LeadSourceAdapterRegistry()
        with pytest.raises(KeyError):
            registry.get("unknown_source")


# ---------------------------------------------------------------------------
# 3. BatdongsanLeadAdapter Tests (AC-2, AC-5)
# ---------------------------------------------------------------------------
class TestBatdongsanLeadAdapter:
    """Validate Batdongsan.com.vn & Muaban.net adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should fetch raw property listings and normalize to standard Lead record."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter

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
        from app.lead_intelligence.adapters.base import RawLeadRecord
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter

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
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter

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


# ---------------------------------------------------------------------------
# 4. ChototLeadAdapter Tests (AC-2)
# ---------------------------------------------------------------------------
class TestChototLeadAdapter:
    """Validate Chợ Tốt multi-category lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should query Chotot API and normalize lead records."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter

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


# ---------------------------------------------------------------------------
# 5. JobMarketLeadAdapter Tests (AC-2)
# ---------------------------------------------------------------------------
class TestJobMarketLeadAdapter:
    """Validate TopCV & ITviec recruitment postings adapter."""

    @pytest.mark.asyncio
    async def test_aggregates_topcv_and_itviec(self) -> None:
        """Should search recruitment portals and extract company hiring signals."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter

        adapter = JobMarketLeadAdapter()
        mock_topcv = [
            {
                "job_id": "topcv_1",
                "title": "Senior Python Backend Engineer",
                "company_name": "FPT Software",
                "salary": "2000 - 3000 USD",
                "company_website": "https://fpt-software.com",
                "hr_email": "recruitment@fpt.com",
                "hr_phone": "02473007575",
            }
        ]
        mock_itviec = [
            {
                "job_id": "itviec_2",
                "title": "AI/ML Tech Lead",
                "company_name": "VNG Corporation",
                "company_website": "https://vng.com.vn",
                "hr_email": "talent@vng.com.vn",
            }
        ]

        with (
            patch.object(adapter, "_search_topcv", AsyncMock(return_value=mock_topcv)),
            patch.object(
                adapter, "_search_itviec", AsyncMock(return_value=mock_itviec)
            ),
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="AI / Backend Engineer",
                limit=20,
            )
            assert len(raw_records) == 2

            normalized_0 = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized_0, NormalizedLead)
            assert normalized_0.company_name == "FPT Software"
            assert normalized_0.primary_email == "recruitment@fpt.com"
            assert normalized_0.canonical_domain == "fpt-software.com"


# ---------------------------------------------------------------------------
# 6. EnterpriseProcurementLeadAdapter Tests (AC-2)
# ---------------------------------------------------------------------------
class TestEnterpriseProcurementLeadAdapter:
    """Validate Masothue & Cổng Mua Sắm Công procurement adapter."""

    @pytest.mark.asyncio
    async def test_enterprise_search_and_procurement_bids(self) -> None:
        """Should fetch company tax registration and public bidding packages."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )

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


# ---------------------------------------------------------------------------
# 7. SocialLeadAdapter Tests (AC-2)
# ---------------------------------------------------------------------------
class TestSocialLeadAdapter:
    """Validate Facebook Groups & Twitter Posts adapter via XActions."""

    @pytest.mark.asyncio
    async def test_social_search_and_contact_extraction(self) -> None:
        """Should parse public group posts and extract contact signals."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.social import SocialLeadAdapter

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


# ---------------------------------------------------------------------------
# 8. ReDoS Safety & VN Phone Prefix Normalization Tests
# ---------------------------------------------------------------------------
class TestPhoneNormalizationAndReDoSSafety:
    """Ensure regex parsing is robust, ReDoS-safe, and standardizes Vietnamese phone numbers."""

    def test_phone_prefix_normalization(self) -> None:
        """Should normalize +84, 84, 0 prefixes into standard 10-digit format."""
        from app.lead_intelligence.adapters.base import normalize_vietnamese_phone

        assert normalize_vietnamese_phone("+84912345678") == "0912345678"
        assert normalize_vietnamese_phone("84912345678") == "0912345678"
        assert normalize_vietnamese_phone("0912.345.678") == "0912345678"
        assert normalize_vietnamese_phone("0912 345 678") == "0912345678"
        assert normalize_vietnamese_phone("0912-345-678") == "0912345678"

    def test_phone_extraction_redos_safe_against_evil_strings(self) -> None:
        """Should extract phones in linear time without catastrophic backtracking."""
        import time

        from app.lead_intelligence.adapters.base import extract_phones_from_text

        evil_string = "0" * 5000 + "9" * 5000 + "abc!@#"
        start_time = time.perf_counter()
        phones = extract_phones_from_text(evil_string)
        duration = time.perf_counter() - start_time

        # Must execute in under 50ms
        assert duration < 0.05
        assert isinstance(phones, list)


# ---------------------------------------------------------------------------
# 9. Story 21.20 New Adapters (Muaban BĐS, VnJobs, VietnamWorks, Mua Sắm Công)
# ---------------------------------------------------------------------------
class TestMuabanBdsLeadAdapter:
    """Validate Muaban.net BĐS lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should query Muaban.net BĐS scraper and normalize to standard Lead record."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter

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


class TestVnJobsLeadAdapter:
    """Validate VnJobs aggregate lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should aggregate job listings and normalize to company leads."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

        adapter = VnJobsLeadAdapter()
        mock_items = [
            {
                "id": "vnj_1",
                "title": "Senior Backend Engineer",
                "company": "FPT Software",
                "location": "Hà Nội",
                "source_urls": ["https://topcv.vn/job/1"],
                "salary": {"min": 20000000, "max": 30000000},
            }
        ]

        with patch.object(
            adapter, "_aggregate_job_listings", AsyncMock(return_value=mock_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="Senior Backend Engineer",
                filters={"locations": ["Hà Nội"]},
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.company_name == "FPT Software"
            assert normalized.canonical_domain == "topcv.vn"


class TestVietnamWorksLeadAdapter:
    """Validate VietnamWorks direct lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should call VietnamWorks scraper and normalize to company leads."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter

        adapter = VietnamWorksLeadAdapter()
        mock_items = [
            {
                "id": "vw:123",
                "title": "Data Scientist",
                "company": "VNG Corporation",
                "location": "TP.HCM",
                "source_url": "https://www.vietnamworks.com/data-scientist-123",
                "salary_min": 25000000,
                "salary_max": 40000000,
                "job_description": "Join VNG",
            }
        ]

        with patch.object(
            adapter, "_fetch_vietnamworks_jobs", AsyncMock(return_value=mock_items)
        ):
            raw_records = await adapter.search_leads(
                workspace_id=1,
                query="Data Scientist",
                limit=10,
            )
            assert len(raw_records) == 1
            normalized = adapter.normalize_lead(raw_records[0])
            assert isinstance(normalized, NormalizedLead)
            assert normalized.company_name == "VNG Corporation"
            assert normalized.source_name == "vietnamworks"

    def test_redact_job_text(self) -> None:
        """Should mask PII in job description text."""
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter

        adapter = VietnamWorksLeadAdapter()
        item = {
            "job_description": "Liên hệ anh Hùng 0912345678",
            "job_requirement": "",
        }
        redacted = adapter._redact_job_text(item)
        assert "0912345678" not in redacted["job_description"]


class TestMuaSamCongLeadAdapter:
    """Validate Mua Sắm Công public procurement lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should call Muasamcong scraper and normalize to procuring-entity leads."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter

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


class TestRegistryIntentRoutingStory2120:
    """Validate 21.20 source routing and deduplication."""

    def test_resolve_job_intent_deduplicates_to_vn_jobs(self) -> None:
        """Generic job query should route to VnJobs, not all job adapters."""
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
        from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
        from app.lead_intelligence.adapters.social import SocialLeadAdapter
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
        from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())
        registry.register(SocialLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "công ty AI tuyển dụng Senior Python tại Hà Nội"
        )
        names = {a.source_name for a in matched}
        assert "vn_jobs" in names
        assert "batdongsan" not in names
        assert "chotot" not in names
        assert "muaban_bds" not in names
        assert "muasamcong" not in names
        assert "enterprise" not in names
        assert "vietnamworks" not in names

    def test_resolve_explicit_vietnamworks(self) -> None:
        """Explicit VietnamWorks keyword should route to VietnamWorks adapter."""
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
        from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

        registry = LeadSourceAdapterRegistry()
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "tìm việc Python trên VietnamWorks"
        )
        names = {a.source_name for a in matched}
        assert "vietnamworks" in names
        assert "vn_jobs" not in names
        assert "job_market" not in names

    def test_resolve_procurement_intent_does_not_trigger_enterprise(self) -> None:
        """Procurement query should route to muasamcong, not the tax directory."""
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
        from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

        registry = LeadSourceAdapterRegistry()
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "gói thầu phần mềm CRM tại Hà Nội"
        )
        names = {a.source_name for a in matched}
        assert "muasamcong" in names
        assert "enterprise" not in names


class TestLeadSourceAdapterStateRecovery:
    """Adapter status should reset from degraded to ok on a successful subsequent call."""

    @pytest.mark.asyncio
    async def test_muaban_bds_recovers_from_degraded(self) -> None:
        """A second successful search_leads call must clear a previous degraded latch."""
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter

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


class TestMultiChannelContactExtraction:
    """Contact extraction should surface phones, emails, and social handles."""

    def test_extract_emails_and_social_from_text(self) -> None:
        """Should extract emails and social IDs from BĐS description text."""
        from app.lead_intelligence.adapters.base import (
            extract_emails_from_text,
            extract_social_ids_from_text,
        )

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
        from app.lead_intelligence.adapters.base import RawLeadRecord
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter

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


class TestLeadGenPostFilter:
    """LeadGenOrchestrator post-filter should drop price and location outliers."""

    def test_post_filter_drops_price_and_location_outliers(self) -> None:
        """Should drop leads with price above max or in wrong location."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            _post_filter_leads,
        )

        leads = [
            NormalizedLead(
                source_name="batdongsan",
                source_id="1",
                title="Nhà quận 7",
                price=7_000_000_000,
                city="Hồ Chí Minh",
            ),
            NormalizedLead(
                source_name="batdongsan",
                source_id="2",
                title="Nhà quận 7",
                price=9_000_000_000,
                city="Hồ Chí Minh",
            ),
            NormalizedLead(
                source_name="batdongsan",
                source_id="3",
                title="Nhà quận 7",
                price=6_000_000_000,
                city="Hà Nội",
            ),
        ]
        filtered = _post_filter_leads(
            leads,
            query="nhà quận 7 TP.HCM giá dưới 8 tỷ",
            filters={"locations": ["TP.HCM"]},
        )
        assert len(filtered) == 1
        assert filtered[0].source_id == "1"
