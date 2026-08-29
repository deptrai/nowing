"""Lead Generation Campaign Planner (Story 21.15 / Signal-First Architecture)."""

from __future__ import annotations

import logging
from typing import Any

from app.lead_intelligence.adapters.base import LeadSourceCategory
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.schemas import CampaignSpec, SubTaskPlan

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
        resolved_adapters = self.registry.resolve_adapters_for_campaign(spec)

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

        return subtasks, expected_sources

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
