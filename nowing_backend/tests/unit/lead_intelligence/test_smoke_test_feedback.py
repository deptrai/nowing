"""Unit tests for Smoke Test Feedback Loop (Story 26.29)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.planner import LeadGenPlanner
from app.lead_intelligence.campaign.schemas import CampaignSpec, SourceBudget
from app.lead_intelligence.schemas import LocationProfilePayload
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LocationMatchMetadata,
)


class MockBdsAdapter(LeadSourceAdapter):
    """Mock BĐS adapter returning one HN and one outside lead."""

    source_name = "batdongsan"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN", "SG"]
    coverage_quality_by_location = {"HN": "high", "SG": "high"}
    last_execution_status = "ok"

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        return [
            RawLeadRecord(
                source_name="batdongsan",
                source_id="hn-1",
                data={
                    "title": "Bán nhà Cầu Giấy",
                    "address": "Cầu Giấy, Hà Nội",
                    "company_name": "Môi giới Cầu Giấy",
                },
            ),
            RawLeadRecord(
                source_name="batdongsan",
                source_id="sg-1",
                data={
                    "title": "Bán nhà Quận 1",
                    "address": "Quận 1, TP Hồ Chí Minh",
                    "company_name": "Môi giới Q1",
                },
            ),
        ]

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        data = raw_record.data
        return NormalizedLead(
            source_name="batdongsan",
            source_id=raw_record.source_id,
            title=data.get("title"),
            company_name=data.get("company_name"),
            address=data.get("address"),
            city="Hà Nội" if "Cầu Giấy" in str(data.get("address")) else "TP Hồ Chí Minh",
            primary_phone="0901234567" if raw_record.source_id == "hn-1" else "0912345678",
            canonical_domain="caugay.example" if raw_record.source_id == "hn-1" else "q1.example",
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        return []


class MockDegradedAdapter(LeadSourceAdapter):
    """Mock adapter in degraded state."""

    source_name = "degraded_social"
    category = LeadSourceCategory.SOCIAL
    supported_provinces = ["*"]
    coverage_quality_by_location = {}
    last_execution_status = "degraded"

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        raise NotImplementedError

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        return []


@pytest.fixture
def registry() -> LeadSourceAdapterRegistry:
    reg = LeadSourceAdapterRegistry()
    reg._adapters.clear()
    reg.register(MockBdsAdapter())
    reg.register(MockDegradedAdapter())
    return reg


def _build_spec(**kwargs: Any) -> CampaignSpec:
    location = kwargs.get("location")
    return CampaignSpec(
        name="Test Smoke",
        workspace_id=1,
        query="nhà đất",
        max_total_leads=5,
        source_budgets=[
            SourceBudget(source_name="batdongsan", max_leads=5, priority=1),
        ],
        location_profile=location,
        **{k: v for k, v in kwargs.items() if k != "location" and k != "max_total_leads"},
    )


@pytest.mark.unit
class TestLocationMatchMetadata:
    """Red-phase unit tests for AC-1 / AC-6 backend telemetry."""

    def test_metadata_counts_matched_and_outside_leads(self) -> None:
        """AC-1: location_match_metadata counts matched vs outside leads."""
        in_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="hn-1",
            location_match_score=90.0,
        )
        out_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="sg-1",
            location_match_score=0.0,
        )

        metadata = LeadGenOrchestrator._build_location_match_metadata(
            final_leads=[in_lead, out_lead],
            degraded_sources=[],
            adapters=[],
            location_profile=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
            icp_criteria=None,
        )

        assert isinstance(metadata, LocationMatchMetadata)
        assert metadata.matched_count == 1
        assert metadata.outside_count == 1
        assert metadata.zero_leads_reason is None

    def test_zero_leads_no_data_in_location(self) -> None:
        """AC-6: empty result with location set → NO_DATA_IN_LOCATION."""
        metadata = LeadGenOrchestrator._build_location_match_metadata(
            final_leads=[],
            degraded_sources=[],
            adapters=[],
            location_profile=LocationProfilePayload(
                province_code="HN",
                province_name="Hà Nội",
                district_codes=["001"],
            ),
            icp_criteria=None,
        )

        assert metadata.zero_leads_reason == "NO_DATA_IN_LOCATION"
        assert "NO_DATA_IN_LOCATION" in metadata.zero_leads_diagnostics

    def test_zero_leads_source_degraded(self) -> None:
        """AC-6: every adapter degraded → SOURCE_DEGRADED."""
        degraded = ["degraded_social"]
        adapters = [MockDegradedAdapter()]

        metadata = LeadGenOrchestrator._build_location_match_metadata(
            final_leads=[],
            degraded_sources=degraded,
            adapters=adapters,
            location_profile=None,
            icp_criteria=None,
        )

        assert metadata.zero_leads_reason == "SOURCE_DEGRADED"

    def test_zero_leads_filters_too_narrow(self) -> None:
        """AC-6: strict min_fit_score with no leads → FILTERS_TOO_NARROW."""
        from app.lead_intelligence.campaign.schemas import ICPCriteria

        metadata = LeadGenOrchestrator._build_location_match_metadata(
            final_leads=[],
            degraded_sources=[],
            adapters=[],
            location_profile=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
            icp_criteria=ICPCriteria(min_fit_score=80.0, negative_keywords=["cheap"]),
        )

        assert metadata.zero_leads_reason == "FILTERS_TOO_NARROW"

    def test_excluded_identities_filter_out_smoke_leads(self) -> None:
        """AC-5: excluded_identities drop known smoke-test leads before dedup."""
        from app.lead_intelligence.campaign.schemas import ICPCriteria

        lead1 = NormalizedLead(
            source_name="batdongsan",
            source_id="hn-1",
            canonical_domain="caugay.example",
            primary_phone="0901234567",
            location_match_score=90.0,
        )
        lead2 = NormalizedLead(
            source_name="batdongsan",
            source_id="hn-2",
            canonical_domain="other.example",
            primary_phone="0909999999",
            location_match_score=90.0,
        )

        spec = _build_spec(
            location=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
            excluded_identities=["caugay.example"],
        )
        spec.icp_criteria = ICPCriteria(min_fit_score=0.0)

        with patch.object(
            LeadSourceAdapterRegistry,
            "get_default",
            return_value=MagicMock(
                resolve_adapters_for_campaign=lambda s: ([MockBdsAdapter()], False)
            ),
        ):
            orchestrator = LeadGenOrchestrator()
            result = orchestrator._build_location_match_metadata(
                final_leads=[lead1, lead2],
                degraded_sources=[],
                adapters=[],
                location_profile=spec.location_profile,
                icp_criteria=spec.icp_criteria,
            )

        assert result.matched_count == 2


@pytest.mark.unit
class TestDiagnoseZeroLeads:
    """Red-phase unit tests for AC-6 diagnostic helper."""

    def test_diagnose_narrow_filters(self) -> None:
        """AC-6: high min_fit_score triggers FILTERS_TOO_NARROW."""
        from app.lead_intelligence.campaign.schemas import ICPCriteria

        spec = _build_spec(
            location=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
        )
        spec.icp_criteria = ICPCriteria(min_fit_score=95.0)

        diagnostic = LeadGenPlanner.diagnose_zero_leads_cause(spec)

        assert diagnostic["reason"] == "FILTERS_TOO_NARROW"
        assert any("Giảm ngưỡng" in action for action in diagnostic["recovery_actions"])

    def test_diagnose_degraded_sources(self) -> None:
        """AC-6: degraded adapter results trigger SOURCE_DEGRADED."""
        spec = _build_spec()
        adapter_results = [
            {"source_name": "degraded_social", "count": 0, "degraded_reason": "rate_limited"},
        ]

        diagnostic = LeadGenPlanner.diagnose_zero_leads_cause(
            spec, adapter_results=adapter_results, status="degraded"
        )

        assert diagnostic["reason"] == "SOURCE_DEGRADED"

    def test_diagnose_no_data_offers_expansion(self) -> None:
        """AC-6: empty location with district codes offers province expansion."""
        spec = _build_spec(
            location=LocationProfilePayload(
                province_code="HN",
                province_name="Hà Nội",
                district_codes=["001"],
            )
        )

        diagnostic = LeadGenPlanner.diagnose_zero_leads_cause(spec)

        assert diagnostic["reason"] == "NO_DATA_IN_LOCATION"
        assert any("Mở rộng ra toàn tỉnh Hà Nội" in action for action in diagnostic["recovery_actions"])


@pytest.mark.asyncio
@pytest.mark.unit
class TestSmokeTestExecute:
    """Red-phase unit tests for AC-1 / AC-5 execute_multi_source_lead_gen."""

    async def test_smoke_test_returns_up_to_5_leads(self, registry: LeadSourceAdapterRegistry) -> None:
        """AC-1: execute_multi_source_lead_gen with max_total_leads=5 returns <=5 leads."""
        spec = _build_spec(
            location=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
            max_total_leads=5,
        )

        orchestrator = LeadGenOrchestrator(registry=registry)
        result = await orchestrator.execute_multi_source_lead_gen(
            workspace_id=1,
            campaign_spec=spec,
            limit=5,
        )

        assert result.total_discovered <= 5
        assert result.location_match_metadata is not None
        assert isinstance(result.location_match_metadata, LocationMatchMetadata)

    async def test_smoke_test_excluded_identities_drop_known_leads(self, registry: LeadSourceAdapterRegistry) -> None:
        """AC-5: excluded_identities filter out previously previewed leads."""
        spec = _build_spec(
            location=LocationProfilePayload(province_code="HN", province_name="Hà Nội"),
            max_total_leads=5,
            excluded_identities=["caugay.example"],
        )

        orchestrator = LeadGenOrchestrator(registry=registry)
        result = await orchestrator.execute_multi_source_lead_gen(
            workspace_id=1,
            campaign_spec=spec,
            limit=5,
        )

        domains = {lead.canonical_domain for lead in result.leads}
        assert "caugay.example" not in domains
