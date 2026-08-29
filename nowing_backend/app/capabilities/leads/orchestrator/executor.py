"""Executor for ``leads.multi_source_gen`` capability (Story 21.15)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.lead_intelligence.schemas import (
    MultiSourceLeadGenRequest,
    MultiSourceLeadGenResponse,
)
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
)


def build_multi_source_lead_gen_executor() -> Callable[
    ..., Awaitable[MultiSourceLeadGenResponse]
]:
    """Construct async executor for leads.multi_source_gen capability."""

    async def _execute(
        payload: MultiSourceLeadGenRequest | dict[str, Any],
        ctx: CapabilityContext,
    ) -> MultiSourceLeadGenResponse:
        req = (
            payload
            if isinstance(payload, MultiSourceLeadGenRequest)
            else MultiSourceLeadGenRequest.model_validate(payload)
        )
        orchestrator = LeadGenOrchestrator()

        filters: dict[str, Any] = {}
        if req.locations:
            filters["locations"] = req.locations
        if req.target_sources:
            filters["target_sources"] = req.target_sources
        if req.target_keywords:
            filters["target_keywords"] = req.target_keywords
        if req.negative_keywords:
            filters["negative_keywords"] = req.negative_keywords
        if req.preferred_channels:
            filters["preferred_channels"] = req.preferred_channels

        effective_limit = min(req.limit, 10) if req.smoke_test else req.limit

        campaign_spec = None
        if req.campaign_id or req.smoke_test or req.target_sources or req.intent:
            from app.lead_intelligence.campaign.schemas import (
                CampaignSpec,
                ICPCriteria,
            )

            intent_value = req.intent if isinstance(req.intent, str) else req.intent.value
            depth_value = (
                req.enrichment_depth.value
                if hasattr(req.enrichment_depth, "value")
                else str(req.enrichment_depth)
            )
            campaign_spec = CampaignSpec(
                name=req.campaign_id or f"sales-copilot-{ctx.workspace_id}",
                workspace_id=ctx.workspace_id,
                client_id=getattr(ctx, "client_id", None),
                table_id=req.table_id,
                query=req.query,
                icp_criteria=ICPCriteria(
                    target_keywords=req.target_keywords,
                    negative_keywords=req.negative_keywords,
                    target_locations=req.locations or [],
                    target_industries=[req.product_type] if req.product_type else [],
                    min_fit_score=req.min_fit_score,
                ),
                intent_tags=[intent_value, req.product_type] if req.product_type else [intent_value],
                target_sources=req.target_sources,
                max_total_leads=effective_limit,
                metadata={
                    "smoke_test": req.smoke_test,
                    "enrichment_depth": depth_value,
                    "product_type": req.product_type,
                    "price_segment": req.price_segment,
                    "preferred_channels": req.preferred_channels,
                },
            )

        result = await orchestrator.execute_and_persist(
            session=ctx.session,
            workspace_id=ctx.workspace_id,
            query=req.query,
            table_id=req.table_id,
            limit=effective_limit,
            filters=filters or None,
            campaign_spec=campaign_spec,
        )
        return MultiSourceLeadGenResponse(
            status=result.status,
            total_discovered=result.total_discovered,
            total_deduplicated=result.total_deduplicated,
            leads=[item.model_dump() for item in result.leads],
            degraded_sources=result.degraded_sources,
            table_id=result.table_id,
        )

    return _execute
