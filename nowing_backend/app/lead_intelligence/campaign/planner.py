"""Lead Generation Campaign Planner (Story 21.15 / Signal-First Architecture)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.adapters.base import LeadSourceCategory
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.schemas import (
    CampaignPlanResponse,
    CampaignSpec,
    SourcePlanAllocation,
    SubTaskPlan,
)

logger = logging.getLogger(__name__)


class LeadGenPlanner:
    """Decomposes a declarative CampaignSpec into concrete SubTaskPlan items."""

    def __init__(self, registry: LeadSourceAdapterRegistry | None = None) -> None:
        self.registry = registry or LeadSourceAdapterRegistry.get_default()

    def plan_from_campaign(
        self, spec: CampaignSpec
    ) -> tuple[list[SubTaskPlan], list[str]]:
        """
        Generate execution subtasks for each resolved scraper adapter based on campaign specs,
        ICP criteria, intent triggers, and source budget limits.

        Returns:
            A tuple of (subtask_plans, expected_sources).
        """
        resolved_adapters, location_fallback = self.registry.resolve_adapters_for_campaign(spec)

        warnings: list[str] = []
        if location_fallback:
            warning_msg = (
                f"No adapter has explicit coverage for location "
                f"{spec.location_profile.province_code if spec.location_profile else ''}; "
                "falling back to keyword-based routing."
            )
            warnings.append(warning_msg)
            logger.warning(warning_msg)

        if not resolved_adapters:
            logger.warning(
                "No adapters resolved for campaign '%s' (workspace %s)",
                spec.name,
                spec.workspace_id,
            )
            return [], []

        budget_map: dict[str, int] = {}
        priority_map: dict[str, int] = {}
        for b in spec.source_budgets:
            src_k = b.source_name.lower().strip()
            budget_map[src_k] = b.max_leads
            priority_map[src_k] = b.priority

        subtasks: list[SubTaskPlan] = []
        expected_sources: list[str] = []

        for adapter in resolved_adapters:
            src_name = adapter.source_name
            src_key = src_name.lower().strip()
            expected_sources.append(src_name)

            # Determine query for this specific adapter
            adapter_query = self._build_query_for_adapter(spec, adapter.category)
            adapter_limit = budget_map.get(
                src_key, min(50, spec.max_total_leads)
            )
            adapter_priority = priority_map.get(src_key, 1)

            # Build platform specific filters from ICP
            filters: dict[str, Any] = {}
            if spec.icp_criteria.target_locations:
                filters["locations"] = list(spec.icp_criteria.target_locations)
                filters["target_locations"] = list(spec.icp_criteria.target_locations)
            if spec.icp_criteria.target_industries:
                filters["industries"] = list(spec.icp_criteria.target_industries)
                filters["target_industries"] = list(spec.icp_criteria.target_industries)
            if spec.icp_criteria.target_keywords:
                filters["keywords"] = list(spec.icp_criteria.target_keywords)
                filters["target_keywords"] = list(spec.icp_criteria.target_keywords)
            if spec.icp_criteria.negative_keywords:
                filters["negative_keywords"] = list(spec.icp_criteria.negative_keywords)

            subtasks.append(
                SubTaskPlan(
                    source_name=src_name,
                    query=adapter_query,
                    limit=adapter_limit,
                    priority=adapter_priority,
                    filters=filters,
                    category=adapter.category,
                )
            )

        # Backwards-compatible: most callers expect two values.
        # The third value is the warnings list; ignored when not unpacked.
        return subtasks, expected_sources

    def _map_coverage_quality(self, score: float) -> str:
        """Map a 0.0-1.0 location coverage score to a discrete quality tier."""
        if score >= 0.9:
            return "high"
        if score >= 0.6:
            return "medium"
        if score >= 0.3:
            return "low"
        return "none"

    def _build_source_allocations(
        self, spec: CampaignSpec, resolved_adapters: list[Any]
    ) -> list[SourcePlanAllocation]:
        """Build pre-flight source allocations with coverage metadata."""
        budget_map: dict[str, int] = {}
        priority_map: dict[str, int] = {}
        for b in spec.source_budgets:
            src_k = b.source_name.lower().strip()
            budget_map[src_k] = b.max_leads
            priority_map[src_k] = b.priority

        allocations: list[SourcePlanAllocation] = []
        for adapter in resolved_adapters:
            src_name = adapter.source_name
            src_key = src_name.lower().strip()

            coverage_score = self.registry.calculate_location_coverage_score(
                adapter, spec.location_profile
            )
            coverage_quality = self._map_coverage_quality(coverage_score)

            status: str = "ready"
            degraded_reason: str | None = None
            if coverage_quality in ("low", "none"):
                status = "degraded"
                degraded_reason = (
                    f"Location coverage for {src_name} is {coverage_quality} "
                    f"for the targeted province/districts."
                )
            elif getattr(adapter, "last_execution_status", "ok") != "ok":
                status = "degraded"
                degraded_reason = (
                    f"Adapter {src_name} reported last execution status: "
                    f"{adapter.last_execution_status}"
                )

            supported_provinces = list(getattr(adapter, "supported_provinces", ["*"]) or ["*"])

            allocations.append(
                SourcePlanAllocation(
                    source_name=src_name,
                    category=adapter.category.value,
                    allocated_limit=budget_map.get(src_key, min(50, spec.max_total_leads)),
                    priority=priority_map.get(src_key, 1),
                    location_coverage_quality=coverage_quality,
                    location_coverage_score=round(coverage_score, 4),
                    supported_provinces=supported_provinces,
                    status=status,
                    degraded_reason=degraded_reason,
                )
            )

        return allocations

    def _estimate_reachable_leads(
        self, spec: CampaignSpec, allocations: list[SourcePlanAllocation]
    ) -> int:
        """Estimate reachable leads as the sum of allocated limits."""
        if not allocations:
            return 0
        return min(sum(a.allocated_limit for a in allocations), spec.max_total_leads)

    def _estimate_cost(self, spec: CampaignSpec) -> tuple[int, int]:
        """Return (cost_vnd, cost_micros) for the campaign."""
        # FR-69: base lead 1,500 VND; verified unlock 5,000 VND.
        auto_unlock = (
            spec.source_budgets
            and any(getattr(b, "auto_unlock", False) for b in spec.source_budgets)
        )
        cost_per_lead = 5000 if auto_unlock else 1500
        cost_vnd = spec.max_total_leads * cost_per_lead
        cost_micros = cost_vnd * 40
        return cost_vnd, cost_micros

    def create_preflight_plan(self, spec: CampaignSpec) -> CampaignPlanResponse:
        """Build an enriched CampaignPlanResponse without mutating plan_from_campaign."""
        subtasks, expected_sources = self.plan_from_campaign(spec)

        resolved_adapters, location_fallback = self.registry.resolve_adapters_for_campaign(spec)

        warnings: list[str] = []
        if location_fallback:
            warning_msg = (
                f"No adapter has explicit coverage for location "
                f"{spec.location_profile.province_code if spec.location_profile else ''}; "
                "falling back to keyword-based routing."
            )
            warnings.append(warning_msg)

        source_allocations = self._build_source_allocations(spec, resolved_adapters)
        estimated_reachable_leads = self._estimate_reachable_leads(spec, source_allocations)
        estimated_cost_vnd, estimated_cost_micros = self._estimate_cost(spec)

        return CampaignPlanResponse(
            campaign_name=spec.name,
            workspace_id=spec.workspace_id,
            total_planned_sources=len(expected_sources),
            expected_sources=expected_sources,
            subtasks=subtasks,
            source_allocations=source_allocations,
            estimated_reachable_leads=estimated_reachable_leads,
            estimated_cost_micros=estimated_cost_micros,
            estimated_cost_vnd=estimated_cost_vnd,
            warnings=warnings,
        )

    def _build_query_for_adapter(
        self, spec: CampaignSpec, category: LeadSourceCategory
    ) -> str:
        """Construct a refined query combining base query, target keywords, and category focus."""
        base_query = spec.query.strip() if spec.query else ""

        # If base query is provided, check if we should augment it with keywords
        if base_query:
            return base_query

        # Fallback to synthesizing query from keywords and ICP
        query_parts: list[str] = []
        if spec.icp_criteria.target_keywords:
            query_parts.extend(spec.icp_criteria.target_keywords[:3])
        if spec.icp_criteria.target_industries:
            query_parts.extend(spec.icp_criteria.target_industries[:2])
        if spec.icp_criteria.target_locations:
            query_parts.extend(spec.icp_criteria.target_locations[:2])

        if query_parts:
            return " ".join(query_parts)

        # Fallback defaults by category
        if category == LeadSourceCategory.REAL_ESTATE:
            return "Bất động sản nhà đất"
        if category == LeadSourceCategory.JOB_MARKET:
            return "Tuyển dụng nhân sự IT doanh nghiệp"
        if category == LeadSourceCategory.ENTERPRISE:
            return "Doanh nghiệp đấu thầu"
        return "Tìm kiếm doanh nghiệp"
