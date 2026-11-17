"""Unit tests for Lead Data Quality improvements (Batdongsan, Job Market, VietnamWorks, Pre-filter)."""

from __future__ import annotations

import pytest

from app.lead_intelligence.adapters.base import (
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
from app.lead_intelligence.campaign.schemas import ICPCriteria
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator

pytestmark = pytest.mark.unit


class TestBatdongsanLeadAdapterDataQuality:
    """Verify bugfixes for lead data quality in Batdongsan adapter."""

    def test_normalize_company_name_not_whole_title_fallback_location(self) -> None:
        """AC: Listing BĐS cá nhân không có project_name/agency_name -> location-derived company_name."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-101",
            data={
                "title": "Bán nhà 496 Xã Đàn; 40m2; 5 tầng kinh doanh đỉnh, giá 8.5 tỷ",
                "location": "Xã Đàn - Đống Đa",
                "city": "Hà Nội",
                "district": "Đống Đa",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert isinstance(lead, NormalizedLead)
        # company_name must NOT contain the whole ad title
        assert lead.company_name != raw.data["title"]
        assert "40m2" not in (lead.company_name or "")
        assert "8.5 tỷ" not in (lead.company_name or "")
        # Location-derived name
        assert lead.company_name == "BĐS Đống Đa - Hà Nội"

    def test_normalize_company_name_derived_from_location_field(self) -> None:
        """AC: When district/city not split, derive company_name from location."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-102",
            data={
                "title": "Bán nhà 496 Xã Đàn; 40m2",
                "location": "Xã Đàn - Đống Đa",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.company_name == "BĐS Xã Đàn - Đống Đa"

    def test_normalize_company_name_preserves_project_name(self) -> None:
        """AC: Listing có project_name -> giữ nguyên company_name."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-103",
            data={
                "title": "Bán liền kề Nam An Khánh",
                "project_name": "Vista Nam An Khánh",
                "district": "Hoài Đức",
                "city": "Hà Nội",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.company_name == "Vista Nam An Khánh"

    def test_normalize_extract_phone_from_title(self) -> None:
        """AC: Phone trong title được trích xuất và chuẩn hóa."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-104",
            data={
                "title": "LH 0973668873 Mr. Dương bán nhà đẹp",
                "description": "Nhà chính chủ sổ đỏ trao tay.",
            },
        )
        candidates = adapter.extract_contact_candidates(raw)
        phones = [c.value for c in candidates if c.channel == "phone"]
        assert "0973668873" in phones

        lead = adapter.normalize_lead(raw)
        assert lead.primary_phone == "0973668873"
        assert lead.confidence_score == 85.0

    def test_normalize_source_url_propagation(self) -> None:
        """AC: Listing có detail_url/url -> source_url được truyền đầy đủ."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-105",
            data={
                "title": "Bán nhà phố Hoàng Mai",
                "url": "https://batdongsan.com.vn/ban-nha-hoang-mai-pr12345",
                "detail_url": "https://batdongsan.com.vn/ban-nha-hoang-mai-pr12345",
                "city": "Hà Nội",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.source_url == "https://batdongsan.com.vn/ban-nha-hoang-mai-pr12345"
        assert lead.raw_data.get("source_url") == "https://batdongsan.com.vn/ban-nha-hoang-mai-pr12345"
        assert lead.canonical_domain == "batdongsan.com.vn"

    def test_normalize_industry_default_to_bat_dong_san(self) -> None:
        """AC: Bất kỳ listing BĐS nào cũng có raw_data['industry'] = 'Bất động sản'."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-106",
            data={
                "title": "Bán đất nền Hoà Lạc",
                "location": "Thạch Thất, Hà Nội",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.raw_data.get("industry") == "Bất động sản"

    @pytest.mark.asyncio
    async def test_fetch_raw_listings_synthesizes_detail_url(self) -> None:
        """When scrape_batdongsan returns listings with detail_url=None, _fetch_raw_listings builds it."""
        from unittest.mock import AsyncMock, patch

        from app.proprietary.platforms.batdongsan.schemas import (
            BatdongsanListing,
            BatdongsanScrapeOutput,
        )

        mock_item = BatdongsanListing(
            listing_id=999888,
            title="Bán chung cư Royal City 2PN",
            price="5 tỷ",
            location="Thanh Xuân, Hà Nội",
            city="HN",
            district="Thanh Xuân",
            detail_url=None,
        )
        mock_output = BatdongsanScrapeOutput(
            total_items=1,
            items=[mock_item],
            degraded=False,
        )

        adapter = BatdongsanLeadAdapter()
        with patch("app.proprietary.platforms.batdongsan.scraper.scrape_batdongsan", AsyncMock(return_value=mock_output)):
            records = await adapter.search_leads(workspace_id=1, query="Bán nhà Hà Nội")

        assert len(records) == 1
        assert records[0].data.get("detail_url") is not None
        assert "999888" in str(records[0].data.get("detail_url"))
        assert records[0].data.get("industry") == "Bất động sản"


class TestRecruitmentAdaptersDataQuality:
    """Verify bugfixes for job_market and vietnamworks adapters."""

    def test_job_market_industry_and_domain(self) -> None:
        """AC: Job market adapter sets industry and fallback domain."""
        adapter = JobMarketLeadAdapter()
        raw = RawLeadRecord(
            source_name="itviec",
            source_id="itv-101",
            data={
                "title": "Senior Python Backend Developer",
                "company": "KMS Technology",
                "location": "Hồ Chí Minh",
                "job_category": "Software Engineering",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.raw_data.get("industry") == "Software Engineering"
        assert lead.canonical_domain == "itviec.com"

        # Fallback industry when not specified
        raw_fallback = RawLeadRecord(
            source_name="topcv",
            source_id="topcv-102",
            data={
                "title": "Tuyển dụng kỹ sư AI",
                "company": "FPT Telecom",
                "location": "Hà Nội",
            },
        )
        lead_fb = adapter.normalize_lead(raw_fallback)
        assert lead_fb.raw_data.get("industry") == "Tuyển dụng IT"
        assert lead_fb.canonical_domain == "topcv.vn"

    def test_vietnamworks_industry_and_domain(self) -> None:
        """AC: VietnamWorks adapter sets industry and domain."""
        adapter = VietnamWorksLeadAdapter()
        raw = RawLeadRecord(
            source_name="vietnamworks",
            source_id="vnw-101",
            data={
                "title": "Trưởng phòng Kinh doanh B2B",
                "company": "Tập đoàn Sun Group",
                "location": "Đà Nẵng",
                "category": "Kinh doanh / Bán hàng",
                "source_url": "https://www.vietnamworks.com/truong-phong-kinh-doanh-12345",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.raw_data.get("industry") == "Kinh doanh / Bán hàng"
        assert lead.canonical_domain == "vietnamworks.com"
        assert lead.source_url == "https://www.vietnamworks.com/truong-phong-kinh-doanh-12345"

        # Fallback industry when not provided
        raw_fb = RawLeadRecord(
            source_name="vietnamworks",
            source_id="vnw-102",
            data={
                "title": "Chuyên viên nhân sự",
                "company": "Công ty ABC",
                "location": "Hà Nội",
            },
        )
        lead_fb = adapter.normalize_lead(raw_fb)
        assert lead_fb.raw_data.get("industry") == "Tuyển dụng"


class TestLocationPreFilterByIcp:
    """Verify ICP location matching and rejection."""

    def test_job_it_at_hcm_rejected_when_requesting_hn(self) -> None:
        """Scenario: Job IT tại HCM khi yêu cầu HN -> location_match_score thấp, pre_filter_by_icp reject."""
        record_hcm = RawLeadRecord(
            source_name="job_market",
            source_id="job-hcm-1",
            data={
                "title": "Senior Golang Developer",
                "company": "VNG Corporation",
                "location": "Hồ Chí Minh",
            },
        )
        record_hn = RawLeadRecord(
            source_name="job_market",
            source_id="job-hn-1",
            data={
                "title": "Senior Golang Developer",
                "company": "FPT Software",
                "location": "Hà Nội",
            },
        )

        # ICP specifying Hà Nội
        icp_hn = ICPCriteria(target_locations=["Hà Nội"])
        passes_hcm, score_hcm = LeadGenOrchestrator.pre_filter_by_icp(record_hcm, icp_hn)
        assert passes_hcm is False
        assert score_hcm == 0.0

        passes_hn, score_hn = LeadGenOrchestrator.pre_filter_by_icp(record_hn, icp_hn)
        assert passes_hn is True
        assert score_hn >= 75.0

        # ICP with dict format containing city="HN"
        icp_city_hn = {"city": "HN"}
        passes_hcm_city, score_hcm_city = LeadGenOrchestrator.pre_filter_by_icp(record_hcm, icp_city_hn)  # type: ignore[arg-type]
        assert passes_hcm_city is False
        assert score_hcm_city == 0.0

        passes_hn_city, score_hn_city = LeadGenOrchestrator.pre_filter_by_icp(record_hn, icp_city_hn)  # type: ignore[arg-type]
        assert passes_hn_city is True
        assert score_hn_city >= 75.0

    def test_nationwide_targeting_allows_all_locations(self) -> None:
        """Nationwide targeting ('toàn quốc' / '*') must allow leads from any city."""
        record_hcm = RawLeadRecord(
            source_name="job_market",
            source_id="job-hcm-2",
            data={"title": "Dev", "location": "Hồ Chí Minh"},
        )
        for wild in ["Toàn quốc", "toàn quốc", "*"]:
            passes, score = LeadGenOrchestrator.pre_filter_by_icp(
                record_hcm, ICPCriteria(target_locations=[wild])
            )
            assert passes is True
            assert score >= 75.0

    def test_embedded_location_profile_in_icp(self) -> None:
        """Embedded location_profile in ICPCriteria is evaluated when location_profile arg is None."""
        record_hn = RawLeadRecord(
            source_name="job_market",
            source_id="job-hn-3",
            data={"title": "Dev", "location": "Hà Nội"},
        )
        icp_dict = {
            "location_profile": {
                "province_code": "SG",
                "province_name": "Hồ Chí Minh",
            }
        }
        passes, score = LeadGenOrchestrator.pre_filter_by_icp(record_hn, icp_dict, location_profile=None)  # type: ignore[arg-type]
        assert passes is False
        assert score == 0.0

    def test_bds_address_comma_only_no_index_error(self) -> None:
        """Comma-only location strings do not raise IndexError."""
        adapter = BatdongsanLeadAdapter()
        raw = RawLeadRecord(
            source_name="batdongsan",
            source_id="bds-comma",
            data={"location": ", , ,", "title": "Bán nhà"},
        )
        lead = adapter.normalize_lead(raw)
        assert lead.company_name == "Bất động sản"

    def test_job_market_source_url_propagation(self) -> None:
        """JobMarketLeadAdapter propagates job_url to source_url."""
        adapter = JobMarketLeadAdapter()
        raw = RawLeadRecord(
            source_name="job_market",
            source_id="jm-url",
            data={
                "title": "Backend Dev",
                "company": "KMS",
                "job_url": "https://itviec.com/it-jobs/backend-dev-kms",
            },
        )
        lead = adapter.normalize_lead(raw)
        assert lead.source_url == "https://itviec.com/it-jobs/backend-dev-kms"
        assert lead.raw_data.get("source_url") == "https://itviec.com/it-jobs/backend-dev-kms"
        assert lead.canonical_domain is not None
        assert "itviec.com" in lead.canonical_domain
