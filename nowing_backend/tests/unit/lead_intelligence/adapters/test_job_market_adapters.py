"""Unit tests for Job Market lead source adapters: TopCV, ITviec, VnJobs, VietnamWorks (Story 21.15 / Story 21.20)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

pytestmark = pytest.mark.unit


class TestJobMarketLeadAdapter:
    """Validate TopCV & ITviec recruitment postings adapter."""

    @pytest.mark.asyncio
    async def test_aggregates_topcv_and_itviec(self) -> None:
        """Should search recruitment portals and extract company hiring signals."""
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


class TestVnJobsLeadAdapter:
    """Validate VnJobs aggregate lead adapter."""

    @pytest.mark.asyncio
    async def test_search_leads_and_normalize(self) -> None:
        """Should aggregate job listings and normalize to company leads."""
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
        adapter = VietnamWorksLeadAdapter()
        item = {
            "job_description": "Liên hệ anh Hùng 0912345678",
            "job_requirement": "",
        }
        redacted = adapter._redact_job_text(item)
        assert "0912345678" not in redacted["job_description"]
