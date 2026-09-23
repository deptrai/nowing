"""Unit tests for Pre-Flight Lead Plan Summary (Story 26.27)."""

from __future__ import annotations

from typing import Any

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


class MockBdsAdapter(LeadSourceAdapter):
    """Mock BĐS adapter with strong SG/HN coverage."""

    source_name = "batdongsan"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN", "SG", "DN", "*"]
    coverage_quality_by_location = {
        "HN": "high",
        "SG": "high",
        "DN": "medium",
    }
    last_execution_status = "ok"

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


class MockJobAdapter(LeadSourceAdapter):
    """Mock adapter with HN medium + nationwide wildcard."""

    source_name = "topcv"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN", "*"]
    coverage_quality_by_location = {"HN": "medium"}
    last_execution_status = "ok"

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


class MockStrictJobAdapter(LeadSourceAdapter):
    """Mock adapter with HN medium but no wildcard."""

    source_name = "strict_topcv"
    category = LeadSourceCategory.REAL_ESTATE
    supported_provinces = ["HN"]
    coverage_quality_by_location = {"HN": "medium"}
    last_execution_status = "ok"

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


class MockDegradedAdapter(LeadSourceAdapter):
    """Mock adapter reporting degraded last execution status."""

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
    reg.register(MockJobAdapter())
    reg.register(MockDegradedAdapter())
    return reg


def _build_spec(location: LocationProfilePayload | None = None) -> CampaignSpec:
    return CampaignSpec(
        name="Test Pre-Flight Plan",
        workspace_id=1,
        query="nhà đất",
        max_total_leads=100,
        source_budgets=[
            SourceBudget(source_name="batdongsan", max_leads=50, priority=2),
            SourceBudget(source_name="topcv", max_leads=30, priority=1),
        ],
        location_profile=location,
    )


def test_create_preflight_plan_returns_enriched_response(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: create_preflight_plan returns CampaignPlanResponse with all required fields."""
    planner = LeadGenPlanner(registry=registry)
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="SG",
            province_name="TP. Hồ Chí Minh",
        )
    )

    plan = planner.create_preflight_plan(spec)

    assert plan.campaign_name == "Test Pre-Flight Plan"
    assert plan.workspace_id == 1
    assert plan.total_planned_sources > 0
    assert plan.expected_sources
    assert plan.source_allocations
    assert plan.estimated_reachable_leads > 0
    assert plan.estimated_cost_vnd == 100 * 1500
    assert plan.estimated_cost_micros == plan.estimated_cost_vnd * 40
    assert isinstance(plan.warnings, list)


def test_source_allocations_coverage_quality(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: source_allocations contain coverage scores and quality labels."""
    planner = LeadGenPlanner(registry=registry)
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="SG",
            province_name="TP. Hồ Chí Minh",
        )
    )

    # Force all mock adapters to be included in plan for this assertion
    spec.target_sources = ["batdongsan", "topcv", "degraded_social"]

    plan = planner.create_preflight_plan(spec)
    by_name = {a.source_name: a for a in plan.source_allocations}

    assert "batdongsan" in by_name
    bds = by_name["batdongsan"]
    assert bds.location_coverage_quality == "high"
    assert bds.location_coverage_score == 1.0
    assert bds.status == "ready"
    assert bds.allocated_limit == 50
    assert bds.priority == 2
    assert "SG" in bds.supported_provinces

    assert "topcv" in by_name
    topcv = by_name["topcv"]
    # topcv declares HN medium but also wildcard support, so SG falls back to nationwide 0.6
    assert topcv.location_coverage_quality == "medium"
    assert topcv.location_coverage_score == 0.6
    assert topcv.status == "ready"
    assert topcv.degraded_reason is None


def test_coverage_quality_mapping(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: coverage score thresholds map to correct quality tiers."""
    planner = LeadGenPlanner(registry=registry)

    assert planner._map_coverage_quality(0.95) == "high"
    assert planner._map_coverage_quality(0.9) == "high"
    assert planner._map_coverage_quality(0.75) == "medium"
    assert planner._map_coverage_quality(0.6) == "medium"
    assert planner._map_coverage_quality(0.45) == "low"
    assert planner._map_coverage_quality(0.3) == "low"
    assert planner._map_coverage_quality(0.15) == "none"


def test_fallback_warning_for_uncovered_location() -> None:
    """AC-1: fallback warning appears when no adapter covers the target location."""
    reg = LeadSourceAdapterRegistry()
    reg._adapters.clear()
    # Strict adapter with no wildcard
    reg.register(MockStrictJobAdapter())

    planner = LeadGenPlanner(registry=reg)
    # Cà Mau (CM) is not covered by any strict adapter
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="CM",
            province_name="Cà Mau",
        )
    )
    spec.target_sources = ["strict_topcv"]
    spec.source_budgets = [
        SourceBudget(source_name="strict_topcv", max_leads=30, priority=1),
    ]

    plan = planner.create_preflight_plan(spec)

    assert any("No adapter has explicit coverage" in w for w in plan.warnings)
    assert any(
        a.location_coverage_quality == "none" for a in plan.source_allocations
    )


def test_degraded_adapter_status(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: adapter with last_execution_status != ok is marked degraded."""
    planner = LeadGenPlanner(registry=registry)
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="SG",
            province_name="TP. Hồ Chí Minh",
        )
    )
    # Force degraded_social to be included in plan
    spec.target_sources = ["degraded_social"]

    plan = planner.create_preflight_plan(spec)
    degraded = [a for a in plan.source_allocations if a.source_name == "degraded_social"]
    assert degraded
    assert degraded[0].status == "degraded"
    assert "degraded" in (degraded[0].degraded_reason or "").lower()


def test_cost_with_auto_unlock(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: cost reflects verified phone unlock pricing when auto_unlock is set."""
    planner = LeadGenPlanner(registry=registry)
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="SG",
            province_name="TP. Hồ Chí Minh",
        )
    )
    spec.source_budgets = [
        SourceBudget(source_name="batdongsan", max_leads=50, priority=2, auto_unlock=True),
    ]

    plan = planner.create_preflight_plan(spec)

    assert plan.estimated_cost_vnd == 100 * 5000
    assert plan.estimated_cost_micros == plan.estimated_cost_vnd * 40


def test_plan_from_campaign_backwards_compatible(registry: LeadSourceAdapterRegistry) -> None:
    """AC-1: plan_from_campaign still returns (subtasks, expected_sources) tuple."""
    planner = LeadGenPlanner(registry=registry)
    spec = _build_spec(
        location=LocationProfilePayload(
            province_code="SG",
            province_name="TP. Hồ Chí Minh",
        )
    )

    subtasks, expected_sources = planner.plan_from_campaign(spec)

    assert isinstance(subtasks, list)
    assert isinstance(expected_sources, list)
    assert len(subtasks) == len(expected_sources)
    assert all(isinstance(s.source_name, str) for s in subtasks)
