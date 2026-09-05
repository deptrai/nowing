"""Unit tests for Location-Aware Adapter Routing & Coverage Quality (Story 26.26)."""

from __future__ import annotations

from typing import Any

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.schemas import LocationProfilePayload


class MockRegionalAdapter(LeadSourceAdapter):
    """Mock adapter focusing on Da Nang and Central region."""

    source_name = "danang_local_bds"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["DN", "QN", "QNA"]
    coverage_quality_by_location = {
        "DN": "high",
        "QN": "medium",
        "492": "high",  # Hai Chau district in Da Nang
    }

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


class MockNationwideAdapter(LeadSourceAdapter):
    """Mock adapter covering nationwide with generic quality."""

    source_name = "nationwide_general"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["*"]
    coverage_quality_by_location = {
        "HN": "high",
        "SG": "high",
    }

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


class MockNorthernAdapter(LeadSourceAdapter):
    """Mock adapter strictly covering Northern provinces."""

    source_name = "north_exclusive"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN", "HP"]
    coverage_quality_by_location = {
        "HN": "high",
        "HP": "high",
    }

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


def test_calculate_location_coverage_score() -> None:
    """AC-1 & AC-2: calculate_location_coverage_score produces accurate quality ratings."""
    reg = LeadSourceAdapterRegistry()
    regional = MockRegionalAdapter()
    nationwide = MockNationwideAdapter()
    northern = MockNorthernAdapter()

    # Da Nang target profile
    dn_profile = LocationProfilePayload(
        province_code="DN",
        province_name="Đà Nẵng",
        district_codes=["492"],
    )

    # Regional has high coverage in DN and district 492
    assert reg.calculate_location_coverage_score(regional, dn_profile) == 1.0

    # Nationwide has wildcard fallback (0.6) for DN (no specific DN override)
    assert reg.calculate_location_coverage_score(nationwide, dn_profile) == 0.6

    # Northern does not support DN
    assert reg.calculate_location_coverage_score(northern, dn_profile) == 0.0

    # None profile returns 1.0 (no penalty)
    assert reg.calculate_location_coverage_score(regional, None) == 1.0


def test_resolve_adapters_for_campaign_composite_ranking() -> None:
    """AC-2: Composite formula (0.4 location + 0.4 vertical + 0.2 cost) prefers high-coverage adapter."""
    reg = LeadSourceAdapterRegistry()
    reg._adapters.clear()

    regional = MockRegionalAdapter()
    nationwide = MockNationwideAdapter()
    northern = MockNorthernAdapter()

    reg.register(regional)
    reg.register(nationwide)
    reg.register(northern)

    # When targeting Da Nang, regional should be ranked first, followed by nationwide, then northern
    dn_profile = LocationProfilePayload(
        province_code="DN",
        province_name="Đà Nẵng",
    )

    ranked, fallback = reg.resolve_adapters_for_campaign(
        prompt="căn hộ biển",
        category=LeadSourceCategory.REAL_ESTATE,
        location_profile=dn_profile,
    )

    assert fallback is False
    assert len(ranked) == 3
    assert ranked[0].source_name == "danang_local_bds"
    assert ranked[1].source_name == "nationwide_general"
    assert ranked[2].source_name == "north_exclusive"


def test_resolve_adapters_for_campaign_fallback_warning() -> None:
    """AC-2: If no adapter covers the requested location, fallback warning is raised."""
    reg = LeadSourceAdapterRegistry()
    reg._adapters.clear()

    # Only northern adapter registered
    northern = MockNorthernAdapter()
    reg.register(northern)

    # Target Ca Mau (CM) which northern does not support
    cm_profile = LocationProfilePayload(
        province_code="CM",
        province_name="Cà Mau",
    )

    ranked, fallback = reg.resolve_adapters_for_campaign(
        prompt="nhà đất",
        category=LeadSourceCategory.REAL_ESTATE,
        location_profile=cm_profile,
    )

    assert fallback is True
    assert len(ranked) == 1
    assert ranked[0].source_name == "north_exclusive"
