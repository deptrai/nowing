"""Unit tests for LeadGenPlanner with Websets pending status (Story 41.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.adapters.websets import WebsetsAdapter
from app.lead_intelligence.campaign.planner import LeadGenPlanner
from app.lead_intelligence.campaign.schemas import CampaignSpec, SourceBudget

pytestmark = pytest.mark.unit


class MockPendingWebsetsAdapter(LeadSourceAdapter):
    source_name = "websets"
    category = LeadSourceCategory.ENTERPRISE
    supported_provinces: list[str] = []
    coverage_quality_by_location: dict[str, str] = {}
    last_execution_status = "pending"

    def __init__(self) -> None:
        super().__init__()
        self.supported_provinces = ["*"]
        self.coverage_quality_by_location = {}

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
    source_name = "degraded_source"
    category = LeadSourceCategory.SOCIAL
    supported_provinces: list[str] = []
    coverage_quality_by_location: dict[str, str] = {}
    last_execution_status = "degraded"

    def __init__(self) -> None:
        super().__init__()
        self.supported_provinces = ["*"]
        self.coverage_quality_by_location = {}

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


class TestLeadGenPlannerWebsets:
    async def test_planner_sets_pending_status_for_async_adapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reg = LeadSourceAdapterRegistry()
        # Real WebsetsAdapter: pending là trạng thái sau khi search_leads() OK
        real_adapter = WebsetsAdapter()
        real_adapter.last_execution_status = "pending"
        monkeypatch.setattr(real_adapter, "get_workspace_status", AsyncMock(return_value="pending"))
        reg.register(real_adapter)

        planner = LeadGenPlanner(registry=reg)
        spec = CampaignSpec(
            name="Tech Campaign",
            workspace_id=1,
            query="find tech companies",
            max_total_leads=50,
            source_budgets=[
                SourceBudget(source_name="websets", max_leads=50, priority=1),
            ],
        )

        plan = await planner.create_preflight_plan(spec)
        allocations = {a.source_name: a for a in plan.source_allocations}

        assert "websets" in allocations
        webset_alloc = allocations["websets"]
        assert webset_alloc.status == "pending"
        assert webset_alloc.degraded_reason == "Asynchronous webset build in progress"

    async def test_planner_distinguishes_pending_from_degraded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reg = LeadSourceAdapterRegistry()
        real_adapter = WebsetsAdapter()
        real_adapter.last_execution_status = "pending"
        monkeypatch.setattr(real_adapter, "get_workspace_status", AsyncMock(return_value="pending"))
        reg.register(real_adapter)
        reg.register(MockDegradedAdapter())

        planner = LeadGenPlanner(registry=reg)
        spec = CampaignSpec(
            name="Search Campaign",
            workspace_id=1,
            query="search companies",
            max_total_leads=100,
            source_budgets=[
                SourceBudget(source_name="websets", max_leads=50, priority=1),
                SourceBudget(source_name="degraded_source", max_leads=50, priority=2),
            ],
        )

        plan = await planner.create_preflight_plan(spec)
        allocations = {a.source_name: a for a in plan.source_allocations}

        assert allocations["websets"].status == "pending"
        assert allocations["degraded_source"].status == "degraded"

    def test_registry_contains_websets_adapter(self) -> None:
        reg = LeadSourceAdapterRegistry.get_default()
        adapter = reg.get("websets")
        assert adapter is not None
        assert isinstance(adapter, WebsetsAdapter)

        # Match intent
        matches = reg.resolve_adapters_for_intent(
            "Tạo webset tìm kiếm công ty công nghệ"
        )
        source_names = [a.source_name for a in matches]
        assert "websets" in source_names
